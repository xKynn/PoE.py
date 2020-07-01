import binascii
import html
import json as js
import math
import os
import re
import threading
import unicodedata
import xml.etree.cElementTree as Etree
from collections import defaultdict
from collections import namedtuple
from io import BytesIO
from queue import Queue

import urllib3
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps
from bs4 import BeautifulSoup as Soup

from poe.exceptions import AbsentItemBaseException
from poe.exceptions import OutdatedPoBException, RequestException
from poe.models import Weapon, Armour, PassiveSkill, Gem
from poe.price import ItemPriceQuery, CurrencyQuery
from .constants import *

re_range = re.compile(r'\(.+?\)')


# Simple cursor class that lets me handle moving around the image quite well
# also get around the hassle of maintaining position and adding and subtracting.


def strip_unicode(text: str):
    return ''.join((c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn'))


class Cursor:
    def __init__(self, x_start):
        self.x = 0
        self.y = 0
        self.x_start = x_start

    # Return current pos of cursor
    @property
    def pos(self):
        return self.x, self.y

    def move_x(self, quantity):
        self.x += quantity

    def move_y(self, quantity):
        self.y += quantity

    def reset_x(self):
        self.x = self.x_start


# Cause relative paths are ass
_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

# Find links wrapped in [[]] returned by Gamepedia
reg = re.compile(r'\[\[[^\]]+\]\]')
try:
    with open(f"{_dir}/keystones.json") as f:
        keystones = js.load(f)

    with open(f"{_dir}/ascendancy.json") as f:
        asc_nodes = js.load(f)

    with open(f"{_dir}/items.json") as f:
        items = js.load(f)
except Exception:
    pass


def unescape_to_list(props, ret_matches=False):
    matches = reg.findall(props)
    has_table = Soup(html.unescape(props)).select_one('table.mw-collapsed tr')
    if not has_table:
        for match in set(matches):
            if '|' in match:
                props = props.replace(match, match.split('|')[1].strip(']]'))
            else:
                props = props.replace(match, match.strip('[[]]'))
        prop_list = html.unescape(props).replace('<br />', '<br>').split('<br>')
        prop_list = [x.replace('<em class="tc -corrupted">', '').replace('</em>', '') for x in prop_list]
    else:
        # FIXME: non-iterable object
        prop_list = [x.text for x in has_table]

    if ret_matches:
        return prop_list, matches
    return prop_list


class ItemRender:
    def __init__(self, flavor):
        self.flavor = flavor.lower()
        self.font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 15)
        self.lore_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCapsItalic.ttf', 15)
        self.header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        self.namebar_left = Image.open(f'{_dir}//{self.flavor}_namebar_left.png').convert('RGBA')
        self.namebar_right = Image.open(f'{_dir}//{self.flavor}_namebar_right.png').convert('RGBA')
        self.namebar_trans = Image.open(f'{_dir}//{self.flavor}_namebar_trans.png').convert('RGBA')
        self.separator = Image.open(f'{_dir}//{self.flavor}_separator.png').convert('RGBA')
        self.div_frame = Image.open(f'{_dir}//div_frame.png').convert('RGBA')
        self.elder_badge = Image.open(f'{_dir}//elder_badge.png').convert('RGBA')
        self.shaper_badge = Image.open(f'{_dir}//shaper_badge.png').convert('RGBA')
        self.redeemer_badge = Image.open(f'{_dir}//redeemer_badge.png').convert('RGBA')
        self.crusader_badge = Image.open(f'{_dir}//crusader_badge.png').convert('RGBA')
        self.hunter_badge = Image.open(f'{_dir}//hunter_badge.png').convert('RGBA')
        self.warlord_badge = Image.open(f'{_dir}//warlord_badge.png').convert('RGBA')
        self.passive_frame = Image.open(f'{_dir}//passive_frame.png').convert('RGBA')
        self.keystone_frame = Image.open(f'{_dir}//keystone_frame.png').convert('RGBA')
        self.notable_frame = Image.open(f'{_dir}//notable_frame.png').convert('RGBA')
        self.ascendancy_frame = Image.open(f'{_dir}//ascendancy_frame.png').convert('RGBA')
        self.shaper_backgrounds = {
            ('1', '1'): Image.open(f'{_dir}//shaper_bg_1x1.png').convert('RGBA'),
            ('1', '2'): Image.open(f'{_dir}//shaper_bg_1x2.png').convert('RGBA'),
            ('1', '3'): Image.open(f'{_dir}//shaper_bg_1x3.png').convert('RGBA'),
            ('1', '4'): Image.open(f'{_dir}//shaper_bg_1x4.png').convert('RGBA'),
            ('2', '1'): Image.open(f'{_dir}//shaper_bg_2x1.png').convert('RGBA'),
            ('2', '2'): Image.open(f'{_dir}//shaper_bg_2x2.png').convert('RGBA'),
            ('2', '3'): Image.open(f'{_dir}//shaper_bg_2x3.png').convert('RGBA'),
            ('2', '4'): Image.open(f'{_dir}//shaper_bg_2x4.png').convert('RGBA'),
        }
        self.elder_backgrounds = {
            ('1', '1'): Image.open(f'{_dir}//elder_bg_1x1.png').convert('RGBA'),
            ('1', '3'): Image.open(f'{_dir}//elder_bg_1x3.png').convert('RGBA'),
            ('1', '4'): Image.open(f'{_dir}//elder_bg_1x4.png').convert('RGBA'),
            ('2', '1'): Image.open(f'{_dir}//elder_bg_2x1.png').convert('RGBA'),
            ('2', '2'): Image.open(f'{_dir}//elder_bg_2x2.png').convert('RGBA'),
            ('2', '3'): Image.open(f'{_dir}//elder_bg_2x3.png').convert('RGBA'),
            ('2', '4'): Image.open(f'{_dir}//elder_bg_2x4.png').convert('RGBA'),
        }

        # A namedtuple to handle properties.
        # This works fairly well except for Separators which is kinda hacky
        self.prop = namedtuple('Property', ['title', 'text', 'color'])

        # I don't know why PIL does this, but spacing with fonts is not consistent,
        # this means I have to compensate by spacing more after separators and stuff
        self.last_action = str()

    # Go through our total properties and image to get the image/box size
    # I feel the code is a bit redundant considering I have two instances
    # of an if-fest, calc_size and sort_stats.
    # TODO: reduce redundancy
    def calc_size(self, stats, header):
        width = self.header_font.getsize(header)[0] + (self.namebar_left.size[0] * 2) + 4
        height = 0
        last_sep = False
        for stat in stats:
            if stat.title == "Separator":
                height += SEPARATOR_HEIGHT + SEPARATOR_SPACING
                last_sep = True
                continue

            elif stat.title == "Elemental Damage:":
                if last_sep:
                    height += SEPARATOR_SPACING
                else:
                    height += STAT_SPACING
                height += STAT_HEIGHT
                stat_text = stat.title
                for element in stat.text.keys():
                    stat_text += f" {stat.text[element]}"
                last_sep = False

            elif stat.title == "Requires":
                if last_sep:
                    height += SEPARATOR_SPACING
                else:
                    height += STAT_SPACING
                height += STAT_HEIGHT
                stat_text = stat.title
                for attr in stat.text.keys():
                    stat_text += f" {attr.title()} {stat.text[attr]}{'' if list(stat.text.keys())[-1] == attr else ','}"
                last_sep = False

            elif stat.title == "Lore" or stat.title == "Reminder":
                if type(stat.text) is list:
                    ht = LINE_SPACING
                    for line in stat.text:
                        w = self.lore_font.getsize(line)
                        ht += STAT_HEIGHT
                        if w[0] > width:
                            width = w[0]
                    height += ht + STAT_SPACING

                else:
                    w = self.lore_font.getsize(stat.text)
                    if w[0] > width:
                        width = w[0]
                    height += STAT_HEIGHT
                last_sep = False
                continue

            elif stat.title == "Image":
                height += stat.text.size[1] + IMAGE_PADDING
                last_sep = False

            else:
                if last_sep:
                    height += SEPARATOR_SPACING
                else:
                    height += STAT_SPACING
                height += STAT_HEIGHT
                stat_text = f"{stat.title}{stat.text}"
                last_sep = False

            if stat.title != "Image":
                # FIXME: referenced before assignment
                w = self.font.getsize(stat_text)
            else:
                w = stat.text.size
            if w[0] > width:
                width = w[0]

        # 34 is the 17px padding from both sides
        return width + 34, height + self.namebar_trans.size[1] + 25

    def sort_stats(self, item):
        stats = list()
        separator = self.prop("Separator", None, None)
        if not isinstance(item, PassiveSkill):
            if 'weapon' in item.tags:
                stats.append(self.prop(item.item_class, '', DESC_COLOR))
                if item.quality:
                    stats.append(self.prop("Quality: ", f"+{item.quality}%", PROP_COLOR))
                if item.physical_damage:
                    stats.append(self.prop("Physical Damage: ", item.physical_damage, PROP_COLOR))

                elements = {
                    element.split('_')[0]: getattr(item, element) for element in [
                        'fire_damage', 'cold_damage', 'lightning_damage'
                    ] if getattr(item, element)
                }
                if elements:
                    stats.append(self.prop("Elemental Damage:", elements, None))

                if item.chaos_damage:
                    stats.append(self.prop("Chaos Damage: ", item.chaos_damage, CHAOS_COLOR))
                if item.critical_chance:
                    stats.append(self.prop("Critical Strike Chance: ", item.critical_chance, None))
                if item.attack_speed:
                    stats.append(self.prop("Attacks Per Second: ", item.attack_speed, PROP_COLOR))
                if int(item.range):
                    stats.append(self.prop("Weapon Range: ", item.range, None))

                stats.append(separator)

            elif 'armour' in item.tags:
                if item.quality:
                    stats.append(self.prop("Quality: ", f"+{item.quality}%", PROP_COLOR))
                if item.block:
                    stats.append(self.prop("Chance To Block: ", f"{item.block}%", PROP_COLOR))
                if item.armour:
                    stats.append(self.prop("Armour: ", item.armour, PROP_COLOR))
                if item.evasion:
                    stats.append(self.prop("Evasion: ", item.evasion, PROP_COLOR))
                if item.energy_shield:
                    stats.append(self.prop("Energy Shield: ", item.energy_shield, PROP_COLOR))
                stats.append(separator)

            elif 'ring' in item.tags or 'amulet' in item.tags or 'belt' in item.tags:
                if item.quality:
                    stats.append(self.prop("Quality: ", f"+{item.quality}%", PROP_COLOR))
                    stats.append(separator)

            elif 'gem' in item.tags:
                stats.append(self.prop(item.gem_tags.replace(',', ', '), '', DESC_COLOR))
                if item.stats_per_level[0]['mana multiplier']:
                    stats.append(self.prop("Mana Multiplier: ", f"{item.stats_per_level[0]['mana multiplier']}%", None))
                if item.radius:
                    stats.append(self.prop("Radius: ", item.radius, None))
                if not item.is_aura:
                    # Enlighten Enhance etc only go up to 10
                    try:
                        stats.append(self.prop(
                            "Mana Cost: ", f"({item.stats_per_level[1]['mana cost']}-{item.stats_per_level[20]['mana cost']})", PROP_COLOR)
                        )
                    except KeyError:
                        stats.append(self.prop(
                            "Mana Cost: ", f"({item.stats_per_level[1]['mana cost']}-{item.stats_per_level[10]['mana cost']})", PROP_COLOR)
                        )
                else:
                    stats.append(self.prop("Mana Reserved: ", f"{item.stats_per_level[0]['mana cost']}%", None))

                # Enlighten Enhance etc only go up to 10
                try:
                    if item.stats_per_level[20]['stored uses']:
                        stats.append(self.prop("Stored Uses", {item.stats_per_level[20]['stored uses']}, None))
                except KeyError:
                    if item.stats_per_level[10]['stored uses']:
                        stats.append(self.prop("Stored Uses", {item.stats_per_level[10]['stored uses']}, None))

                if item.stats_per_level[0]['cooldown']:
                    stats.append(self.prop("Cooldown Time: ", f"{item.stats_per_level[0]['cooldown']} sec", None))
                if item.cast_time:
                    stats.append(self.prop("Cast Time: ", f"{item.cast_time} sec", None))
                if item.stats_per_level[0]['critical strike chance']:
                    stats.append(
                        self.prop("Critical Strike Chance: ", f"{item.stats_per_level[0]['critical strike chance']}%", None)
                    )
                if item.stats_per_level[0]['damage effectiveness']:
                    stats.append(
                        self.prop("Damage Effectiveness: ", f"{item.stats_per_level[0]['damage effectiveness']}%", None)
                    )
                stats.append(separator)

            elif item.base == 'Prophecy':
                if len(item.lore.split(' ')) > 7:
                    lore = item.lore.split(' ')
                    sep_lore = [lore[x:x + 7] for x in range(0, len(lore), 7)]
                    for line in sep_lore:
                        stats.append(self.prop('Lore', ' '.join(line), UNIQUE_COLOR))
                else:
                    stats.append(self.prop('Lore', item.lore, UNIQUE_COLOR))
                stats.append(separator)

                obj_list, matches = unescape_to_list(item.objective, ret_matches=True)
                if 'while holding' in obj_list[0]:
                    item_name = matches[3].split('|')[1].strip(']]')
                    pre_holding = obj_list[0].split(' while holding ')[0]
                    new_obj = f"{pre_holding} while holding {item_name}"
                else:
                    new_obj = obj_list[0]

                if len(new_obj.split(' ')) > 7:
                    obj_split = new_obj.split(' ')
                    obj_sep = [obj_split[x:x + 7] for x in range(0, len(obj_split), 7)]
                    for line in obj_sep:
                        stats.append(self.prop(' '.join(line), '', None))
                else:
                    stats.append(self.prop(new_obj, '', None))
                stats.append(separator)
                stats.append(self.prop("Seal Cost: ", item.seal_cost, DESC_COLOR))

            if item.requirements.has_reqs and item.base != "Prophecy":
                reqs = {}
                if item.requirements.level:
                    reqs['level'] = item.requirements.level
                if item.requirements.str:
                    reqs['str'] = item.requirements.str
                if item.requirements.dex:
                    reqs['dex'] = item.requirements.dex
                if item.requirements.int:
                    reqs['int'] = item.requirements.int
                stats.append(self.prop("Requires", reqs, None))
                stats.append(separator)

            try:
                if item.enchant:
                    stats.append(self.prop(item.enchant, '', CRAFTED))
                    stats.append(separator)
            except AttributeError:
                pass

            if 'gem' in item.tags:
                if len(item.description.split(' ')) > 7:
                    desc = item.description.split(' ')
                    description = [desc[x:x + 7] for x in range(0, len(desc), 7)]
                    for line in description:
                        stats.append(self.prop(' '.join(line), '', GEM_COLOR))
                else:
                    stats.append(self.prop(item.description, '', GEM_COLOR))
                stats.append(separator)

                if item.quality_bonus:
                    stats.append(self.prop("Per 1% Quality:", "", DESC_COLOR))
                    if '&lt;br&gt;' in item.quality_bonus:
                        for bonus in item.quality_bonus.split('&lt;br&gt;'):
                            stats.append(self.prop(bonus, "", PROP_COLOR))
                    else:
                        stats.append(self.prop(item.quality_bonus, "", PROP_COLOR))
                    stats.append(separator)

                stat_text = item.stat_text.split("&lt;br&gt;")
                for stat in stat_text:
                    if len(stat.split(' ')) > 7:
                        st = stat.split(' ')
                        sep_stat = [st[x:x + 7] for x in range(0, len(st), 7)]
                        for sep in sep_stat:
                            stats.append(self.prop(' '.join(sep), "", PROP_COLOR))
                    else:
                        stats.append(self.prop(stat, "", PROP_COLOR))

                stats.append(separator)
                stats.append(self.prop("Gem Help", "Place into an item socket of the right", DESC_COLOR))
                stats.append(self.prop("Gem Help", "colour to gain this skill. Right click to", DESC_COLOR))
                stats.append(self.prop("Gem Help", "remove from a socket.", DESC_COLOR))

            if 'gem' not in item.tags and item.base != "Prophecy":
                if item.implicits:
                    implicits = unescape_to_list(item.implicits)
                else:
                    implicits = None
                if item.explicits:
                    explicits = unescape_to_list(item.explicits)
                else:
                    explicits = None

                if explicits and explicits[0].startswith('{'):
                    implicits = [explicits[0]]
                    explicits.pop(0)
                if implicits:
                    for implicit in implicits:
                        if "{crafted}" in implicit or "(enchant)" in implicit:
                            stats.append(self.prop(implicit.replace('{crafted}', '').replace('(enchant)', ''),
                                                   '', CRAFTED))
                            stats.append(separator)
                        else:
                            stats.append(self.prop(implicit.replace('(implicit)', ''), '', PROP_COLOR))

                    stats.append(separator)

                if explicits:
                    for explicit in explicits:
                        if explicit.lower() == "corrupted":
                            stats.append(self.prop(explicit, '', CORRUPTED))
                        elif "(crafted)" in explicit or "{crafted}" in explicit:
                            stats.append(self.prop(explicit.replace('{crafted}', '').replace(' (crafted)', ''),
                                                   '', CRAFTED))
                        else:
                            stats.append(self.prop(explicit, '', PROP_COLOR))

                if item.lore:
                    if stats[-1] is not separator:
                        stats.append(separator)
                    lore = self.prop('Lore', unescape_to_list(item.lore), UNIQUE_COLOR)
                    stats.append(lore)

            if item.icon:
                http = urllib3.PoolManager()

                def ico(icon):
                    r = http.request('GET', icon, preload_content=False)
                    im = Image.open(BytesIO(r.read()))
                    im = im.convert('RGBA')
                    return im

                try:
                    if item.skill_icon:
                        stats.append(self.prop('Image', ico(item.skill_icon), None))
                except AttributeError:
                    pass
                stats.append(self.prop('Image', ico(item.icon), None))

        else:
            if item.name:
                stats.append(self.prop('', item.name, DESC_COLOR))

            passive_type = None
            if item.asc_class:
                passive_type = f"{item.asc_class} Notable Passive Skill"
            elif item.is_notable:
                passive_type = "Notable Passive Skill"
            elif item.is_keystone:
                passive_type = "Keystone"
            stats.append(self.prop(passive_type, '', NORMAL_COLOR))

            for line in unescape_to_list(item.stat_text):
                stats.append(self.prop(line, '', PROP_COLOR))
            if item.icon:
                http = urllib3.PoolManager()

                def ico(icon):
                    r = http.request('GET', icon, preload_content=False)
                    im = Image.open(BytesIO(r.read()))
                    im = im.convert('RGBA')
                    return im

                try:
                    # FIXME: unresolved attribute
                    if item.skill_icon:
                        stats.append(self.prop('Image', ico(item.skill_icon), None))
                except AttributeError:
                    pass
                stats.append(self.prop('Image', ico(item.icon), None))

            if item.reminder_text:
                lines = unescape_to_list(item.reminder_text)
                for line in lines:
                    if len(line.split(' ')) > 7:
                        lore = line.split(' ')
                        sep_lore = [lore[x:x + 7] for x in range(0, len(lore), 7)]
                        for set_line in sep_lore:
                            stats.append(self.prop('Reminder', ' '.join(set_line), DESC_COLOR))
                    else:
                        stats.append(self.prop("Reminder", line, DESC_COLOR))

            if item.flavor_text:
                if len(item.flavor_text.split(' ')) > 7:
                    lore = item.flavor_text.split(' ')
                    sep_lore = [lore[x:x + 7] for x in range(0, len(lore), 7)]
                    for line in sep_lore:
                        stats.append(self.prop('Lore', ' '.join(line), UNIQUE_COLOR))
                else:
                    stats.append(self.prop("Lore", item.flavor_text, UNIQUE_COLOR))

        return stats

    def render_divcard(self, card):
        http = urllib3.PoolManager()
        r = http.request('GET', card.card_art, preload_content=False)
        art = Image.open(BytesIO(r.read()))
        art = art.convert('RGBA')
        item = Image.new('RGBA', self.div_frame.size, (255, 0, 0, 0))
        cur = Cursor(self.div_frame.size[0] // 2)
        cur.reset_x()
        cur.move_x((art.size[0] // 2) * -1)
        cur.move_y(47)
        item.alpha_composite(art, cur.pos)
        item.alpha_composite(self.div_frame, (0, 0))
        cur.reset_x()
        d = ImageDraw.Draw(item)
        cur.y = 0
        cur.move_y(20)
        header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        cur.move_x((header_font.getsize(card.name)[0] // 2) * -1)
        d.text(cur.pos, card.name, fill='black', font=header_font)
        cur.reset_x()
        cur.x = 77
        cur.y = 316
        cur.move_x((self.font.getsize(card.stack_size)[0] // 2) * -1)
        d.text(cur.pos, card.stack_size, fill=None, font=self.font)
        cur.y = 384
        cur.reset_x()
        fill = flavor_color[card.reward_flavor]
        cur.move_x((self.font.getsize(card.reward)[0] // 2) * -1)
        d.text(cur.pos, card.reward, fill=fill, font=self.font)
        cur.reset_x()
        if card.is_corrupted:
            cur.y = 384 + self.font.getsize(card.reward)[1] + 6
            cur.move_x((self.font.getsize("Corrupted")[0] // 2) * -1)
            d.text(cur.pos, "Corrupted", fill=CORRUPTED, font=self.font)
            cur.reset_x()
        cur.y = 536

        first_lore = unescape_to_list(card.lore)
        for first_line in first_lore:
            text = first_line
            if len(text.split(' ')) > 7:
                lore = text.split(' ')
                sep_lore = [lore[x:x + 7] for x in range(0, len(lore), 7)]
                for line in sep_lore:
                    joined_line = ' '.join(line)
                    cur.move_y(STAT_SPACING)
                    cur.move_x((self.font.getsize(joined_line)[0] // 2) * -1)
                    d.text(cur.pos, joined_line, fill=UNIQUE_COLOR, font=self.lore_font)
                    cur.move_y(self.lore_font.getsize(joined_line)[1])
                    cur.reset_x()

            else:
                cur.move_y(STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0] // 2) * -1)
                d.text(cur.pos, text, fill=UNIQUE_COLOR, font=self.lore_font)
                cur.move_y(self.lore_font.getsize(text)[1])
                cur.reset_x()
        return item

    def render(self, poe_item):
        stats = self.sort_stats(poe_item)
        fill = flavor_color[self.flavor]
        try:
            if self.header_font.getsize(poe_item.name) > self.header_font.getsize(poe_item.base):
                header = poe_item.name
            else:
                header = poe_item.base
        except (AttributeError, TypeError):
            header = poe_item.name

        box_size = self.calc_size(stats, header)
        center_x = box_size[0] // 2
        item = Image.new('RGBA', box_size, color='black')
        cur = Cursor(center_x)

        if not isinstance(poe_item, PassiveSkill):
            try:
                if poe_item.influences:
                    apply_influences = []
                    for influence in poe_item.influences:
                        if influence == "shaper":
                            apply_influences.append(self.shaper_badge)
                        elif influence == "elder":
                            apply_influences.append(self.elder_badge)
                        elif influence == "redeemer":
                            apply_influences.append(self.redeemer_badge)
                        elif influence == "crusader":
                            apply_influences.append(self.crusader_badge)
                        elif influence == "hunter":
                            apply_influences.append(self.hunter_badge)
                        elif influence == "warlord":
                            apply_influences.append(self.warlord_badge)

                    if poe_item.rarity.lower() in ['rare', 'unique', 'relic']:
                        self.namebar_left.alpha_composite(apply_influences[0], (8, 18))
                        if len(apply_influences) > 1:
                            self.namebar_right.alpha_composite(apply_influences[1], (9, 18))
                        else:
                            self.namebar_right.alpha_composite(apply_influences[0], (9, 18))
                    else:
                        self.namebar_left.alpha_composite(apply_influences[0], (4, 6))
                        if len(apply_influences) > 1:
                            self.namebar_right.alpha_composite(apply_influences[1], (1, 6))
                        else:
                            self.namebar_right.alpha_composite(apply_influences[0], (1, 6))
            except AttributeError:
                pass

            item.paste(self.namebar_left, cur.pos)
            cur.move_x(self.namebar_left.size[0])
            transformed_namebar = self.namebar_trans.resize((item.size[0] - (self.namebar_left.size[0] * 2),
                                                             self.namebar_trans.size[1]))
            item.paste(transformed_namebar, cur.pos)
            cur.move_x(transformed_namebar.size[0])
            item.paste(self.namebar_right, cur.pos)

        cur.reset_x()
        d = ImageDraw.Draw(item)
        cur.move_y(8)
        cur.move_x((self.header_font.getsize(poe_item.name)[0] // 2) * -1)
        d.text(cur.pos, poe_item.name, fill=fill, font=self.header_font)

        if not isinstance(poe_item, PassiveSkill):
            cur.move_y(2 + self.header_font.getsize(poe_item.name)[1])
        else:
            cur.move_y(self.header_font.getsize(poe_item.name)[1] // 2)
        cur.reset_x()

        if not isinstance(poe_item, PassiveSkill):
            if 'gem' not in poe_item.tags and poe_item.base != "Prophecy":
                if poe_item.base not in poe_item.name:
                    cur.move_x((self.header_font.getsize(poe_item.base)[0] // 2) * -1)
                    d.text(cur.pos, poe_item.base, fill=fill, font=self.header_font)
                    cur.reset_x()
            cur.y = 0
            # FIXME: referenced before assignment
            cur.move_y(transformed_namebar.size[1])
        else:
            pass

        for stat in stats:
            if stat.title == "Separator":
                self.last_action = "Separator"
                cur.move_x((self.separator.size[0] // 2) * -1)
                cur.move_y(SEPARATOR_SPACING + 2)
                item.paste(self.separator, cur.pos)
                cur.reset_x()

            elif stat.title == "Elemental Damage:":
                stat_text = stat.title
                for element in stat.text.keys():
                    stat_text += f" {stat.text[element]}"
                cur.move_x((self.font.getsize(stat_text)[0] // 2) * -1)
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize(stat.title)[0])
                for element in stat.text.keys():
                    d.text(cur.pos, f" {stat.text[element]}", fill=ELE_COLOR[element], font=self.font)
                    cur.move_x(self.font.getsize(f" {stat.text[element]}")[0])
                cur.move_y(STAT_HEIGHT)
                cur.reset_x()
                self.last_action = ""

            elif stat.title == "Requires":
                text = stat.title
                for attr in stat.text.keys():
                    text += f" {attr.title()} {stat.text[attr]}" \
                            f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                cur.move_y(0 if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0] // 2) * -1)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize(stat.title)[0])

                for attr in stat.text.keys():
                    if attr == 'level':
                        d.text(cur.pos, f" {attr.title()}", fill=DESC_COLOR, font=self.font)
                        cur.move_x(self.font.getsize(f" {attr.title()}")[0])
                        attribute_final = f" {stat.text[attr]}" \
                                          f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                        d.text(cur.pos, attribute_final, font=self.font)
                    else:
                        d.text(cur.pos, f" {stat.text[attr]}", font=self.font)
                        cur.move_x(self.font.getsize(f" {stat.text[attr]}")[0])
                        attribute_final = f" {attr.title()}{'' if list(stat.text.keys())[-1] == attr else ','}"
                        d.text(cur.pos, attribute_final, font=self.font, fill=DESC_COLOR)
                    cur.move_x(self.font.getsize(attribute_final)[0])
                cur.move_y(STAT_HEIGHT)
                cur.reset_x()
                self.last_action = ""

            elif stat.title == "Lore" or stat.title == "Reminder":
                if type(stat.text) is list:
                    for line in stat.text:
                        text = line
                        cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                        cur.move_x((self.font.getsize(text)[0] // 2) * -1)
                        d.text(cur.pos, text, fill=stat.color, font=self.lore_font)
                        cur.move_y(self.lore_font.getsize(text)[1])
                        cur.reset_x()
                        self.last_action = ""

                else:
                    cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                    cur.move_x((self.font.getsize(stat.text)[0] // 2) * -1)
                    d.text(cur.pos, stat.text, fill=stat.color, font=self.lore_font)
                    cur.move_y(STAT_HEIGHT)
                    cur.reset_x()

            elif stat.title == "Image" and not isinstance(poe_item, PassiveSkill):
                cur.move_x((stat.text.size[0] // 2) * -1)
                cur.move_y(4)
                ic = stat.text
                if not isinstance(poe_item, Gem) and 'shaper' in poe_item.influences:
                    ic = Image.alpha_composite(self.shaper_backgrounds[poe_item.size].resize(ic.size), ic)

                if not isinstance(poe_item, Gem) and 'elder' in poe_item.influences:
                    ic = Image.alpha_composite(self.elder_backgrounds[poe_item.size].resize(ic.size), ic)

                item.alpha_composite(ic, cur.pos)
                cur.move_y(stat.text.size[1])
                cur.reset_x()

            elif stat.title == "Image" and isinstance(poe_item, PassiveSkill):
                ic = stat.text
                if poe_item.asc_class:
                    frame = self.ascendancy_frame
                elif poe_item.is_keystone:
                    frame = self.keystone_frame
                elif poe_item.is_notable:
                    frame = self.notable_frame
                else:
                    frame = self.passive_frame

                icl = round(math.sqrt((frame.size[0] ** 2) / 2))
                old_s = ic.size[0]
                ic = ic.resize((icl, icl))
                cur.move_x((ic.size[0] // 2) * -1)
                cur.move_y(30)
                item.alpha_composite(ic, cur.pos)
                cur.move_y(((old_s + 26 - ic.size[0]) // 2) * -1)
                cur.reset_x()
                cur.move_x((frame.size[0] // 2) * -1)
                item.alpha_composite(frame, cur.pos)
                cur.move_y(frame.size[1])
                cur.reset_x()

            elif stat.title == "Stored Uses":
                text = f"Can Store {stat.text} Use(s)"
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0] // 2) * -1)
                d.text(cur.pos, "Can Store ", fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize("Can Store ")[0])
                d.text(cur.pos, stat.text + " ", font=self.font)
                cur.move_x(self.font.getsize(stat.text + " ")[0])
                d.text(cur.pos, "Use(s)", fill=DESC_COLOR, font=self.font)
                cur.reset_x()

            elif stat.title == "Gem Help":
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(stat.text)[0] // 2) * -1)
                d.text(cur.pos, stat.text, fill=DESC_COLOR, font=self.lore_font)
                cur.move_y(STAT_HEIGHT)
                cur.reset_x()

            elif stat.title == "Seal Cost: ":
                coin = Image.open(f'{_dir}//silver_coin.png').convert('RGBA')
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(stat.title)[0] // 2) * -1)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_y(STAT_HEIGHT + STAT_SPACING)
                cur.reset_x()
                sealtext = f"{stat.text}X   Silver Coin"
                cur.move_x((self.font.getsize(sealtext)[0] // 2) * -1)
                d.text(cur.pos, f"{stat.text}X ", fill=NORMAL_COLOR, font=self.font)
                cur.move_x(self.font.getsize(f"{stat.text}X ")[0])
                item.alpha_composite(coin, cur.pos)
                cur.move_x(coin.size[0] + 2)
                d.text(cur.pos, "Silver Coin", fill=NORMAL_COLOR, font=self.font)
                cur.move_y(STAT_HEIGHT)
                cur.reset_x()

            else:
                text = f"{stat.title}{stat.text}"
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0] // 2) * -1)

                if ':' in stat.title:
                    d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                    cur.move_x(self.font.getsize(stat.title)[0])
                    d.text(cur.pos, str(stat.text), fill=stat.color, font=self.font)
                else:
                    if stat.title.startswith('{'):
                        color = CRAFTED
                    else:
                        color = stat.color
                    d.text(cur.pos, stat.title, fill=color, font=self.font)

                cur.move_y(STAT_HEIGHT)
                cur.reset_x()
                self.last_action = ""

        item = ImageOps.expand(item, border=1, fill=fill)
        return item


def parse_game_item(itemtext):
    item = itemtext.split('\n')

    groups = []
    curr_group = []
    for line in item:
        if "---" in line:
            groups.append(curr_group)
            curr_group = []
        else:
            curr_group.append(line)
    groups.append(curr_group)

    pobitem = {'name': '', 'special': [], 'enchant': [],
               'implicit': [], 'stats': [], 'quality': 0, 'type': "game"}

    unmarked_blocks = 0

    print(item, groups)

    for group in groups:
        if group[0].startswith('Rarity:'):
            pobitem['rarity'] = group[0].split(' ')[1].title()
            pobitem['base'] = group[len(group)-1]

            if len(group) > 2:
                pobitem['name'] = group[1]

        # or group[0].startswith('Armour:') or group[0].startswith('Evasion Rating:') or group[0].startswith('Energy Shield:') or
        elif group[0].startswith('Quality') or group[0].startswith('Map Tier:'):
            for line in group:
                if line.startswith('Quality:'):
                    pobitem['quality'] = line.replace(
                        'Quality: +', '').replace('% (augmented)', '')
                elif line.startswith('Map Tier:') or line.startswith('Item Quantity:') or line.startswith('Item Rarity:'): # map stuff
                    pobitem['implicit'].append(line)
                elif line.startswith('Quality ('):  # catalysts
                    pobitem['implicit'].append(line)
        elif group[0].startswith('Requirements:'):
            pass
        elif group[0].startswith('Sockets:'):
            pass
        elif group[0].startswith('Item Level:'):
            pass
        elif group[0].startswith('Energy Shield:'):
            pass
        elif group[0].startswith('Armour:'):
            pass
        elif group[0].startswith('Evasion Rating:'):
            pass
        elif group[0].startswith('Chance to Block:'):
            pass
        elif group[0].startswith('Price:'):
            pass
        elif group[0].endswith('(enchant)'):
            for line in group:
                pobitem['enchant'].append(line.replace('(enchant)', ''))
        elif group[0].endswith('(implicit)'):
            for line in group:
                pobitem['implicit'].append(line.replace('(implicit)', ''))
        elif group[0].startswith('Corrupted'):
            # should corrupted be an explicit?
            pobitem['stats'].append('Corrupted')
        elif group[0].endswith(' Item'):
            for line in group:
                pobitem['special'].append(line)
        else:  # unid is an explicit
            # if (groups.index(group) < len(group)-1) or len(pobitem['stats']) == 0:
            if (unmarked_blocks == 0):
                unmarked_blocks += 1
                print("appending stats")
                for line in group:
                    print(line)
                    pobitem['stats'].append(line)
            else:  # flavor
                pass

    print(pobitem)

    return {
        'name': pobitem['name'], 'base': pobitem['base'], 'stats': pobitem['stats'], 'rarity': pobitem['rarity'],
        'implicits': pobitem['implicit'], 'quality': pobitem['quality'], 'special': pobitem['special'],
        'enchant': pobitem['enchant']
    }


def parse_pob_item(itemtext):
    if "Implicits: " not in itemtext:
        print("not in")
        return parse_game_item(itemtext)
    item = itemtext.split('\n')
    item = [line for line in item if "---" not in line]
    qualtext = 0
    variant = None
    pobitem = {'special': [], 'enchant': "", 'type': None}
    for index, line in enumerate(item):
        if "{variant:" in line:
            variant_now = line[line.index("t:") + 2:line.index("}")].split(',')
            if variant not in variant_now:
                item.pop(index)
                continue
            line = item[index] = line.split("}", 1)[1]

        if "{range:" in line:
            try:
                percent = float(line[line.index("e:") + 2:line.index("}")])
            except Exception:
                pass
            txt = line.split("}")[1]
            matches = re_range.findall(txt)

            for match in matches:
                stat = match[1:-1]
                if " to " in stat:
                    separator = stat.find(' to ', 1)
                    range_end = stat[separator + 4:]
                else:
                    separator = stat.find('-', 1)
                    range_end = stat[separator + 1:]
                range_start = stat[:separator]
                if '.' in range_start or '.' in range_end:
                    # FIXME: referenced before assignment
                    calc_stat = float(percent * float(range_end))
                else:
                    calc_stat = int(percent * float(range_end))
                txt = txt.replace(match, str(calc_stat))
            item[index] = txt

        if line.startswith("Rarity"):
            pobitem['rarity'] = line.split(' ')[1].title()
            pobitem['rarity_index'] = index
            continue

        elif line.startswith("Selected Variant"):
            variant = line.split(": ")[1]
            continue

        # elif line.startswith("Item Level"):
        #     pobitem['type'] = "game"
        #     if item[index + 3].startswith('--'):
        #         offset = 2
        #         if "(implicit)" not in item[index + offset]:
        #             pobitem['enchant'] = item[index + offset]
        #             offset = 4
        #         if "(implicit)" in item[index + offset]:
        #             pobitem['implicits'] = 0
        #             for line_inner in item[index + offset:]:
        #                 print(line_inner)
        #                 if "(implicit)" in line_inner:
        #                     pobitem['implicits'] = pobitem['implicits'] + 1
        #                 if "---" in line_inner:
        #                     break
        #             pobitem['statstart_index'] = index + offset + pobitem['implicits']
        #         else:
        #             pobitem['statstart_index'] = index + offset
        #     else:
        #         pobitem['statstart_index'] = index + 2

        elif line.startswith("====="):
            pobitem['statstart_index'] = index

        elif line.startswith("Implicits:") and 'implicits' not in pobitem:
            pobitem['type'] = 'pob'
            pobitem['implicits'] = int(line.split(': ')[1])
            pobitem['statstart_index'] = index + pobitem['implicits']

        elif "(enchant)" in line or "(implicit)" in line:
            if 'implicits' not in pobitem:
                pobitem['implicits'] = 1
            else:
                pobitem['implicits'] = pobitem['implicits'] + 1

            pobitem['statstart_index'] = index

        elif line.startswith("Requires"):
            pobitem['statstart_index'] = index

        elif line.startswith("Quality"):
            try:
                qualtext = line.split("+")[1].split(' ')[0].strip('%')
            except IndexError:
                pass

        if "Shaper Item" in line:
            pobitem['special'].append("Shaper Item")
        if "Elder Item" in line:
            pobitem['special'].append("Elder Item")
        if "Crusader Item" in line:
            pobitem['special'].append("Crusader Item")
        if "Redeemer Item" in line:
            pobitem['special'].append("Redeemer Item")
        if "Warlord Item" in line:
            pobitem['special'].append("Warlord Item")
        if "Hunter Item" in line:
            pobitem['special'].append("Hunter Item")

    if pobitem['rarity'].lower() in ['unique', 'rare', 'relic']:
        name = item[pobitem['rarity_index'] + 1]
        base = item[pobitem['rarity_index'] + 2]

    elif pobitem['rarity'].lower() == 'magic':
        name = item[pobitem['rarity_index'] + 1]
        if "Superior" in name:
            name = name.replace("Superior", "").strip()
        base = get_base_from_magic(name)

    else:
        name = item[pobitem['rarity_index'] + 1]
        if "Superior" in name:
            name = name.replace("Superior", "").strip()
        base = name

    if 'implicits' in pobitem and pobitem['implicits']:
        if pobitem['type'] == 'game':
            offset = 0
        else:
            offset = 1
        implicits = item[:pobitem['statstart_index'] + offset][-1 * pobitem['implicits']:]
        implicits = [implicit.replace('(implicit)', '') for implicit in implicits]

    elif item[pobitem['statstart_index'] - 2].startswith('--') and 'Item Level' not in item[pobitem['statstart_index'] - 1]:
        imp_end = "None"
        for ind, stat in enumerate(item[pobitem['statstart_index'] - 1:]):
            if stat.startswith('--'):
                if item[pobitem['statstart_index'] - 1:][ind + 1] not in ['Shaper Item', 'Elder Item']:
                    imp_end = ind - 1
                    break

        if imp_end != "None":
            implicits = item[pobitem['statstart_index'] - 1:][0:imp_end]
        else:
            implicits = []
    else:
        implicits = []

    stat_text = item[pobitem['statstart_index'] + 1:]
    stat_text = [stat for stat in stat_text if not stat.startswith('--')
                 and not ":" in stat and stat]
    if '(' in base and ')' in base:
        base = base[:base.find('(') - 1]
    if "Synthesised" in base:
        base = base.replace("Synthesised", "").strip()
    if "Synthesised" in name:
        name = name.replace("Synthesised", "").strip()
    print(implicits, stat_text)
    return {
        'name': name, 'base': base, 'stats': stat_text, 'rarity': pobitem['rarity'],
        'implicits': implicits, 'quality': int(qualtext), 'special': pobitem['special'],
        'enchant': pobitem['enchant']
    }


def ensure_rangeless(stat):
    if "-" in str(stat):
        return stat.split('-')[0][1:]
    return stat


def modify_base_stats(item):
    stats = {
        'flat es': 0, 'flat armour': 0, 'flat evasion': 0, 'inc es': int(item.quality),
        'inc armour': int(item.quality), 'inc evasion': int(item.quality), 'aspd': 0,
        'fire low': 0, 'fire max': 0, 'fire inc': 0, 'cold low': 0, 'cold max': 0,
        'cold inc': 0, 'light low': 0, 'light max': 0, 'light inc': 0, 'chaos low': 0,
        'chaos max': 0, 'chaos inc': 0, 'phys low': 0, 'phys max': 0, 'phys inc': int(item.quality),
        'cc': 0, 'range': 0, 'block': 0
    }

    if item.implicits:
        for stat in unescape_to_list(item.implicits):
            text = stat.lower().replace('{crafted}', '').replace('{fractured}', '')
            if not any(c.isdigit() for c in text) or 'minion' in text or 'global' in text:
                continue
            if ' per ' in text or ' if ' in text or ',' in text:
                continue
            if " to " in text and "multiplier" not in text and ":" not in text:
                if 'armour' in text and isinstance(item, Armour):
                    stats['flat armour'] += int(text.split(' ')[0][1:])
                elif 'evasion rating' in text and isinstance(item, Armour):
                    stats['flat evasion'] += int(text.split(' ')[0][1:])
                elif 'maximum energy shield' in text and isinstance(item, Armour):
                    stats['flat es'] += int(text.split(' ')[0][1:])
                elif 'weapon range' in text and isinstance(item, Weapon):
                    stats['range'] += int(text.split(' ')[0][1:])
                elif 'block' in text and 'spell damage' not in text and 'block recovery' not in text and \
                        "maximum" not in text:
                    stats['block'] += int(text.split(' ')[0][:-1])
                if "damage" in text and "reflect" not in text and "converted" not in text and isinstance(item, Weapon):
                    k = None
                    if 'lightning' in text:
                        k = 'light'
                    if 'cold' in text:
                        k = 'cold'
                    if 'fire' in text:
                        k = 'fire'
                    if 'chaos' in text:
                        k = 'chaos'
                    if 'physical' in text:
                        k = 'phys'
                    if k:
                        stats[f'{k} low'] += int(text.split(' to ')[0].split(' ')[-1])
                        stats[f'{k} max'] += int(text.split(' to ')[1].split(' ')[0])

            elif " increased " in text:
                if "armour" in text and isinstance(item, Armour):
                    stats['inc armour'] += int(text.split(' ')[0][:-1])
                if "evasion rating" in text and isinstance(item, Armour):
                    stats['inc evasion'] += int(text.split(' ')[0][:-1])
                if "energy shield" in text and isinstance(item, Armour):
                    stats['inc es'] += int(text.split(' ')[0][:-1])
                elif 'block' in text and 'block recovery' not in text and 'spell damage' not in text and \
                        "maximum" not in text:
                    stats['block'] += int(text.split(' ')[0][:-1])
                if "attack speed" in text and isinstance(item, Weapon):
                    stats['aspd'] += int(text.split(' ')[0][:-1])
                if "critical strike chance" in text and isinstance(item, Weapon):
                    stats['cc'] += int(text.split(' ')[0][:-1])
                if "damage" in text and isinstance(item, Weapon):
                    if 'lightning' in text:
                        stats['light inc'] += int(text.split(' ')[0][:-1])
                    if 'cold' in text:
                        stats['cold inc'] += int(text.split(' ')[0][:-1])
                    if 'fire' in text:
                        stats['fire inc'] += int(text.split(' ')[0][:-1])
                    if 'chaos' in text:
                        stats['chaos inc'] += int(text.split(' ')[0][:-1])
                    if 'physical' in text:
                        stats['phys inc'] += int(text.split(' ')[0][:-1])

    if item.explicits:
        for stat in unescape_to_list(item.explicits):
            text = stat.lower().replace('{crafted}', '').replace('{fractured}', '')
            if not any(c.isdigit() for c in text) or 'minion' in text or 'global' in text:
                continue
            if ' per ' in text or ' if ' in text or ',' in text:
                continue
            if " to " in text and "multiplier" not in text and ":" not in text:
                if 'armour' in text and isinstance(item, Armour):
                    stats['flat armour'] += int(text.split(' ')[0][1:])
                elif 'evasion rating' in text and isinstance(item, Armour):
                    stats['flat evasion'] += int(text.split(' ')[0][1:])
                elif 'maximum energy shield' in text and isinstance(item, Armour):
                    stats['flat es'] += int(text.split(' ')[0][1:])
                elif 'weapon range' in text and isinstance(item, Weapon):
                    stats['range'] += int(text.split(' ')[0][1:])
                elif 'block' in text and 'block recovery' not in text and 'spell damage' not in text \
                        and "maximum" not in text:
                    stats['block'] += int(text.split(' ')[0][:-1])
                if "damage" in text and "reflect" not in text and "converted" not in text and isinstance(item, Weapon):
                    k = None
                    if 'lightning' in text:
                        k = 'light'
                    if 'cold' in text:
                        k = 'cold'
                    if 'fire' in text:
                        k = 'fire'
                    if 'chaos' in text:
                        k = 'chaos'
                    if 'physical' in text:
                        k = 'phys'
                    if k:
                        stats[f'{k} low'] += int(text.split(' to ')[0].split(' ')[-1])
                        stats[f'{k} max'] += int(text.split(' to ')[1].split(' ')[0])

            elif " increased " in text:
                if "armour" in text and isinstance(item, Armour):
                    stats['inc armour'] += int(text.split(' ')[0][:-1])
                if "evasion rating" in text and isinstance(item, Armour):
                    stats['inc evasion'] += int(text.split(' ')[0][:-1])
                if "energy shield" in text and isinstance(item, Armour):
                    stats['inc es'] += int(text.split(' ')[0][:-1])
                elif 'block' in text and 'block recovery' not in text and 'spell damage' not in text:
                    stats['block'] += int(text.split(' ')[0][:-1])
                if "attack speed" in text and isinstance(item, Weapon):
                    stats['aspd'] += int(text.split(' ')[0][:-1])
                if "critical strike chance" in text and isinstance(item, Weapon):
                    stats['cc'] += int(text.split(' ')[0][:-1])
                if "damage" in text and isinstance(item, Weapon):
                    if 'lightning' in text:
                        stats['light inc'] += int(text.split(' ')[0][:-1])
                    if 'cold' in text:
                        stats['cold inc'] += int(text.split(' ')[0][:-1])
                    if 'fire' in text:
                        stats['fire inc'] += int(text.split(' ')[0][:-1])
                    if 'chaos' in text:
                        stats['chaos inc'] += int(text.split(' ')[0][:-1])
                    if 'physical' in text:
                        stats['phys inc'] += int(text.split(' ')[0][:-1])

    if 'weapon' in item.tags:
        if stats['aspd']:
            _as = float(ensure_rangeless(item.attack_speed))
            item.attack_speed = f"{(_as + (stats['aspd'] / 100) * _as):.2}"

        if stats['cc']:
            cc = 5.0
            cc += cc * (stats['cc'] / 100)
            item.critical_chance = f"{cc:.2}%"

        if stats['range']:
            i_range = int(ensure_rangeless(item.range))
            i_range += stats['range']
            item.range = f"{i_range}"

        if stats['fire max'] or stats['fire inc']:
            if stats['fire max']:
                item.fire_min = stats['fire low']
                item.fire_max = stats['fire max']
            fire_m = int(ensure_rangeless(item.fire_min))
            fire_mx = int(ensure_rangeless(item.fire_max))
            fire_m += fire_m * (stats['fire inc'] / 100)
            fire_mx += fire_mx * (stats['fire inc'] / 100)
            item.fire_min = str(round(fire_m))
            item.fire_max = str(round(fire_mx))

        if stats['cold max'] or stats['cold inc']:
            if stats['cold max']:
                item.cold_min = stats['cold low']
                item.cold_max = stats['cold max']
            cold_m = int(ensure_rangeless(item.cold_min))
            cold_mx = int(ensure_rangeless(item.cold_max))
            cold_m += cold_m * (stats['cold inc'] / 100)
            cold_mx += cold_mx * (stats['cold inc'] / 100)
            item.cold_min = str(round(cold_m))
            item.cold_max = str(round(cold_mx))

        if stats['light max'] or stats['light inc']:
            if stats['light max']:
                item.lightning_min = stats['light low']
                item.lightning_max = stats['light max']
            lightning_m = int(ensure_rangeless(item.lightning_min))
            lightning_mx = int(ensure_rangeless(item.lightning_max))
            lightning_m += lightning_m * (stats['light inc'] / 100)
            lightning_mx += lightning_mx * (stats['light inc'] / 100)
            item.lightning_min = str(round(lightning_m))
            item.lightning_max = str(round(lightning_mx))

        if stats['chaos max'] or stats['chaos inc']:
            if stats['chaos max']:
                item.chaos_min = stats['chaos low']
                item.chaos_max = stats['chaos max']
            chaos_m = int(ensure_rangeless(item.chaos_min))
            chaos_mx = int(ensure_rangeless(item.chaos_max))
            chaos_m += chaos_m * (stats['chaos inc'] / 100)
            chaos_mx += chaos_mx * (stats['chaos inc'] / 100)
            item.chaos_min = str(round(chaos_m))
            item.chaos_max = str(round(chaos_mx))

        if stats['phys max'] or stats['phys inc']:
            physical_m = int(ensure_rangeless(item.physical_min)) + stats['phys low']
            physical_mx = int(ensure_rangeless(item.physical_max)) + stats['phys max']
            physical_m += physical_m * (stats['phys inc'] / 100)
            physical_mx += physical_mx * (stats['phys inc'] / 100)
            item.physical_min = str(round(physical_m))
            item.physical_max = str(round(physical_mx))

    else:
        try:
            if item.armour:
                arm = int(ensure_rangeless(item.armour))
                arm += stats['flat armour']
                arm += (stats['inc armour'] / 100) * arm
                item.armour = str(round(arm))
        except Exception:
            return

        if item.evasion:
            ev = int(ensure_rangeless(item.evasion))
            ev += stats['flat evasion']
            ev += (stats['inc evasion'] / 100) * ev
            item.evasion = str(round(ev))

        if item.energy_shield:
            es = int(ensure_rangeless(item.energy_shield))
            es += stats['flat es']
            es += (stats['inc es'] / 100) * es
            item.energy_shield = str(round(es))

        if "shield" in item.tags:
            block = int(ensure_rangeless(item.block))
            block += stats['block']
            item.block = str(round(block))


def _get_wiki_base(item, object_dict, cl, slot, char_api=False, thread_exc_queue=None):
    try:
        assert item['rarity'].lower()
    except Exception:
        pass

    if item['rarity'].lower() in ['unique', 'relic'] and char_api:
        try:
            wiki_base = cl.find_items({'name': item['name']})[0]
        except IndexError:
            ex = AbsentItemBaseException(f"Could not find {item['name']}")
            if thread_exc_queue:
                thread_exc_queue.put(ex)
            return
        if not wiki_base:
            pass

        if isinstance(wiki_base, Weapon):
            wiki_base.attack_speed = item.get('attack_speed', 0)
            wiki_base.chaos_min = item.get('chaos_min', 0)
            wiki_base.chaos_max = item.get('chaos_max', 0)
            wiki_base.cold_min = item.get('cold_min', 0)
            wiki_base.cold_max = item.get('cold_max', 0)
            wiki_base.fire_min = item.get('fire_min', 0)
            wiki_base.fire_max = item.get('fire_max', 0)
            wiki_base.lightning_min = item.get('lightning_min', 0)
            wiki_base.lightning_max = item.get('lightning_max', 0)
            wiki_base.physical_min = item.get('physical_min', 0)
            wiki_base.physical_max = item.get('physical_max', 0)
            wiki_base.range = item.get('range', 0)
            wiki_base.critical_chance = item.get('critical_chance', 0)

        elif isinstance(wiki_base, Armour):
            wiki_base.armour = item.get('armour', 0)
            wiki_base.evasion = item.get('evasion', 0)
            wiki_base.energy_shield = item.get('energy_shield', 0)

        if item['rarity'].lower() == 'relic':
            wiki_base.rarity = 'relic'

    elif item['rarity'].lower() in ['unique', 'relic']:
        real_base = cl.find_items({'name': item['base']})[0]
        try:
            wiki_base = cl.find_items({'name': item['name']})[0]
        except IndexError:
            wiki_base = real_base
            wiki_base.implicits = item['implicits']
            wiki_base.explicits = item['stats']
            wiki_base.name = item['name']
            wiki_base.base = item['base']
            wiki_base.rarity = item['rarity']

        if isinstance(wiki_base, Weapon):
            wiki_base.attack_speed = real_base.attack_speed
            wiki_base.chaos_min = real_base.chaos_min
            wiki_base.chaos_max = real_base.chaos_max
            wiki_base.cold_min = real_base.cold_min
            wiki_base.cold_max = real_base.cold_max
            wiki_base.fire_min = real_base.fire_min
            wiki_base.fire_max = real_base.fire_max
            wiki_base.lightning_min = real_base.lightning_min
            wiki_base.lightning_max = real_base.lightning_max
            if real_base.physical_min > wiki_base.physical_min:
                wiki_base.physical_min = real_base.physical_min
            if real_base.physical_max > wiki_base.physical_max:
                wiki_base.physical_max = real_base.physical_max
            wiki_base.range = real_base.range
            wiki_base.critical_chance = real_base.critical_chance

        elif isinstance(wiki_base, Armour):
            wiki_base.armour = real_base.armour
            wiki_base.evasion = real_base.evasion
            wiki_base.energy_shield = real_base.energy_shield

        if item['rarity'].lower() == 'relic':
            wiki_base.rarity = 'relic'

    elif "Flask" in item['base']:
        return
    else:
        if item['rarity'].lower() == 'magic' and item['name'] == item['base']:
            if '' in item['stats']:
                item['stats'].remove('')
                item['base'] = get_base_from_magic(item['base'])
        wl = []

        for w in item['base'].split(' '):
            if not any(char.isdigit() for char in w):
                wl.append(w)
        try:
            wiki_base = cl.find_items({'name': ' '.join(wl).replace("Synthesised", "").strip()})[0]
        except IndexError:
            ex = AbsentItemBaseException(f"Could not find {item['name']}")
            if thread_exc_queue:
                thread_exc_queue.put(ex)
            return

        wiki_base.rarity = item['rarity']
        wiki_base.name = item['name']
        wiki_base.base = item['base']

    if char_api:
        if item['implicits']:
            wiki_base.implicits = '&lt;br&gt;'.join(item['implicits'])
        if item['explicits']:
            wiki_base.explicits = '&lt;br&gt;'.join(item['explicits'])

    else:
        try:
            pass
        except Exception:
            pass
        if item['implicits']:
            wiki_base.implicits = '<br>'.join(item['implicits'])
        if item['stats']:
            wiki_base.explicits = '&lt;br&gt;'.join(item['stats'])
        if item['enchant']:
            wiki_base.enchant = item['enchant']
    wiki_base.quality = item['quality']

    if wiki_base.rarity.lower() not in ['unique', 'relic'] and char_api or char_api is False:
        if wiki_base.quality == '' or "ring" in wiki_base.tags or "amulet" in wiki_base.tags \
                or "belt" in wiki_base.tags or "quiver" in wiki_base.tags or "flask" in wiki_base.tags \
                or "jewel" in wiki_base.tags:
            pass
        else:
            modify_base_stats(wiki_base)

    if item['special']:
        for influence in item['special']:
            if influence == "Shaper Item":
                wiki_base.influences.append("shaper")
            elif influence == "Elder Item":
                wiki_base.influences.append("elder")
            elif influence == "Redeemer Item":
                wiki_base.influences.append("redeemer")
            elif influence == "Crusader Item":
                wiki_base.influences.append("crusader")
            elif influence == "Warlord Item":
                wiki_base.influences.append("warlord")
            elif influence == "Hunter Item":
                wiki_base.influences.append("hunter")

    object_dict[slot] = wiki_base


def parse_pob_xml(xml: str, cl=None):
    tree = Etree.ElementTree(Etree.fromstring(xml))
    equipped = {}
    slots = tree.findall('Items/Slot')
    for slot in slots:
        if 'socket' in slot.attrib['name'].lower():
            continue
        equipped[slot.attrib['name']] = {}
        equipped[slot.attrib['name']]['id'] = slot.attrib['itemId']

    if cl:
        obj_dict = {}
        threads = []
        exc_queue = Queue()
        for slot in equipped:
            item_id = equipped[slot]['id']
            tree_item = tree.find(f'Items/Item[@id="{item_id}"]')
            if 'variant' in tree_item.attrib:
                lines = tree_item.text.replace('\t', '').split('\n')
                for line in lines[:]:
                    if line.startswith('{variant'):
                        variant = line.split('variant:')[1][0]
                        if variant != tree_item.attrib['variant']:
                            lines.remove(line)
                tree_item.text = '\n'.join(lines)
            equipped[slot]['raw'] = tree_item.text.replace('\t', '')
            try:
                equipped[slot]['parsed'] = parse_pob_item(equipped[slot]['raw'])
            except Exception:
                continue

            item = equipped[slot]['parsed']
            t = threading.Thread(target=_get_wiki_base, args=(item, obj_dict, cl, slot))
            threads.append(t)
            t.start()

        for thread in threads:
            thread.join()

        if not exc_queue.empty():
            raise exc_queue.get()

        for slot in obj_dict:
            equipped[slot]['object'] = obj_dict[slot]

    skill_slots = tree.findall('Skills/Skill')
    for skill in skill_slots:
        if 'slot' in skill.attrib:
            slot = skill.attrib['slot']
            if slot in equipped:
                equipped[slot]['gems'] = []
                lst = equipped[slot]['gems']
            else:
                continue

        else:
            if 'gem_groups' not in equipped:
                equipped['gem_groups'] = {}
            try:
                if not skill.getchildren()[0].attrib['nameSpec'] in equipped['gem_groups']:
                    equipped['gem_groups'][skill.getchildren()[0].attrib['nameSpec']] = []
            except Exception:
                continue
            lst = equipped['gem_groups'][skill.getchildren()[0].attrib['nameSpec']]

        gems = skill.getchildren()
        for gem in gems:
            gem_d = {
                'name': gem.attrib['nameSpec'],
                'level': gem.attrib['level'],
                'enabled': gem.attrib['enabled'],
                'quality': gem.attrib['quality']
            }
            lst.append(gem_d)

    stats = {}
    active_spec = int(tree.find('Tree').attrib['activeSpec']) - 1
    current_tree = tree.findall('Tree/Spec')[active_spec]
    tree_base64 = current_tree.find('URL').text.replace('\t', '').replace('\n', '').rsplit('/', 1)[1]
    byte_tree = binascii.a2b_base64(tree_base64.replace('-', '+').replace('_', '/'))
    pos = 7
    total_nodes = (len(byte_tree) - 7) // 2
    nodes = []

    for _ in range(total_nodes):
        nodes.append(str(int.from_bytes(byte_tree[pos:pos + 2], byteorder='big')))
        pos += 2
    stats['keystones'] = []
    stats['asc_nodes'] = []

    for node in nodes:
        if node in keystones:
            stats['keystones'].append(keystones[node])
        if node in asc_nodes:
            stats['asc_nodes'].append(asc_nodes[node])

    stats['trees'] = {}
    for spec in tree.findall('Tree/Spec'):
        name = spec.attrib['title'] if 'title' in spec.attrib else 'Default'
        stats['trees'][name] = spec.find('URL').text.replace('\t', '').replace('\n', '').replace('/passive', '/fullscreen-passive')
    stats['jewels'] = []
    jewel_sockets = current_tree.findall('Sockets/Socket')
    for socket in jewel_sockets:
        if socket.attrib['itemId'] != "0":
            item_id = socket.attrib['itemId']
            parsed = parse_pob_item(tree.find(f'Items/Item[@id="{item_id}"]').text.replace('\t', ''))
            stats['jewels'].append(parsed)

    stats['equipped'] = equipped
    try:
        stats['bandit'] = tree.find('Build').attrib['bandit']
    except Exception:
        stats['bandit'] = "None"

    try:
        stats['class'] = tree.find('Build').attrib.get('className', "None")
        stats['ascendancy'] = tree.find('Build').attrib.get('ascendClassName', "None")
        try:
            stats['total_dps'] = tree.find('Build/PlayerStat[@stat="CombinedDPS"]').attrib['value']
        except Exception:
            stats['total_dps'] = tree.find('Build/PlayerStat[@stat="TotalDPS"]').attrib['value']

        stats['level'] = tree.find('Build').attrib['level']
        try:
            main_group = int(tree.find('Build').attrib.get('mainSocketGroup', 1))
            skill_in_group = int(skill_slots[main_group - 1].attrib.get('mainActiveSkill', 1))
            stats['main_skill'] = skill_slots[main_group - 1].getchildren()[skill_in_group - 1].attrib['nameSpec']
        except Exception:
            stats['main_skill'] = " "

        stats['crit_chance'] = tree.find('Build/PlayerStat[@stat="PreEffectiveCritChance"]').attrib['value']
        stats['effective_crit_chance'] = tree.find('Build/PlayerStat[@stat="CritChance"]').attrib['value']
        stats['chance_to_hit'] = tree.find('Build/PlayerStat[@stat="HitChance"]').attrib['value']
        stats['str'] = tree.find('Build/PlayerStat[@stat="Str"]').attrib['value']
        stats['dex'] = tree.find('Build/PlayerStat[@stat="Dex"]').attrib['value']
        stats['int'] = tree.find('Build/PlayerStat[@stat="Int"]').attrib['value']
        stats['life'] = tree.find('Build/PlayerStat[@stat="Life"]').attrib['value']
        stats['life_regen'] = tree.find('Build/PlayerStat[@stat="LifeRegen"]').attrib['value']
        stats['es'] = tree.find('Build/PlayerStat[@stat="EnergyShield"]').attrib['value']
        stats['es_regen'] = tree.find('Build/PlayerStat[@stat="EnergyShieldRegen"]').attrib['value']
        try:
            stats['degen'] = tree.find('Build/PlayerStat[@stat="TotalDegen"]').attrib['value']
        except AttributeError:
            stats['degen'] = "0"

        stats['evasion'] = tree.find('Build/PlayerStat[@stat="Evasion"]').attrib['value']
        stats['block'] = tree.find('Build/PlayerStat[@stat="BlockChance"]').attrib['value']
        stats['spell_block'] = tree.find('Build/PlayerStat[@stat="SpellBlockChance"]').attrib['value']
        stats['dodge'] = tree.find('Build/PlayerStat[@stat="AttackDodgeChance"]').attrib['value']
        stats['spell_dodge'] = tree.find('Build/PlayerStat[@stat="SpellDodgeChance"]').attrib['value']
        stats['fire_res'] = tree.find('Build/PlayerStat[@stat="FireResist"]').attrib['value']
        stats['cold_res'] = tree.find('Build/PlayerStat[@stat="ColdResist"]').attrib['value']
        stats['light_res'] = tree.find('Build/PlayerStat[@stat="LightningResist"]').attrib['value']
        stats['chaos_res'] = tree.find('Build/PlayerStat[@stat="ChaosResist"]').attrib['value']
        try:
            stats['power_charges'] = tree.find('Build/PlayerStat[@stat="PowerChargesMax"]').attrib['value']
        except Exception:
            stats['power_charges'] = '3'
        try:
            stats['frenzy_charges'] = tree.find('Build/PlayerStat[@stat="FrenzyChargesMax"]').attrib['value']
        except Exception:
            stats['frenzy_charges'] = '3'
        try:
            stats['endurance_charges'] = tree.find('Build/PlayerStat[@stat="EnduranceChargesMax"]').attrib['value']
        except Exception:
            stats['endurance_charges'] = '3'

    except AttributeError:
        raise OutdatedPoBException()

    return stats


def parse_poe_char_api(json, cl, items_only=False):
    rarity = {
        0: "Normal",
        1: "Magic",
        2: "Rare",
        3: "Unique",
        4: "Gem"
    }
    equipped = {}
    threads = []
    obj_dict = {}
    for item in json['items']:
        # TODO: Find a more idiomatic way to do this
        #   As it is now, this dict should only ever contain values of type `int`
        char_item = defaultdict(int)

        if items_only and 'Prophecy' in item['icon'] or 'Divination' in item['icon']:
            equipped['Item'] = item
            continue

        char_item['rarity'] = rarity[item['frameType']]
        char_item['name'] = item["name"].split('>>')[-1]
        if 'properties' in item:
            for prop in item['properties']:
                if prop['name'] == "Quality":
                    char_item['quality'] = int(prop['values'][0][0][1:-1])

                # Weapon stats
                if prop['name'] == "Physical Damage":
                    char_item['physical_min'] = prop['values'][0][0].split('-')[0]
                    char_item['physical_max'] = prop['values'][0][0].split('-')[1]
                if prop['name'] == "Fire Damage":
                    char_item['fire_min'] = prop['values'][0][0].split('-')[0]
                    char_item['fire_max'] = prop['values'][0][0].split('-')[1]
                if prop['name'] == "Cold Damage":
                    char_item['cold_min'] = prop['values'][0][0].split('-')[0]
                    char_item['cold_max'] = prop['values'][0][0].split('-')[1]
                if prop['name'] == "Lightning Damage":
                    char_item['lightning_min'] = prop['values'][0][0].split('-')[0]
                    char_item['lightning_max'] = prop['values'][0][0].split('-')[1]
                if prop['name'] == "Chaos Damage":
                    char_item['chaos_min'] = prop['values'][0][0].split('-')[0]
                    char_item['chaos_max'] = prop['values'][0][0].split('-')[1]
                if prop['name'] == "Critical Strike Chance":
                    char_item['critical_chance'] = prop['values'][0][0]
                if prop['name'] == "Attacks per Second":
                    char_item['attack_speed'] = prop['values'][0][0]
                if prop['name'] == "Weapon Range":
                    char_item['range'] = prop['values'][0][0]

                # Armour Stats
                if prop['name'] == "Armour":
                    char_item['armour'] = prop['values'][0][0]
                if prop['name'] == "Energy Shield":
                    char_item['energy_shield'] = prop['values'][0][0]
                if prop['name'] == "Evasion":
                    char_item['evasion'] = prop['values'][0][0]

        if char_item['name'] == '':
            char_item['name'] = item["typeLine"]
        if char_item['rarity'] == "Magic":
            char_item['base'] = get_base_from_magic(item['typeLine'])
        else:
            char_item['base'] = item["typeLine"]

        if items_only:
            slot = "Item"
        elif 'Ring' in item['inventoryId']:
            slot = "Ring 2" if "2" in item['inventoryId'] else "Ring 1"
        elif item['inventoryId'] == "Offhand":
            slot = "Weapon 2"
        elif item['inventoryId'] == "Weapon":
            slot = "Weapon 1"
        elif item['inventoryId'] == "Helm":
            slot = "Helmet"
        elif item['inventoryId'] == "BodyArmour":
            slot = "Body Armour"
        elif item['inventoryId'] == "Flask":
            slot = f"Flask {int(item['x']) + 1}"
            char_item['name'] = item["typeLine"].split('>>')[-1]
            if item['frameType'] == 1 and 'Flask of' in char_item['name']:
                char_item['rarity'] = "Magic"
        elif item['inventoryId'] in ['Amulet', 'Helm', 'Gloves', 'Belt', 'Flask', 'Boots', 'Weapon', 'PassiveJewels']:
            slot = item['inventoryId']
        else:
            continue

        if 'implicitMods' in item:
            char_item['implicits'] = item['implicitMods']
        else:
            char_item['implicits'] = []

        if 'explicitMods' in item:
            char_item['explicits'] = item['explicitMods']
        else:
            char_item['explicits'] = []

        if 'craftedMods' in item:
            for mod in item['craftedMods']:
                # FIXME: unresolved attribute
                char_item['explicits'].append("{crafted}"f"{mod}")
        if 'corrupted' in item:
            # FIXME: unresolved attribute
            char_item['explicits'].append('Corrupted')
        if 'enchantMods' in item:
            char_item['implicits'] = ["{crafted}" + item['enchantMods'][0]]

        equipped[slot] = {}
        if slot == 'PassiveJewels' or items_only:
            if type(equipped[slot]) is dict:
                equipped[slot] = []
            equipped[slot].append(char_item)
        else:
            equipped[slot] = char_item

        if 'socketedItems' in item and not items_only:
            equipped[slot]['gems'] = []
            for socketed in item['socketedItems']:
                if socketed['frameType'] == 4:
                    gem_d = {'name': socketed['typeLine']}
                    for prop in socketed['properties']:
                        if prop['name'] == 'Quality':
                            gem_d['quality'] = prop['values'][0][0].replace('+', '').replace('%', '')
                        if prop['name'] == 'Level':
                            gem_d['level'] = prop['values'][0][0]
                    if 'quality' not in gem_d:
                        gem_d['quality'] = 0
                    equipped[slot]['gems'].append(gem_d)

        if slot != 'PassiveJewels' and 'Flask' not in slot:
            t = threading.Thread(target=_get_wiki_base, args=(char_item, obj_dict, cl, slot, True))
            threads.append(t)
            t.start()

    for thread in threads:
        thread.join()
    if items_only:
        equipped["items_objects"] = []
    for slot in obj_dict:
        if not items_only:
            equipped[slot]['object'] = obj_dict[slot]
        else:
            equipped["items_objects"] = obj_dict[slot]

    stats = {'equipped': equipped}
    if 'character' in json:
        stats['level'] = json['character']['level']
        stats['ascendancy'] = json['character']['ascendancyClass']
        stats['class'] = json['character']['class']
        stats['charname'] = json['character']['name']
        stats['league'] = json['character']['league']
    return stats


def get_base_from_magic(name: str):
    return ' '.join(name.split("of")[0].split("'")[-1].split()[1:])


def poe_skill_tree(hashes, asc: str = "None", return_keystones=False, return_asc=False):
    char = {
        "marauder": 1,
        "ranger": 2,
        "witch": 3,
        "duelist": 4,
        "templar": 5,
        "shadow": 6,
        "scion": 7
    }
    ascendancy_bytes = {
        "marauder": {
            "none": 0,
            "juggernaut": 1,
            "berserker": 2,
            "chieftain": 3
        },
        "ranger": {
            "none": 0,
            "raider": 1,
            "deadeye": 2,
            "pathfinder": 3
        },
        "witch": {
            "none": 0,
            "occultist": 1,
            "elementalist": 2,
            "necromancer": 3
        },
        "duelist": {
            "none": 0,
            "slayer": 1,
            "gladiator": 2,
            "champion": 3
        },
        "templar": {
            "none": 0,
            "inquisitor": 1,
            "hierophant": 2,
            "guardian": 3
        },
        "shadow": {
            "none": 0,
            "assassin": 1,
            "trickster": 2,
            "saboteur": 3
        },
        "scion": {
            "none": 0,
            "ascendant": 1
        }
    }

    # This took me a real assload of time to figure out
    # Either the 4th only or the first 4 bytes represent tree/b64 format version on poe side
    # 5th and 6th byte are character class and ascendancy respectively
    # Not sure if 7th byte should inherently be 0, but I think its related to start/exit nodes
    ba = bytearray([0, 0, 0, 4])
    char_class = None
    asc = asc.lower()
    for a_char in ascendancy_bytes:
        if asc in ascendancy_bytes[a_char]:
            char_class = a_char
            break
    if not char_class:
        char_class = asc
        asc = "none"

    ba += bytes([char[char_class]])
    ba += bytes([ascendancy_bytes[char_class][asc.lower()]])
    ba += bytes([0])
    for hash_obj in hashes:
        ba += hash_obj.to_bytes(2, 'big')

    post = binascii.b2a_base64(ba).decode().replace('+', '-').replace('/', '_')
    tree_keystones = []
    ascendancy = []
    for hash_obj in hashes:
        if str(hash_obj) in keystones:
            tree_keystones.append(keystones[str(hash_obj)])
        if str(hash_obj) in asc_nodes:
            ascendancy.append(asc_nodes[str(hash_obj)])

    if return_keystones and return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", tree_keystones, ascendancy
    elif return_keystones and not return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", tree_keystones
    elif return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", ascendancy

    return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}"


def get_active_leagues():
    http = urllib3.PoolManager()
    resp = http.request('GET', 'https://www.pathofexile.com/api/trade/data/leagues')
    if resp.status != 200:
        raise RequestException(resp.data.decode('utf-8'))

    leagues = js.loads(resp.data.decode('utf-8'))

    return leagues['result']


def _trade_api_query(data, league, endpoint):
    http = urllib3.PoolManager()
    print(js.dumps(data).encode('utf-8'))
    resp = http.request(
        'POST', f'https://www.pathofexile.com/api/trade/{endpoint}/{league}',
        body=js.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'}
    )

    if resp.status != 200:
        raise RequestException(resp.data.decode('utf-8'))

    json_result = js.loads(resp.data.decode('utf-8'))
    listing_ids = json_result['result']

    entries = http.request('GET', f'https://www.pathofexile.com/api/trade/fetch/{",".join(listing_ids[:10])}')
    if entries.status != 200:
        raise RequestException(entries.data.decode('utf-8'))

    return js.loads(entries.data.decode('utf-8'))['result']


def currency_rates(have: str, want: str, league: str):
    data = {
        "exchange": {
            "status": {
                "option": "online"
            },
            "have": [have],
            "want": [want]
        }
    }
    listings = _trade_api_query(data, league, 'exchange')
    return CurrencyQuery(have, want, league, listings)


def item_price(item, league):
    data = {
        "query": {
            "term": item,
            "status": {
                "option": "online"
            }
        },
        "sort": {
            "price": "asc"
        },
    }
    listings = _trade_api_query(data, league, 'search')
    return ItemPriceQuery(item, league, listings)
