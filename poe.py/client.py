import requests

from .clientbase import ClientBase
from .exceptions import RequestException
from .exceptions import NotFoundException
from .exceptions import ServerException
from .models import Item
from .models import ItemDrop
from .models import Requirements


class Client(ClientBase):
    def __init__(self, session: requests.Session=None):
        self.session = session or requests.Session()
        self.base_url = "https://pathofexile.gamepedia.com/api.php"

    def request_gen(self, url, params=None, session=None):
        sess = session or self.session
        params['action'] = 'cargoquery'
        params['format'] = 'json'
        with sess.get(url, params=params) as req:
            try:
                resp = req.json()
            except (requests.Timeout, requests.ConnectionError):
                raise RequestException(req, {})

            if 300 > req.status_code >= 200:
                return resp
            elif req.status_code == 404:
                raise NotFoundException(req, resp)
            elif req.status_code > 500:
                raise ServerException(req, resp)
            else:
                raise RequestException(req, resp)

    def get_items(self, where: dict):
        where_params = []
        for key, val in where.items():
            if key.lower() not in self.valid_item_filters:
                print(f"WARNING: {key} is not a valid filter, continuing without it.")
                del where[key]
                continue
            where_params.append(f'{key} LIKE "%{val}%"')
        where_str = " AND ".join(where_params)
        params = {
            'tables': "items",
            'fields': f"{','.join(self.valid_item_filters)},_pageName=name",
            'where': where_str
        }
        data = self.request_gen(self.base_url, params=params)
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


