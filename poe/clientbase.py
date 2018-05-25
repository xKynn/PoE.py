import json
import os

from .models import Item
from .models import Weapon
from .models import Armour
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
            'tables': "skill_levels,skill",
            'join_on': "skill_levels._pageName=skill._pageName",
            'fields': f"{','.join(self.valid_gem_filters)},"
                      "skill_levels._pageName=name".replace(',stat_text', ',skill.stat_text')
                      .replace('quality_stat_text', 'skill.quality_stat_text'),
            'where': where_str,
            'group_by': 'skill_levels._pageName'
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

    def item_list_gen(self, data, req=None, url=None):
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
            else:
                stats = None
                i = Item
            drops = ItemDrop(item['drop enabled'], item['drop level'],
                             item['drop level maximum'], item['drop leagues'],
                             item['drop areas'], item['drop text'])
            req = Requirements(item['required dexterity'], item['required strength'],
                               item['required intelligence'], item['required level'])

            item = i(item['base item'], item['class'], item['name'],
                     item['rarity'], (item['size x'], item['size y']), drops, req,
                     item['flavour text'], item['help text'], self.bool_(item['is corrupted']),
                     self.bool_(item['is relic']), item['alternate art inventory icons'],
                     item['quality'], item['implicit stat text'], item['explicit stat text'], stats)

            final_list.append(item)
        return final_list