import html
import json
import os

from bs4 import BeautifulSoup as Soup

from .models import Armour
from .models import DivCard
from .models import Gem
from .models import Item
from .models import ItemDrop
from .models import PassiveSkill
from .models import Prophecy
from .models import Requirements
from .models import Weapon
from .utils import reg


class ClientBase:
    _dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'valid_filters.json')
    with open(_dir) as f:
        filters = json.load(f)

    valid_item_filters = filters['item']
    valid_gem_filters = filters['gem']
    valid_gem_level_filters = filters['gem_levels']
    valid_weapon_filters = filters['weapon']
    valid_armour_filters = filters['armour']
    valid_passive_filters = filters['passives']
    # No other way to tell if an item is an elder or shaper unique other than locally storing it at the moment
    shaper_items = filters['shaper']
    elder_items = filters['elder']
    operators = ['>', '<', '=']

    @staticmethod
    def extract_cargoquery(data):
        extracted = []
        for item in data['cargoquery']:
            extracted.append(item['title'])
        return extracted

    @staticmethod
    def bool_(val):
        return bool(int(val))

    def _param_gen(self, where, filters):
        where_params = []
        for key, val in where.items():
            if 'skill_id' in filters and key == 'name':
                key = 'skill_levels._pageName'
            if val[0] in self.operators:
                where_params.append(f'{key}{val}')
            else:
                where_params.append(f'{key} LIKE "{val}"')
        where_str = " AND ".join(where_params)
        return where_str

    def gem_param_gen(self, where):
        where_str = self._param_gen(where, self.valid_gem_filters)
        params = {
            'tables': "skill_levels,skill,items,skill_gems",
            'join_on': "skill_levels._pageName=skill._pageName,skill_levels._pageName=items._pageName,skill_levels._pageName=skill_gems._pageName",
            'fields': f"{','.join(self.valid_gem_filters)},skill_levels._pageName=name,items.inventory_icon, skill_gems.gem_tags, items.tags",
            'where': where_str,
            'group_by': 'name'
        }
        return params

    def item_param_gen(self, where, limit):
        where_str = self._param_gen(where, self.valid_item_filters)
        params = {
            'tables': "items",
            'fields': f"{','.join(self.valid_item_filters)},_pageName=name",
            'where': where_str,
            'order_by': "name"
        }
        if limit:
            params['limit'] = str(limit)
        return params

    def passive_param_gen(self, where, limit):
        where_str = self._param_gen(where, self.valid_passive_filters)
        params = {
            'tables': "passive_skills",
            'fields': f"{','.join(self.valid_passive_filters)}",
            'where': where_str
        }
        if limit:
            params['limit'] = str(limit)
        return params

    def passive_list_gen(self, data, req=None):
        result_list = self.extract_cargoquery(data)
        final_list = []
        for passive in result_list:
            asc_class = passive.get("ascendancy class", None)
            flavor_text = passive.get("flavour text", None)
            icon = self.get_image_url(passive['icon'], req)
            is_keystone = bool(int(passive.get("is keystone", None)))
            is_notable = bool(int(passive.get("is notable", None)))
            name = passive.get("name", None)
            reminder_text = passive.get("reminder text", None)
            stat_text = passive.get("stat text", None)
            int_id = passive.get("int id", None)
            final_list.append(PassiveSkill(
                asc_class, flavor_text, icon, is_keystone, is_notable, name, reminder_text, stat_text, int_id
            ))
        return final_list

    @staticmethod
    def get_image_url(filename, req):
        query_url = "https://pathofexile.gamepedia.com/api.php?action=query"
        param = {
            'titles': filename,
            'prop': 'imageinfo&',
            'iiprop': 'url'
        }
        dat = req(query_url, param)
        ic = dat['query']['pages'][list(dat['query']['pages'].keys())[0]].get('imageinfo', None)
        return ic[0]['url'] if ic else ic

    def get_gems(self, where: dict, req, url):
        params = self.gem_param_gen(where)
        data = req(url, params=params)
        final_list = []

        result_list = self.extract_cargoquery(data)
        for gem in result_list:
            vendor_params = {
                'tables': "vendor_rewards",
                'fields': "act,classes",
                'where': f'''reward="{gem['name']}"'''
            }
            vendors_raw = req(url, params=vendor_params)
            vendors = self.extract_cargoquery(vendors_raw)

            for act in vendors:
                act['classes'] = act['classes'].replace('�', ', ')
            stats_params = {
                'tables': "skill_levels",
                'fields': ','.join(self.valid_gem_level_filters),
                'where': f'''_pageName="{gem['name']}"'''
            }
            stats_raw = req(url, params=stats_params)
            print(stats_raw)
            stats_list = self.extract_cargoquery(stats_raw)
            stats = {}

            if int(gem['has percentage mana cost']) or int(gem['has reservation mana cost']):
                aura = True
            else:
                aura = False

            for stats_dict in stats_list:
                stats[int(stats_dict['level'])] = stats_dict

            # Fix for broken skill_levels table.
            # requirements = Requirements(
            #     '-', '-',
            #     '-', '-'
            # )

            requirements = Requirements(
                stats[1]['dexterity requirement'], stats[1]['strength requirement'],
                stats[1]['intelligence requirement'], stats[1]['level requirement']
            )

            inv_icon = self.get_image_url(gem['inventory icon'], req)
            if gem['skill icon']:
                skill_icon = self.get_image_url(gem['skill icon'], req)
            else:
                skill_icon = None

            gem = Gem(gem["skill id"], gem["cast time"], gem["description"],
                      gem["name"], gem["item class restriction"], gem["stat text"],
                      gem["quality stat text"], gem["radius"],
                      gem["radius description"], gem["radius secondary"],
                      gem["radius secondary description"], gem["radius tertiary"],
                      gem["radius tertiary description"], skill_icon,
                      gem["skill screenshot"], inv_icon, gem['gem tags'], gem['tags'], stats,
                      aura, vendors, requirements)
            final_list.append(gem)
        return final_list

    def item_list_gen(self, data, req=None, url=None):
        result_list = self.extract_cargoquery(data)
        final_list = []
        influences = []
        for item in result_list:
            if item['name'] in self.shaper_items:
                influences.append("shaper")
            if item['name'] in self.elder_items:
                influences.append("elder")
            if 'weapon' in item['tags'].split(','):
                params = {
                    'tables': 'weapons',
                    'fields': ','.join(self.valid_weapon_filters),
                    'where': f'_pageName="{item["name"]}"'
                }
                data = req(url, params)
                stats = self.extract_cargoquery(data)[0]
                i = Weapon

            elif 'armour' in item['tags'].split(','):
                if 'shield' in item['tags'].split(','):
                    params = {
                        'tables': 'armours, shields',
                        'join_on': 'armours._pageName=shields._pageName',
                        'fields': f"{','.join(self.valid_armour_filters)},block_range_average",
                        'where': f'shields._pageName="{item["name"]}"'
                    }

                else:
                    params = {
                        'tables': 'armours',
                        'fields': ','.join(self.valid_armour_filters),
                        'where': f'_pageName="{item["name"]}"'
                    }
                # Only extra stat a shield has from other armours is the block chance
                # So I didn't add it to a filter key and blah blah
                data = req(url, params)
                stats = self.extract_cargoquery(data)[0]
                i = Armour

            elif 'gem' in item['tags'].split(','):
                current_item = self.get_gems({'name': item['name']}, req, url)[0]

            elif 'divination_card' in item['tags'].split(','):
                params = {
                    'tables': 'divination_cards, stackables',
                    'join_on': 'divination_cards._pageName=stackables._pageName',
                    'fields': 'card_art, stack_size',
                    'where': f'divination_cards._pageName="{item["name"]}"'
                }
                data = self.extract_cargoquery(req(url, params))[0]
                card_art = self.get_image_url(data['card art'], req)
                soup = Soup(html.unescape(item['html']))
                div_data = soup.select_one('span.divicard-reward span span')

                if "[[Corrupted]]" in item['html']:
                    item['is corrupted'] = True

                # FIXME: unresolved attribute
                reward_flavour = div_data.attrs['class'][1][1:]
                if reward_flavour == 'currency':
                    reward_flavour = 'normal'

                # FIXME: unresolved attribute
                matches = reg.findall(div_data.text)
                if len(matches) > 1:
                    reward = matches[1].split('|')[1].strip(']]')
                elif len(matches) == 1:
                    reward = matches[0].split('|')[1].strip(']]')
                else:
                    # FIXME: unresolved attribute
                    reward = div_data.text

                stats = {
                    'card_art': card_art,
                    'stack_size': data['stack size'],
                    'reward_flavor': reward_flavour,
                    'reward': reward
                }
                i = DivCard

            elif item['base item'] == "Prophecy":
                params = {
                    'tables': 'prophecies',
                    'fields': 'objective, prediction_text, seal_cost',
                    'where': f'_pageName="{item["name"]}"'
                }
                data = req(url, params)
                stats = self.extract_cargoquery(data)[0]
                i = Prophecy
            else:
                stats = None
                i = Item

            if 'gem' not in item['tags'].split(','):
                print(item['inventory icon'])
                image_url = self.get_image_url(item['inventory icon'], req)
                drops = ItemDrop(item['drop enabled'], item['drop level'],
                                 item['drop level maximum'], item['drop leagues'],
                                 item['drop areas'], item['drop text'])
                requirements = Requirements(
                    item['required dexterity'], item['required strength'],
                    item['required intelligence'], item['required level']
                )

                # FIXME: referenced before assignment
                current_item = i(
                    item['base item'], item['class'], item['name'],
                    item['rarity'], (item['size x'], item['size y']), drops, requirements,
                    item['flavour text'], item['help text'], self.bool_(item['is corrupted']),
                    self.bool_(item['is relic']), item['alternate art inventory icons'],
                    item['quality'], item['implicit stat text'], item['explicit stat text'],
                    # FIXME: referenced before assignment
                    item['tags'], image_url, influences, stats
                )

            # FIXME: referenced before assignment
            final_list.append(current_item)
        return final_list
