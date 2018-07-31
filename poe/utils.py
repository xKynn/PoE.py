import html
import re
import os
import urllib3

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps
from collections import namedtuple
from io import BytesIO
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
        print('x moved from ', old_x, ' to ', self.x)

    def move_y(self, quant):
        old_y = self.y
        self.y += quant
        print('y moved from ', old_y, ' to ', self.y)

    # Probably should call it reset_x because that's what it does
    # Reset x
    def reset(self):
        print('x reset to ', self.reset_x)
        self.x = self.reset_x


# Cause relative paths are ass
_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


class ItemRender:
    def __init__(self, flavor):
        self.flavor = flavor
        self.font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 15)
        self.lore_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCapsItalic.ttf', 15)
        self.header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        self.namebar_left = Image.open(f'{_dir}//{flavor}_namebar_left.png')
        self.namebar_right = Image.open(f'{_dir}//{flavor}_namebar_right.png')
        self.namebar_trans = Image.open(f'{_dir}//{flavor}_namebar_trans.png')
        self.separator = Image.open(f'{_dir}//{flavor}_separator.png')

        # A namedtuple to handle properties.
        # This works fairly well except for Separators which is kinda hacky
        self.prop = namedtuple('Property', ['title', 'text', 'color'])

        # Gamepedia API will return links decorated with [[]]
        # at times with singular and plurals as well, re here handles that
        self.re = re.compile(r'\[\[[^\]]+\]\]')

        # I don't know why PIL does this, but spacing with fonts is not consistent,
        # this means i have to compensate by spacing more after separators and stuff
        self.last_action = str()

    def unescape_to_list(self, props):
        matches = self.re.findall(props)

        for match in set(matches):
            if '|' in match:
                props = props.replace(match, match.split('|')[1].strip(']]'))
            else:
                props = props.replace(match, match.strip('[[]]'))

        prop_list = html.unescape(props).split('<br>')
        return prop_list

    # Go through our total properties and image to get the image/box size
    # I feel the code is a bit redundant considering i have to instances
    # of an if-fest, calc_size and sort_stats.
    # TODO:
    # 1. Maybe make less redundant later
    def calc_size(self, stats):
        width = 0
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
                ht = LINE_SPACING
                for line in stat.text:
                    print(line)
                    w = self.font.getsize(line)
                    ht += STAT_HEIGHT
                    if w[0] > width:
                        width = w[0]
                height += ht + STAT_SPACING
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

            print(stat_text)
            if stat.title != "Image":
                w = self.font.getsize(stat_text)
            else:
                w = stat.text.size
            if w[0] > width:
                width = w[0]

        # 34 is the 17px padding from both sides
        return width+34, height+self.namebar_trans.size[1]

    #def

    def sort_stats(self, item):
        stats = list()
        separator = self.prop("Separator", None, None)

        if 'weapon' in item.tags:
            stats.append(self.prop(item.item_class, '', DESC_COLOR))
            stats.append(self.prop("Quality: ", item.quality, PROP_COLOR))
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
            stats.append(self.prop("Quality: ", item.quality, PROP_COLOR))
            if item.armour:
                stats.append(self.prop("Armour: ", item.armour, PROP_COLOR))
            if item.evasion:
                stats.append(self.prop("Evasion: ", item.evasion, PROP_COLOR))
            if item.energy_shield:
                stats.append(self.prop("Energy Shield: ", item.energy_shield, PROP_COLOR))
            stats.append(separator)

        elif 'gem' in item.tags:
            stats.append(self.prop(item.gem_tags, '', DESC_COLOR))
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


        if item.requirements.has_reqs:
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
        if 'gem' not in item.tags:
            if item.implicits:
                implicits = self.unescape_to_list(item.implicits)
                for implicit in implicits:
                    stats.append(self.prop(implicit, '', PROP_COLOR))
                stats.append(separator)

            if item.explicits:
                explicits = self.unescape_to_list(item.explicits)
                for explicit in explicits:
                    stats.append(self.prop(explicit, '', PROP_COLOR))

            if item.lore:
                if stats[-1] is not separator:
                    stats.append(separator)
                lore = self.prop('Lore', self.unescape_to_list(item.lore), UNIQUE_COLOR)
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

    def render(self, poe_item):
        stats = self.sort_stats(poe_item)
        fill = flavor_color[self.flavor]
        box_size = self.calc_size(stats)
        print('box size=', box_size, 'center', box_size[0]//2)
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
        if 'gem' not in poe_item.tags:
            cur.move_x((self.header_font.getsize(poe_item.base)[0]//2)*-1)
            d.text(cur.pos, poe_item.base, fill=UNIQUE_COLOR, font=self.header_font)
            cur.reset()
        cur.y = 0
        cur.move_y(transformed_namebar.size[1])
        print(stats[-1].title)
        for stat in stats:
            if stat.title == "Separator":
                self.last_action = "Separator"
                print('separator going to start')
                cur.move_x((self.separator.size[0]//2)*-1)
                cur.move_y(SEPARATOR_SPACING+2)
                item.paste(self.separator, cur.pos)
                print('separator consumption')
                print("sepsize", self.separator.size[1])
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
                if self.last_action == "Separator":
                    print("last was sep")
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
                print("req", self.font.getsize(stat.title)[1])
                cur.reset()
                self.last_action = ""
            elif stat.title == "Lore":
                for line in stat.text:
                    text = line
                    cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                    cur.move_x((self.font.getsize(text)[0]//2)*-1)
                    d.text(cur.pos, text, fill=stat.color, font=self.lore_font)
                    cur.move_y(self.lore_font.getsize(text)[1])
                    cur.reset()
                    self.last_action = ""
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
            else:
                text = f"{stat.title}{stat.text}"
                cur.move_y(SEPARATOR_SPACING if self.last_action == "Separator" else STAT_SPACING)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                if ':' in stat.title:
                    print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=DESC_COLOR, font=self.font)
                    cur.move_x(self.font.getsize(stat.title)[0])
                    d.text(cur.pos, stat.text, fill=stat.color, font=self.font)
                else:
                    print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=stat.color, font=self.font)
                cur.move_y(STAT_HEIGHT)
                cur.reset()
                self.last_action = ""
        item = ImageOps.expand(item, border=1, fill=fill)
        item.save('test.png')
