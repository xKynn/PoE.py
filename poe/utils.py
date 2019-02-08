import binascii
import html
import json as js
import os
import re
import threading
import xml.etree.cElementTree as ET
from collections import namedtuple
from io import BytesIO

import urllib3
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps

from .constants import *


# Simple cursor class that lets me handle moving around the image quite well
# also get around the hassle of maintaining position and adding and subtracting.

class Cursor:

    def __init__(self, reset):
        self.x = 0
        self.y = 0
        self.reset_x = reset

    # Return current pos of cursor
    @property
    def pos(self):
        return self.x, self.y

    def move_x(self, quant):
        old_x = self.x
        self.x += quant
        #print('x moved from ', old_x, ' to ', self.x)

    def move_y(self, quant):
        old_y = self.y
        self.y += quant
        #print('y moved from ', old_y, ' to ', self.y)

    # Probably should call it reset_x because that's what it does
    # Reset x
    def reset(self):
        #print('x reset to ', self.reset_x)
        self.x = self.reset_x


# Cause relative paths are ass
_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

# Gamepedia API will return links decorated with [[]]
# at times with singular and plurals as well, re here handles that
reg = re.compile(r'\[\[[^\]]+\]\]')

with open(f"{_dir}/keystones.json") as f:
    keystones = js.load(f)

with open(f"{_dir}/ascendancy.json") as f:
    asc_nodes = js.load(f)

def unescape_to_list(props, ret_matches=False):
    matches = reg.findall(props)

    for match in set(matches):
        if '|' in match:
            props = props.replace(match, match.split('|')[1].strip(']]'))
        else:
            props = props.replace(match, match.strip('[[]]'))

    prop_list = html.unescape(props).replace('<br />', '<br>').split('<br>')
    prop_list = [x.replace('<em class="tc -corrupted">', '').replace('</em>', '') for x in prop_list]
    if ret_matches:
        return prop_list, matches
    return prop_list

