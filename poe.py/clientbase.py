import json

from .models import Item
from .models import ItemDrop
from .models import Requirements


class ClientBase:
    with open('valid_filters.json') as f:
        filters = json.load(f)

    valid_item_filters = filters['item']

    valid_gem_filters = filters['gem']

    valid_gem_level_filters = filters['gem_levels']

    @staticmethod
    def extract_cargoquery(data):
        extracted = []
        for item in data['cargoquery']:
            extracted.append(item['title'])
        return extracted

    @staticmethod
    def bool_(val):
        return bool(int(val))

    @staticmethod
    def _param_gen(where, filters):
        where_params = []
        for key, val in where.items():
            if key.lower() not in filters:
                print(f"WARNING: {key} is not a valid filter, continuing without it.")
                del where[key]
                continue
            if key == 'active_skill_name':
                key = 'skill_levels._pageName'
            where_params.append(f'{key} LIKE "%{val}%"')
        where_str = " AND ".join(where_params)
        return where_str

    def gem_param_gen(self, where):

        where_str = self._param_gen(where, self.valid_gem_filters)
        params = {
            'tables': "skill_levels,skill",
            'join_on': "skill_levels._pageName=skill._pageName",
            'fields': f"{','.join(self.valid_gem_filters)},"
                      "skill_levels._pageName=name",
            'where': where_str
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

    def item_list_gen(self, data):
        result_list = self.extract_cargoquery(data)
        final_list = []
        for item in result_list:
            drops = ItemDrop(item['drop_enabled'], item['drop_level'],
                             item['drop_level_maximum'], item['drop_leagues'],
                             item['drop_areas'], item['drop_text'])
            req = Requirements(item['required_dexterity'], item['required_strength'],
                               item['required_intelligence'], item['required_level'])
            item = Item(item['base'], item['class'], item['name'],
                        item['rarity'], item['size_x'],
                        (item['size_x'], item['size_y']), drops, req,
                        item['flavour_text'], item['help_text'], self.bool_(item['is_corrupted']),
                        self.bool_(item['is_relic']), item['alternate_art_inventory_icons'],
                        item['quality'], item['implicit_stat_text'], item['explicit_stat_text'])

            final_list.append(item)
        return final_list