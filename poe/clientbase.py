import json
import os
import html

from .models import Item
from .models import Weapon
from .models import Armour
from .models import Prophecy
from .models import Gem
from .models import ItemDrop
from .models import Requirements


class ClientBase:
    _dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'valid_filters.json')
    with open(_dir) as f:
        filters = json.load(f)

    valid_item_filters = filters['item']

    valid_gem_filters = filters['gem']

    valid_gem_level_filters = filters['gem_levels']

    valid_weapon_filters = filters['weapon']

    valid_armour_filters = filters['armour']

    operators = ['>', '<', '=']

    @staticmethod
    def extract_cargoquery(data):
        extracted = []
        #print(data)
        for item in data['cargoquery']:
            extracted.append(item['title'])
        return extracted

    @staticmethod
    def bool_(val):
        return bool(int(val))

    def _param_gen(self, where, filters):
        where_params = []
        for key, val in where.items():
            #if key.lower() not in filters:
             #   print(f"WARNING: {key} is not a valid filter, continuing without it.")
              #  continue
            if 'skill_id' in filters and key == 'name':
                key = 'skill_levels._pageName'
            if val[0] in self.operators:
                where_params.append(f'{key}{val}')
            else:
                where_params.append(f'{key}%20LIKE%20%22{val}%22')
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

    def item_param_gen(self, where):
        where_str = self._param_gen(where, self.valid_item_filters)
        params = {
            'tables': "items",
            'fields': f"{','.join(self.valid_item_filters)},_pageName=name",
            'where': where_str
        }
        return params
    @staticmethod
    def get_image_url(filename, req):
        query_url = "https://pathofexile.gamepedia.com/api.php?action=query"
        param = {
                'titles': filename,
                'prop': 'imageinfo&',
                'iiprop': 'url'
            }
        dat = req(query_url, param)
        return dat['query']['pages'][list(dat['query']['pages'].keys())[0]]['imageinfo'][0]['url']

    def get_gems(self, where: dict, req, url):
        params = self.gem_param_gen(where)
        data = req(url, params=params)
        result_list = self.extract_cargoquery(data)
        final_list = []
        for gem in result_list:
            vendor_params = {
                'tables': "vendor_rewards",
                'fields': "act,classes",
                'where': f'''reward=%22{gem['name']}%22'''
            }
            vendors_raw = req(url, params=vendor_params)
            vendors = self.extract_cargoquery(vendors_raw)
            for act in vendors:
                act['classes'] = act['classes'].replace('�', ', ')
            stats_params = {
                'tables': "skill_levels",
                'fields': ','.join(self.valid_gem_level_filters),
                'where': f'''_pageName=%22{gem['name']}%22'''
            }
            stats_raw = req(url, params=stats_params)
            stats_list = self.extract_cargoquery(stats_raw)
            stats = {}
            print(gem['has percentage mana cost'], gem['has reservation mana cost'])
            if int(gem['has percentage mana cost']) or int(gem['has reservation mana cost']):
                aura = True
            else:
                aura = False
            for stats_dict in stats_list:
                stats[int(stats_dict['level'])] = stats_dict
            requirements = Requirements(stats[1]['dexterity requirement'], stats[1]['strength requirement'],
                                        stats[1]['intelligence requirement'], stats[1]['level requirement'])
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
    def item_list_gen(self, data, req=None, url=None, where=None):
        result_list = self.extract_cargoquery(data)
        final_list = []
        for item in result_list:
            if 'weapon' in item['tags']:
                params = {
                    'tables': 'weapons',
                    'fields': ','.join(self.valid_weapon_filters),
                    'where': f'_pageName="{item["name"]}"'
                }
                data = req(url, params)
                stats = self.extract_cargoquery(data)[0]
                i = Weapon
            elif 'armour' in item['tags']:
                params = {
                    'tables': 'armours',
                    'fields': ','.join(self.valid_armour_filters),
                    'where': f'_pageName="{item["name"]}"'
                }
                data = req(url, params)
                stats = self.extract_cargoquery(data)[0]
                i = Armour
            elif 'gem' in item['tags']:
                current_item = self.get_gems({'name': item['name']}, req, url)[0]
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
            print(item['inventory icon'])
            if 'gem' not in item['tags']:
                image_url = self.get_image_url(item['inventory icon'], req)
                drops = ItemDrop(item['drop enabled'], item['drop level'],
                                 item['drop level maximum'], item['drop leagues'],
                                 item['drop areas'], item['drop text'])
                requirements = Requirements(item['required dexterity'], item['required strength'],
                                   item['required intelligence'], item['required level'])

                current_item = i(item['base item'], item['class'], item['name'],
                                 item['rarity'], (item['size x'], item['size y']), drops, requirements,
                                 item['flavour text'], item['help text'], self.bool_(item['is corrupted']),
                                 self.bool_(item['is relic']), item['alternate art inventory icons'],
                                 item['quality'], item['implicit stat text'], item['explicit stat text'],
                                 item['tags'], image_url, stats)

            final_list.append(current_item)
        return final_list