class ItemRender:
    def __init__(self, flavor):
        self.flavor = flavor.lower()
        self.font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 15)
        self.lore_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCapsItalic.ttf', 15)
        self.header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        self.namebar_left = Image.open(f'{_dir}//{self.flavor}_namebar_left.png')
        self.namebar_right = Image.open(f'{_dir}//{self.flavor}_namebar_right.png')
        self.namebar_trans = Image.open(f'{_dir}//{self.flavor}_namebar_trans.png')
        self.separator = Image.open(f'{_dir}//{self.flavor}_separator.png')
        self.div_frame = Image.open(f'{_dir}//div_frame.png')

        # A namedtuple to handle properties.
        # This works fairly well except for Separators which is kinda hacky
        self.prop = namedtuple('Property', ['title', 'text', 'color'])

        # I don't know why PIL does this, but spacing with fonts is not consistent,
        # this means i have to compensate by spacing more after separators and stuff
        self.last_action = str()

    # Go through our total properties and image to get the image/box size
    # I feel the code is a bit redundant considering i have to instances
    # of an if-fest, calc_size and sort_stats.
    # TODO:
    # 1. Maybe make less redundant later
    def calc_size(self, stats, header):
        width = self.header_font.getsize(header)[0] + 6
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
                    stat_text += f" {attr.title()} {stat.text[attr]}" \
                                 f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                last_sep = False
            elif stat.title == "Lore":
                if type(stat.text) is list:
                    ht = LINE_SPACING
                    for line in stat.text:
                        #print(line)
                        w = self.font.getsize(line)
                        ht += STAT_HEIGHT
                        if w[0] > width:
                            width = w[0]
                    height += ht + STAT_SPACING
                else:
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

            #print(stat_text)
            if stat.title != "Image":
                w = self.font.getsize(stat_text)
            else:
                w = stat.text.size
            if w[0] > width:
                width = w[0]

        # 34 is the 17px padding from both sides
        return width+34, height+self.namebar_trans.size[1]+25

    #def

    def sort_stats(self, item):
        stats = list()
        separator = self.prop("Separator", None, None)

        if 'weapon' in item.tags:
            stats.append(self.prop(item.item_class, '', DESC_COLOR))
            stats.append(self.prop("Quality: ", f"+{item.quality}%", PROP_COLOR))
            if item.physical_damage:
                stats.append(self.prop("Physical Damage: ", item.physical_damage, PROP_COLOR))
            if item.cold_damage or item.fire_damage or item.lightning_damage:
                # I'd like to do this a bit neater sometime in the future
                eles = {}
                if item.fire_damage:
                    eles['fire'] = item.fire_damage
                if item.cold_damage:
                    eles['cold'] = item.cold_damage
                if item.lightning_damage:
                    eles['lightning'] = item.lightning_damage
                stats.append(self.prop("Elemental Damage:", eles, None))
            if item.chaos_damage:
                stats.append(self.prop("Chaos Damage: ", item.chaos_damage, CHAOS_COLOR))
            if item.critical_chance:
                stats.append(self.prop("Critical Strike Chance: ", item.critical_chance, None))
            if item.attack_speed:
                stats.append(self.prop("Attacks Per Second: ", item.attack_speed, PROP_COLOR))
            stats.append(self.prop("Weapon Range: ", item.range, None))

            stats.append(separator)

        elif 'armour' in item.tags:
            stats.append(self.prop("Quality: ", f"+{item.quality}%", PROP_COLOR))
            if item.armour:
                stats.append(self.prop("Armour: ", item.armour, PROP_COLOR))
            if item.evasion:
                stats.append(self.prop("Evasion: ", item.evasion, PROP_COLOR))
            if item.energy_shield:
                stats.append(self.prop("Energy Shield: ", item.energy_shield, PROP_COLOR))
            stats.append(separator)

        elif 'gem' in item.tags:
            stats.append(self.prop(item.gem_tags.replace(',', ', '), '', DESC_COLOR))
            if item.stats_per_level[0]['mana multiplier']:
                stats.append(self.prop("Mana Multiplier: ", f"{item.stats_per_level[0]['mana multiplier']}%", None))
            if item.radius:
                stats.append(self.prop("Radius: ", item.radius, None))
            if not item.is_aura:
                stats.append(self.prop("Mana Cost: ", f"({item.stats_per_level[1]['mana cost']}-{item.stats_per_level[20]['mana cost']})", PROP_COLOR))
            else:
                stats.append(self.prop("Mana Reserved: ", f"{item.stats_per_level[0]['mana cost']}%", None))
            if item.stats_per_level[20]['stored uses']:
                stats.append(self.prop("Stored Uses", {item.stats_per_level[20]['stored uses']}, None))
            if item.stats_per_level[0]['cooldown']:
                stats.append(self.prop("Cooldown Time: ", f"{item.stats_per_level[0]['cooldown']} sec", None))
            if item.cast_time:
                stats.append(self.prop("Cast Time: ", f"{item.cast_time} sec", None))
            if item.stats_per_level[0]['critical strike chance']:
                stats.append(self.prop("Critical Strike Chance: ", f"{item.stats_per_level[0]['critical strike chance']}%", None))
            if item.stats_per_level[0]['damage effectiveness']:
                stats.append(self.prop("Damage Effectiveness: ", f"{item.stats_per_level[0]['damage effectiveness']}%", None))
            stats.append(separator)

        elif item.base == 'Prophecy':
            if len(item.lore.split(' ')) > 7:
                lore = item.lore.split(' ')
                sep_lore = [lore[x:x+7] for x in range(0, len(lore),7)]
                for line in sep_lore:
                    stats.append(self.prop('Lore', ' '.join(line), UNIQUE_COLOR))
            else:
                stats.append(self.prop('Lore', item.lore, UNIQUE_COLOR))
            stats.append(separator)
            obj_list, matches = unescape_to_list(item.objective, ret_matches=True)
            if 'while holding' in obj_list[0]:
                itemname = matches[3].split('|')[1].strip(']]')
                pre_holding = obj_list[0].split(' while holding ')[0]
                new_obj = f"{pre_holding} while holding {itemname}"
            else:
                new_obj = obj_list[0]
            if len(new_obj.split(' ')) > 7:
                obj_split = new_obj.split(' ')
                obj_sep = [obj_split[x:x+7] for x in range(0, len(obj_split),7)]
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

        if 'gem' in item.tags:
            if len(item.description.split(' ')) > 7:
                desc = item.description.split(' ')
                description = [desc[x:x+7] for x in range(0, len(desc),7)]
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
                    sep_stat = [st[x:x+7] for x in range(0, len(st),7)]
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
                    if implicit.startswith('{'):
                        stats.append(self.prop(implicit.replace('{crafted}',''), '', CRAFTED))
                    else:
                        stats.append(self.prop(implicit, '', PROP_COLOR))
                    
                stats.append(separator)
            
            if explicits:
                for explicit in explicits:
                    if explicit.lower() == "corrupted":
                        stats.append(self.prop(explicit, '', CORRUPTED))
                    elif explicit.startswith('{'):
                        stats.append(self.prop(explicit.replace('{crafted}',''), '', CRAFTED))
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

        return stats

    def render_divcard(self, card):
        http = urllib3.PoolManager()
        r = http.request('GET', card.card_art, preload_content=False)
        art = Image.open(BytesIO(r.read()))
        art = art.convert('RGBA')
        item = Image.new('RGBA', self.div_frame.size, (255, 0, 0, 0))
        cur = Cursor(self.div_frame.size[0]//2)
        cur.reset()
        cur.move_x((art.size[0]//2)*-1)
        cur.move_y(47)
        item.alpha_composite(art, cur.pos)
        item.alpha_composite(self.div_frame, (0,0))
        cur.reset()
        d = ImageDraw.Draw(item)
        cur.y = 0
        cur.move_y(20)
        header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        cur.move_x((header_font.getsize(card.name)[0]//2)*-1)
        d.text(cur.pos, card.name, fill='black', font=header_font)
        cur.reset()
        cur.x = 77
        cur.y = 316
        cur.move_x((self.font.getsize(card.stack_size)[0] // 2) * -1)
        d.text(cur.pos, card.stack_size, fill=None, font=self.font)
        cur.y = 384
        cur.reset()
        fill = flavor_color[card.reward_flavor]
        cur.move_x((self.font.getsize(card.reward)[0] // 2) * -1)
        d.text(cur.pos, card.reward, fill=fill, font=self.font)
        cur.reset()
        cur.y = 536
        first_lore = unescape_to_list(card.lore)
        for first_line in first_lore:
            text = first_line
            if len(text.split(' ')) > 7:
                lore = text.split(' ')
                sep_lore = [lore[x:x+7] for x in range(0, len(lore),7)]
                for line in sep_lore:
                    joined_line = ' '.join(line)
                    cur.move_y(STAT_SPACING)
                    cur.move_x((self.font.getsize(joined_line)[0] // 2) * -1)
                    d.text(cur.pos, joined_line, fill=UNIQUE_COLOR, font=self.lore_font)
                    cur.move_y(self.lore_font.getsize(joined_line)[1])
                    cur.reset()
            else:
                cur.move_y(STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0] // 2) * -1)
                d.text(cur.pos, text, fill=UNIQUE_COLOR, font=self.lore_font)
                cur.move_y(self.lore_font.getsize(text)[1])
                cur.reset()
        return item

    def render(self, poe_item):
        stats = self.sort_stats(poe_item)
        fill = flavor_color[self.flavor]
        box_size = self.calc_size(stats, poe_item.name)
        #print('box size=', box_size, 'center', box_size[0]//2)
        center_x = box_size[0]//2
        item = Image.new('RGBA', box_size, color='black')
        cur = Cursor(center_x)
        item.paste(self.namebar_left, cur.pos)
        cur.move_x(self.namebar_left.size[0])
        transformed_namebar = self.namebar_trans.resize((item.size[0]-(self.namebar_left.size[0]*2),
                                                         self.namebar_trans.size[1]))
        item.paste(transformed_namebar, cur.pos)
        cur.move_x(transformed_namebar.size[0])
        item.paste(self.namebar_right, cur.pos)
        cur.reset()
        d = ImageDraw.Draw(item)
        cur.move_y(8)
        cur.move_x((self.header_font.getsize(poe_item.name)[0]//2)*-1)
        d.text(cur.pos, poe_item.name, fill=fill, font=self.header_font)
        cur.move_y(2+self.header_font.getsize(poe_item.name)[1])
        cur.reset()
        if 'gem' not in poe_item.tags and poe_item.base != "Prophecy":
            if poe_item.base not in poe_item.name:
                cur.move_x((self.header_font.getsize(poe_item.base)[0]//2)*-1)
                d.text(cur.pos, poe_item.base, fill=fill, font=self.header_font)
                cur.reset()
        cur.y = 0
        cur.move_y(transformed_namebar.size[1])
        #print(stats[-1].title)
        for stat in stats:
            if stat.title == "Separator":
                self.last_action = "Separator"
                #print('separator going to start')
                cur.move_x((self.separator.size[0]//2)*-1)
                cur.move_y(SEPARATOR_SPACING+2)
                item.paste(self.separator, cur.pos)
                #print('separator consumption')
                #print("sepsize", self.separator.size[1])
                #cur.move_y(self.separator.size[1])
                cur.reset()
            elif stat.title == "Elemental Damage:":
                stat_text = stat.title
                for element in stat.text.keys():
                    stat_text += f" {stat.text[element]}"
                cur.move_x((self.font.getsize(stat_text)[0]//2)*-1)
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize(stat.title)[0])
                for element in stat.text.keys():
                    d.text(cur.pos, f" {stat.text[element]}", fill=ELE_COLOR[element], font=self.font)
                    cur.move_x(self.font.getsize(f" {stat.text[element]}")[0])
                cur.move_y(STAT_HEIGHT)
                cur.reset()
                self.last_action = ""
            elif stat.title == "Requires":
                text = stat.title
                for attr in stat.text.keys():
                    text += f" {attr.title()} {stat.text[attr]}" \
                            f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                cur.move_y(0 if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize(stat.title)[0])
                for attr in stat.text.keys():
                    if attr == 'level':
                        d.text(cur.pos, f" {attr.title()}", fill=DESC_COLOR, font=self.font)
                        cur.move_x(self.font.getsize(f" {attr.title()}")[0])
                        attribute_final = f" {stat.text[attr]}"\
                                          f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                        d.text(cur.pos, attribute_final, font=self.font)
                    else:
                        d.text(cur.pos, f" {stat.text[attr]}", font=self.font)
                        cur.move_x(self.font.getsize(f" {stat.text[attr]}")[0])
                        attribute_final = f" {attr.title()}"\
                                          f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                        d.text(cur.pos, attribute_final, font=self.font, fill=DESC_COLOR)
                    cur.move_x(self.font.getsize(attribute_final)[0])
                cur.move_y(STAT_HEIGHT)
                #print("req", self.font.getsize(stat.title)[1])
                cur.reset()
                self.last_action = ""
            elif stat.title == "Lore":
                if type(stat.text) is list:
                    for line in stat.text:
                        text = line
                        cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                        cur.move_x((self.font.getsize(text)[0]//2)*-1)
                        d.text(cur.pos, text, fill=stat.color, font=self.lore_font)
                        cur.move_y(self.lore_font.getsize(text)[1])
                        cur.reset()
                        self.last_action = ""
                else:
                    cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                    cur.move_x((self.font.getsize(stat.text)[0] // 2) * -1)
                    d.text(cur.pos, stat.text, fill=stat.color, font=self.lore_font)
                    cur.move_y(STAT_HEIGHT)
                    cur.reset()
            elif stat.title == "Image":
                cur.move_x((stat.text.size[0]//2)*-1)
                cur.move_y(4)
                #stat.text.show()
                #item.show()
                item.alpha_composite(stat.text, cur.pos)
                cur.move_y(stat.text.size[1])
                cur.reset()
            elif stat.title == "Stored Uses":
                text = f"Can Store {stat.text} Use(s)"
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                d.text(cur.pos, "Can Store ", fill=DESC_COLOR, font=self.font)
                cur.move_x(self.font.getsize("Can Store ")[0])
                d.text(cur.pos, stat.text+ " ", font=self.font)
                cur.move_x(self.font.getsize(stat.text +" ")[0])
                d.text(cur.pos, "Use(s)", fill=DESC_COLOR, font=self.font)
                cur.reset()
            elif stat.title == "Gem Help":
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(stat.text)[0]//2)*-1)
                d.text(cur.pos, stat.text, fill=DESC_COLOR, font=self.lore_font)
                cur.move_y(STAT_HEIGHT)
                cur.reset()
            elif stat.title == "Seal Cost: ":
                coin = Image.open(f'{_dir}//silver_coin.png').convert('RGBA')
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(stat.title)[0]//2)*-1)
                d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                cur.move_y(STAT_HEIGHT+STAT_SPACING)
                cur.reset()
                sealtext = f"{stat.text}X   Silver Coin"
                cur.move_x((self.font.getsize(sealtext)[0] // 2) * -1)
                d.text(cur.pos, f"{stat.text}X ", fill=NORMAL_COLOR, font=self.font)
                cur.move_x(self.font.getsize(f"{stat.text}X ")[0])
                item.alpha_composite(coin, cur.pos)
                cur.move_x(coin.size[0]+2)
                d.text(cur.pos, "Silver Coin", fill=NORMAL_COLOR, font=self.font)
                cur.move_y(STAT_HEIGHT)
                cur.reset()
            else:
                text = f"{stat.title}{stat.text}"
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                if ':' in stat.title:
                    #print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                    cur.move_x(self.font.getsize(stat.title)[0])
                    d.text(cur.pos, stat.text, fill=stat.color, font=self.font)
                else:
                    if stat.title.startswith('{'):
                        color = CRAFTED
                    else:
                        color = stat.color
                    #print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=color, font=self.font)
                cur.move_y(STAT_HEIGHT)
                cur.reset()
                self.last_action = ""
        item = ImageOps.expand(item, border=1, fill=fill)
        return item


def parse_pob_item(itemtext):
    item = itemtext.split('\n')
    qualtext = None
    pobitem = {}
    for index, line in enumerate(item):
        if line.startswith("Rarity"):
            pobitem['rarity'] = line.split(' ')[1].title()
            pobitem['rarity_index'] = index
            continue
        elif line.startswith("Item Level"):
            if item[index+3].startswith('--'):
                pobitem['statstart_index'] = index + 3
            else:
                pobitem['statstart_index'] = index + 1
        elif line.startswith("====="):
            pobitem['statstart_index'] = index
        elif line.startswith("Implicits:"):
            pobitem['implicits'] = int(line.split(': ')[1])
            pobitem['statstart_index'] = index+pobitem['implicits']
        elif line.startswith("Requires"):
            pobitem['statstart_index'] = index
        elif line.startswith("Quality"):
            qualtext = line.split("Quality: +")[1].split("%")[0]
    if pobitem['rarity'].lower() in ['unique', 'rare']:
        name = item[pobitem['rarity_index']+1]
        base = item[pobitem['rarity_index']+2]
    elif pobitem['rarity'].lower() == 'magic':
        name = item[pobitem['rarity_index']+1]
        base = name.split('>>')[-1]
    else:
        name = item[pobitem['rarity_index'] + 1]
        base = item[pobitem['rarity_index'] + 1]
    if 'implicits' in pobitem:
        implicits = item[pobitem['statstart_index'] - (pobitem['implicits']-1):][:pobitem['implicits']]
    elif item[pobitem['statstart_index']-2].startswith('--') and 'Item Level' not in item[pobitem['statstart_index']-1]:
        imp_end = "None"
        for ind, stat in enumerate(item[pobitem['statstart_index']-1:]):
            print(stat)
            if stat.startswith('--'):
                if item[pobitem['statstart_index']-1:][ind+1] not in ['Shaper Item', 'Elder Item']:
                    imp_end = ind
                    break
        if imp_end != "None":
            print(item[pobitem['statstart_index']-2:])
            print(imp_end)
            implicits = item[pobitem['statstart_index']-1:][0:imp_end]
        else:
            implicits = []
    else:
        implicits = []
    stat_text = item[pobitem['statstart_index']+1:]
    return {'name': name, 'base': base, 'stats': stat_text, 'rarity': pobitem['rarity'],
            'implicits': implicits, 'quality': int(qualtext)}

def modify_base_stats(item):
    stats = {'flat es': 0, 'flat armour': 0, 'flat evasion': 0,
             'inc es': int(item.quality), 'inc armour': int(item.quality), 'inc evasion': int(item.quality),
             'aspd': 0,
             'fire low': 0, 'fire max': 0, 'fire inc': 0, 'cold low': 0, 'cold max': 0,
             'cold inc': 0, 'light low': 0, 'light max': 0, 'light inc': 0,
             'chaos low': 0, 'chaos max': 0, 'chaos inc': 0,
             'phys low': 0, 'phys max': 0, 'phys inc': int(item.quality),
             'cc': 0, 'range': 0}
    if item.implicits:
        for stat in unescape_to_list(item.implicits):
            text = stat.lower().replace('{crafted}', '')
            if ' per ' in text or ' if ' in text:
                continue
            if " to " in text:
                if 'armour' in text:
                    stats['flat armour'] += int(text.split(' ')[0][1:])
                elif 'evasion rating' in text:
                    stats['flat evasion'] += int(text.split(' ')[0][1:])
                elif 'maximum energy shield' in text:
                    stats['flat es'] += int(text.split(' ')[0][1:])
                elif 'weapon range' in text:
                    stats['range'] += int(text.split(' ')[0][1:])
                if "damage" in text and "reflect" not in text and "converted" not in text:
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
                if "armour" in text:
                    stats['inc armour'] += int(text.split(' ')[0][:-1])
                if "evasion rating" in text:
                    stats['inc evasion'] += int(text.split(' ')[0][:-1])
                if "energy shield" in text:
                    stats['inc es'] += int(text.split(' ')[0][:-1])
                if "attack speed" in text:
                    stats['aspd'] += int(text.split(' ')[0][:-1])
                if "critical strike chance" in text:
                    stats['cc'] += int(text.split(' ')[0][:-1])
                if "damage" in text:
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
            text = stat.lower().replace('{crafted}', '')
            print(text)
            if ' per ' in text or ' if ' in text:
                continue
            if " to " in text:
                if 'armour' in text:
                    stats['flat armour'] += int(text.split(' ')[0][1:])
                elif 'evasion rating' in text:
                    stats['flat evasion'] += int(text.split(' ')[0][1:])
                elif 'maximum energy shield' in text:
                    stats['flat es'] += int(text.split(' ')[0][1:])
                elif 'weapon range' in text:
                    stats['range'] += int(text.split(' ')[0][1:])
                if "damage" in text and "reflect" not in text and "converted" not in text:
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
                        print(text)
                        stats[f'{k} low'] += int(text.split(' to ')[0].split(' ')[-1])
                        stats[f'{k} max'] += int(text.split(' to ')[1].split(' ')[0])
            elif " increased " in text:
                if "armour" in text:
                    stats['inc armour'] += int(text.split(' ')[0][:-1])
                if "evasion rating" in text:
                    stats['inc evasion'] += int(text.split(' ')[0][:-1])
                if "energy shield" in text:
                    print(text)
                    stats['inc es'] += int(text.split(' ')[0][:-1])
                if "attack speed" in text:
                    stats['aspd'] += int(text.split(' ')[0][:-1])
                if "critical strike chance" in text:
                    stats['cc'] += int(text.split(' ')[0][:-1])
                if "damage" in text:
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

    print(stats)

    if 'weapon' in item.tags:
        if stats['aspd']:
            _as = float(item.attack_speed)
            item.attack_speed = f"{(_as + (stats['aspd']/100)*_as):.2}"
        if stats['cc']:
            cc = float(item.critical_chance.replace('%',''))
            cc += cc*(stats['cc']/100)
            item.critical_chance = f"{cc:.2}%"
        if stats['range']:
            i_range = int(item.range)
            i_range += stats['range']
            item.range = f"{i_range}"
        if stats['fire max'] or stats['fire inc']:
            if stats['fire max']:
                item.fire_min = stats['fire low']
                item.fire_max = stats['fire max']
            fire_m = int(item.fire_min)
            fire_mx = int(item.fire_max)
            fire_m += fire_m*(stats['fire inc']/100)
            fire_mx += fire_mx*(stats['fire inc']/100)
            item.fire_min = str(round(fire_m))
            item.fire_max = str(round(fire_mx))
        if stats['cold max'] or stats['cold inc']:
            if stats['cold max']:
                item.cold_min = stats['cold low']
                item.cold_max = stats['cold max']
            cold_m = int(item.cold_min)
            cold_mx = int(item.cold_max)
            cold_m += cold_m*(stats['cold inc']/100)
            cold_mx += cold_mx*(stats['cold inc']/100)
            item.cold_min = str(round(cold_m))
            item.cold_max = str(round(cold_mx))
        if stats['light max'] or stats['light inc']:
            if stats['light max']:
                item.lightning_min = stats['light low']
                item.lightning_max = stats['light max']
            lightning_m = int(item.lightning_min)
            lightning_mx = int(item.lightning_max)
            lightning_m += lightning_m*(stats['light inc']/100)
            lightning_mx += lightning_mx*(stats['light inc']/100)
            item.lightning_min = str(round(lightning_m))
            item.lightning_max = str(round(lightning_mx))
        if stats['chaos max'] or stats['chaos inc']:
            if stats['chaos max']:
                item.chaos_min = stats['chaos low']
                item.chaos_max = stats['chaos max']
            chaos_m = int(item.chaos_min)
            chaos_mx = int(item.chaos_max)
            chaos_m += chaos_m*(stats['chaos inc']/100)
            chaos_mx += chaos_mx*(stats['chaos inc']/100)
            item.chaos_min = str(round(chaos_m))
            item.chaos_max = str(round(chaos_mx))
        if stats['phys max'] or stats['phys inc']:
            if stats['phys max']:
                item.physical_min = stats['phys low']
                item.physical_max = stats['phys max']
            physical_m = int(item.physical_min)
            physical_mx = int(item.physical_max)
            physical_m += physical_m*(stats['phys inc']/100)
            physical_mx += physical_mx*(stats['phys inc']/100)
            item.physical_min = str(round(physical_m))
            item.physical_max = str(round(physical_mx))
    else:
        if item.armour:
            arm = int(item.armour)
            arm += stats['flat armour']
            arm += (stats['inc armour']/100) * arm
            item.armour = str(round(arm))
        if item.evasion:
            ev = int(item.evasion)
            ev += stats['flat evasion']
            ev += (stats['inc evasion']/100) * ev
            item.evasion = str(round(ev))
        if item.energy_shield:
            print(item.energy_shield)
            es = int(item.energy_shield)
            print(stats['flat es'])
            es += stats['flat es']
            es += (stats['inc es']/100) * es
            item.energy_shield = str(round(es))
def _get_wiki_base(item, object_dict, cl, slot, char_api=False):
    if item['rarity'].lower() == 'unique':
        wiki_base = cl.find_items({'name': item['name']})[0]
    elif "Flask" in item['base']:
        return
    else:
        #print("base", item['base'])
        try:
            if item['rarity'].lower() == 'magic' and item['name'] == item['base']:
                if '' in item['stats']:
                    item['stats'].remove('')
                if len(item['stats']) == 1:
                    if ' of ' in item['base']:
                        item['base'] = item['base'].rsplit(' of ')[0]
                    else:
                        item['base'] = ' '.join(item['base'].split(' ')[1:])
                else:
                    item['base'] = ' '.join(item['base'].split(' of ')[0].split(' ')[1:])

            wiki_base = cl.find_items({'name': item['base']})[0]
        except:
            print(item)
        wiki_base.rarity = item['rarity']
        wiki_base.name = item['name']
        wiki_base.base = item['base']
    if char_api:
        if item['implicits']:
            wiki_base.implicits = '&lt;br&gt;'.join(item['implicits'])
        if item['explicits']:
            wiki_base.explicits = '&lt;br&gt;'.join(item['explicits'])
    else:
        if item['implicits']:
            wiki_base.implicits = '<br>'.join(item['implicits'])
        if item['rarity'].lower() != 'unique':
            wiki_base.explicits = '&lt;br&gt;'.join(item['stats'])
        else:
            if wiki_base.implicits:
                pob_implicits = item['stats'][:len(wiki_base.implicits.split('&lt;br&gt;'))]
                wiki_base.implicits = '&lt;br&gt;'.join(pob_implicits)
    if 'quality' in item and item['quality']:
        wiki_base.quality = item['quality']

    if wiki_base.rarity.lower() != 'unique' and getattr(wiki_base, 'armour', "Absent") != "Absent":
        modify_base_stats(wiki_base)
    object_dict[slot] = wiki_base

def parse_pob_xml(xml: str, cl=None):
    tree = ET.ElementTree(ET.fromstring(xml))
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
        for slot in equipped:
            item_id = equipped[slot]['id']
            tree_item = tree.find(f'Items/Item[@id="{item_id}"]')
            if 'variant' in tree_item.attrib:
                lines = tree_item.text.replace('\t','').split('\n')
                for line in lines[:]:
                    if line.startswith('{variant'):
                        variant = line.split('variant:')[1][0]
                        if variant != tree_item.attrib['variant']:
                            lines.remove(line)
                tree_item.text = '\n'.join(lines)
            equipped[slot]['raw'] = tree_item.text.replace('\t', '')
            ##print(equipped[slot]['raw'])
            equipped[slot]['parsed'] = parse_pob_item(equipped[slot]['raw'])
            item = equipped[slot]['parsed']
            t = threading.Thread(target=_get_wiki_base, args=(item, obj_dict, cl, slot))
            threads.append(t)
            t.start()
        for thread in threads:
            thread.join()
        for slot in obj_dict:
            equipped[slot]['object'] = obj_dict[slot]
    skill_slots = tree.findall('Skills/Skill')
    for skill in skill_slots:
        if 'slot' in skill.attrib:
            slot = skill.attrib['slot']
            equipped[slot]['gems'] = []
            lst = equipped[slot]['gems']
        else:
            if not 'gem_groups' in equipped:
                equipped['gem_groups'] = {}
            if not skill.getchildren()[0].attrib['nameSpec'] in equipped['gem_groups']:
                equipped['gem_groups'][skill.getchildren()[0].attrib['nameSpec']] = []
            lst = equipped['gem_groups'][skill.getchildren()[0].attrib['nameSpec']]
        gems = skill.getchildren()
        for gem in gems:
            gem_d = {}
            gem_d['name'] = gem.attrib['nameSpec']
            gem_d['level'] = gem.attrib['level']
            gem_d['enabled'] = gem.attrib['enabled']
            gem_d['quality'] = gem.attrib['quality']
            lst.append(gem_d)
    stats = {}
    active_spec = int(tree.find('Tree').attrib['activeSpec'])-1
    current_tree = tree.findall('Tree/Spec')[active_spec]
    tree_base64 = current_tree.find('URL').text.replace('\t', '').replace('\n', '').rsplit('/', 1)[1]
    byte_tree = binascii.a2b_base64(tree_base64.replace('-', '+').replace('_', '/'))
    pos = 7
    total_nodes = (len(byte_tree)-7)//2
    nodes = []
    for _ in range(total_nodes):
        nodes.append(str(int.from_bytes(byte_tree[pos:pos+2], byteorder='big')))
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
    except:
        stats['bandit'] = "None"
    stats['class'] = tree.find('Build').attrib['className']
    stats['ascendancy'] = tree.find('Build').attrib['ascendClassName']
    stats['total_dps'] = tree.find('Build/PlayerStat[@stat="TotalDPS"]').attrib['value']
    stats['level'] = tree.find('Build').attrib['level']
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
    stats['power_charges'] = tree.find('Build/PlayerStat[@stat="PowerChargesMax"]').attrib['value']
    stats['frenzy_charges'] = tree.find('Build/PlayerStat[@stat="FrenzyChargesMax"]').attrib['value']
    stats['endurance_charges'] = tree.find('Build/PlayerStat[@stat="EnduranceChargesMax"]').attrib['value']

    return stats


def parse_poe_char_api(json, cl):
    rarity = {0: "Normal",
              1: "Magic",
              2: "Rare",
              3: "Unique",
              4: "Gem"}
    equipped = {}
    threads = []
    obj_dict = {}
    for item in json['items']:
        char_item = {}
        char_item['rarity'] = rarity[item['frameType']]
        char_item['name'] = item["name"].split('>>')[-1]
        if char_item['name'] == '':
            char_item['name'] = item["typeLine"].split('>>')[-1]
        ##print(char_item['name'], item['category'])
        if char_item['rarity'] == "Magic":
            char_item['base'] = item['typeLine'].split('>>')[-1]
        else:
            char_item['base'] = item["typeLine"]
        if 'Ring' in item['inventoryId']:
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
            slot = f"Flask {int(item['x'])+1}"
            char_item['name'] = item["typeLine"].split('>>')[-1]
            if item['frameType'] == 1 and 'Flask of' in char_item['name']:
                char_item['rarity'] = "Magic"
        elif item['inventoryId'] in ['Amulet', 'Helm', 'Gloves', 'Belt', 'Flask', 'Boots', 'Weapon',
                                                 'PassiveJewels']:
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
        if 'corrupted' in item:
            char_item['explicits'].append('Corrupted')
        if 'enchantMods' in item:
            char_item['implicits'] = ["{crafted}"+item['enchantMods'][0]]
        equipped[slot] = {}
        #print(item.keys())
        if slot == 'PassiveJewels':
            if type(equipped[slot]) is dict:
                equipped[slot] = []
            equipped[slot].append(char_item)
        else:
            equipped[slot] = char_item
        if 'socketedItems' in item:
            equipped[slot]['gems'] = []
            for socketed in item['socketedItems']:
                if socketed['frameType'] == 4:
                    gem_d = {}
                    gem_d['name'] = socketed['typeLine']
                    for prop in socketed['properties']:
                        if prop['name'] == 'Quality':
                            gem_d['quality'] = prop['values'][0][0].replace('+', '').replace('%', '')
                        if prop['name'] == 'Level':
                            gem_d['level'] = prop['values'][0][0]
                    if not 'quality' in gem_d:
                        gem_d['quality'] = 0
                    equipped[slot]['gems'].append(gem_d)
        if slot != 'PassiveJewels' and 'Flask' not in slot:
            t = threading.Thread(target=_get_wiki_base, args=(char_item, obj_dict, cl, slot, True))
            threads.append(t)
            t.start()
    for thread in threads:
        thread.join()
    for slot in obj_dict:
        equipped[slot]['object'] = obj_dict[slot]
    stats = {'equipped': equipped}
    if 'character' in json:
        stats['level'] = json['character']['level']
        stats['ascendancy'] = json['character']['ascendancyClass']
        stats['class'] = json['character']['class']
        stats['charname'] = json['character']['name']
        stats['league'] = json['character']['league']
    return stats

def poe_skill_tree(hashes, asc: str = "None",
                   return_keystones=False, return_asc=False):
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
        "ranger":  {
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
    # Not sure if 7th byte should inherently be 0, but i think its related to start/exit nodes
    ba = bytearray()
    ba += bytes([0])
    ba += bytes([0])
    ba += bytes([0])
    ba += bytes([4])
    found = False
    asc = asc.lower()
    for a_char in ascendancy_bytes:
        if asc in ascendancy_bytes[a_char]:
            found = True
            char_class = a_char
            break
    if not found:
        char_class = asc
        asc = "none"
    ba += bytes([char[char_class]])
    ba += bytes([ascendancy_bytes[char_class][asc.lower()]])
    ba += bytes([0])
    for hash in hashes:
        ba += hash.to_bytes(2, 'big')
    post = binascii.b2a_base64(ba).decode().replace('+', '-').replace('/', '_')
    tree_keystones = []
    ascendancy = []
    for hash in hashes:
        if str(hash) in keystones:
            tree_keystones.append(keystones[str(hash)])
        if str(hash) in asc_nodes:
            ascendancy.append(asc_nodes[str(hash)])

    if return_keystones and return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", tree_keystones, ascendancy
    elif return_keystones and not return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", tree_keystones
    elif return_asc:
        return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}", ascendancy

    return f"https://www.pathofexile.com/fullscreen-passive-skill-tree/{post}"
