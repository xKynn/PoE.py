from functools import wraps
import inspect
import html
import re
import os
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps
from collections import namedtuple


def initializer(func):
    names, varargs, keywords, defaults = inspect.getargspec(func)

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        for name, arg in list(zip(names[1:], args)) + list(kwargs.items()):
            setattr(self, name, arg)

        # for name, default in zip(reversed(names), reversed(defaults)):
        #     if not hasattr(self, name):
        #         setattr(self, name, default)

        func(self, *args, **kwargs)

    return wrapper


class Cursor:

    def __init__(self, reset):
        self.x = 0
        self.y = 0
        self.reset_x = reset

    @property
    def pos(self):
        return (self.x, self.y)

    def move_x(self, quant):
        old_x = self.x
        self.x += quant
        print('x moved from ', old_x, ' to ', self.x)

    def move_y(self, quant):
        old_y = self.y
        self.y += quant
        print('y moved from ', old_y, ' to ', self.y)

    def reset(self):
        print('x reset to ', self.reset_x)
        self.x = self.reset_x


_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


class ItemRender:
    def __init__(self, rarity):
        self.font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 15)
        self.header_font = ImageFont.truetype(f'{_dir}//Fontin-SmallCaps.ttf', 20)
        self.namebar_left = Image.open(f'{_dir}//{rarity}_namebar_left.png')
        self.namebar_right = Image.open(f'{_dir}//{rarity}_namebar_right.png')
        self.namebar_trans = Image.open(f'{_dir}//{rarity}_namebar_trans.png')
        self.separator = Image.open(f'{_dir}//{rarity}_separator.png')
        self.prop = namedtuple('Property', ['title', 'text', 'color'])
        self.re = re.compile(r'\[\[[^\]]+\]\]')
        self.prop_color = (136, 136, 255)
        self.ele_color = {'fire': (150, 0, 0),
                          'cold': (54, 100, 146),
                          'lightning': (255, 215, 0)}
        self.prop_chaos = (208, 32, 144)
        self.unique_color = (175, 96, 37)
        self.prop_desc = (127, 127, 127)

    def unescape_to_list(self, props):
        matches = self.re.findall(props)

        for match in set(matches):
            if '|' in match:
                props = props.replace(match, match.split('|')[1].strip(']]'))
            else:
                props = props.replace(match, match.strip('[[]]'))

        prop_list = html.unescape(props).split('<br>')
        return prop_list

    def calc_size(self, stats):
        width = 0
        height = 0
        last_stat = ""
        for stat in stats:
            if stat.title == "Separator":
                height += 8
                last_stat = "sep"
                continue
            elif stat.title == "Elemental Damage:":
                stat_text = stat.title
                for element in stat.text.keys():
                    stat_text += f" {stat.text[element]}"
                last_stat = ""
            elif stat.title == "Requires":
                height += 19
                stat_text = stat.title
                for attr in stat.text.keys():
                    stat_text += f" {attr.title()} {stat.text[attr]}" \
                                 f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                last_stat = ""
            elif stat.title == "Lore":
                ht = 4
                for line in stat.text:
                    print(line)
                    w = self.font.getsize(line)
                    ht += 19
                    if w[0] > width:
                        width = w[0]
                height += ht
                last_stat = ""
                continue
            else:
                if last_stat == "sep":
                    height += 19
                else:
                    height += 19
                stat_text = f"{stat.title}{stat.text}"

            print(stat_text)
            w = self.font.getsize(stat_text)
            if w[0] > width:
                width = w[0]

        # 34 is the 17px padding from both sides
        return width+34, height+56

    def sort_stats(self, item):
        stats = list()
        separator = self.prop("Separator", None, None)
        stats.append(self.prop(item.item_class, '', self.prop_desc))
        stats.append(self.prop("Quality: ", item.quality, self.prop_color))
        if item.physical_damage:
            stats.append(self.prop("Physical Damage: ", item.physical_damage, self.prop_color))
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
            stats.append(self.prop("Chaos Damage: ", item.chaos_damage, self.prop_chaos))
        if item.critical_chance:
            stats.append(self.prop("Critical Strike Chance: ", item.critical_chance, None))
        if item.attack_speed:
            stats.append(self.prop("Attacks Per Second: ", item.attack_speed, self.prop_color))
        stats.append(self.prop("Weapon Range: ", item.range, None))

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

        if item.implicits:
            implicits = self.unescape_to_list(item.implicits)
            for implicit in implicits:
                stats.append(self.prop(implicit, '', self.prop_color))
            stats.append(separator)

        if item.explicits:
            explicits = self.unescape_to_list(item.explicits)
            for explicit in explicits:
                stats.append(self.prop(explicit, '', self.prop_color))

        if item.lore:
            if stats[-1] is not separator:
                stats.append(separator)
            lore = self.prop('Lore', self.unescape_to_list(item.lore), self.unique_color)
            stats.append(lore)

        return stats

    def render(self, weapon):
        stats = self.sort_stats(weapon)
        box_size = self.calc_size(stats)
        print('box size=', box_size, 'center', box_size[0]//2)
        center_x = box_size[0]//2
        item = Image.new('RGB', box_size)
        item = ImageOps.expand(item, border=1, fill=self.unique_color)
        cur = Cursor(center_x)
        item.paste(self.namebar_left, cur.pos)
        cur.move_x(self.namebar_left.size[0])
        transformed_namebar = self.namebar_trans.resize((box_size[0]-(self.namebar_left.size[0]*2),
                                                         self.namebar_trans.size[1]))
        item.paste(transformed_namebar, cur.pos)
        cur.move_x(transformed_namebar.size[0])
        item.paste(self.namebar_right, cur.pos)
        cur.reset()
        d = ImageDraw.Draw(item)
        cur.move_y(8)
        cur.move_x((self.header_font.getsize(weapon.name)[0]//2)*-1)
        d.text(cur.pos, weapon.name, fill=self.unique_color, font=self.header_font)
        cur.move_y(2+self.header_font.getsize(weapon.name)[1])
        cur.reset()
        cur.move_x((self.header_font.getsize(weapon.base)[0]//2)*-1)
        d.text(cur.pos, weapon.base, fill=self.unique_color, font=self.header_font)
        cur.reset()
        cur.y = 0
        cur.move_y(transformed_namebar.size[1])
        self.last_action = ""
        print(stats[-1].title)
        for stat in stats:
            if stat.title == "Separator":
                self.last_action = "Separator"
                print('separator going to start')
                cur.move_x((self.separator.size[0]//2)*-1)
                cur.move_y(5)
                item.paste(self.separator, cur.pos)
                print('separator consumption')
                cur.move_y(self.separator.size[1])
                cur.reset()
            elif stat.title == "Elemental Damage:":
                stat_text = stat.title
                for element in stat.text.keys():
                    stat_text += f" {stat.text[element]}"
                cur.move_x((self.font.getsize(stat_text)[0]//2)*-1)
                cur.move_y(2 if self.last_action == "Separator" else 4)
                d.text(cur.pos, stat.title, fill=self.prop_desc, font=self.font)
                cur.move_x(self.font.getsize(stat.title))
                for element in stat.text.keys():
                    d.text(cur.pos, f" {stat.text}", fill=self.ele_color[element], font=self.font)
                    cur.move_x(self.font.getsize(f" {stat.text}")[0])
                cur.move_y(self.font.getsize(stat.title)[1])
                cur.reset()
                self.last_action = ""
            elif stat.title == "Requires":
                text = stat.title
                for attr in stat.text.keys():
                    text += f" {attr.title()} {stat.text[attr]}" \
                            f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                if self.last_action == "Separator":
                    print("last was sep")
                cur.move_y(2 if self.last_action == "Separator" else 4)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                d.text(cur.pos, stat.title, fill=self.prop_desc, font=self.font)
                cur.move_x(self.font.getsize(stat.title)[0])
                for attr in stat.text.keys():
                    if attr == 'level':
                        d.text(cur.pos, f" {attr.title()}", fill=self.prop_desc, font=self.font)
                        cur.move_x(self.font.getsize(f" {attr.title()}")[0])
                        attribute_final = f" {stat.text[attr]}"\
                                          f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                    else:
                        d.text(cur.pos, f" {stat.text[attr]}", font=self.font, fill=self.prop_desc)
                        cur.move_x(self.font.getsize(f" {stat.text[attr]}")[0])
                        attribute_final = f" {attr.title()}"\
                                          f"{'' if list(stat.text.keys())[-1] == attr else ','}"
                    d.text(cur.pos, attribute_final, font=self.font)
                    cur.move_x(self.font.getsize(attribute_final)[0])
                cur.move_y(self.font.getsize(stat.title)[1])
                cur.reset()
                self.last_action = ""
            elif stat.title == "Lore":
                for line in stat.text:
                    text = line
                    cur.move_y(2 if self.last_action == "Separator" else 4)
                    cur.move_x((self.font.getsize(text)[0]//2)*-1)
                    d.text(cur.pos, text, fill=stat.color, font=self.font)
                    cur.move_y(self.font.getsize(text)[1])
                    cur.reset()
                    self.last_action = ""
            else:
                text = f"{stat.title}{stat.text}"
                cur.move_y(2 if self.last_action == "Separator" else 4)
                cur.move_x((self.font.getsize(text)[0]//2)*-1)
                if ':' in stat.title:
                    print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=self.prop_desc, font=self.font)
                    cur.move_x(self.font.getsize(stat.title)[0])
                    d.text(cur.pos, stat.text, fill=stat.color, font=self.font)
                else:
                    print(stat.title, cur.pos, stat.color)
                    d.text(cur.pos, stat.title, fill=stat.color, font=self.font)
                cur.move_y(self.font.getsize(stat.title)[1])
                cur.reset()
                self.last_action = ""

        item.save('test.png')
