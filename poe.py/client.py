import requests

from .clientbase import ClientBase
from .exceptions import RequestException
from .exceptions import NotFoundException
from .exceptions import ServerException
from .models import Item
from .models import ItemDrop
from .models import Requirements
from .models import Gem


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
        params = self.item_param_gen(where)
        data = self.request_gen(self.base_url, params=params)
        return self.item_list_gen(data)

    def get_gem(self, where: dict):
        params = self.gem_param_gen(where)
        result_list = self.extract_cargoquery(params)
        final_list = []
        for gem in result_list:
            vendor_params = {
                'tables': "vendor_rewards",
                'fields': "act,classes",
                'where': f'''reward="{gem['name']}"'''
            }
            vendors_raw = self.request_gen(self.base_url, params=vendor_params)
            vendors = self.extract_cargoquery(vendors_raw)
            stats_params = {
                'tables': "skill_levels",
                'fields': ','.join(self.valid_gem_level_filters),
                'where': f'''_pageName="{gem['name']}"'''
            }
            stats_raw = self.request_gen(self.base_url, params=stats_params)
            stats_list = self.extract_cargoquery(stats_raw)
            stats = {}
            for stats_dict in stats_list:
                stats[int(stats_dict['level'])] = stats_dict
            gem = Gem(gem["skill_id"], gem["cast_time"], gem["description"],
                      gem["name"], gem["item_class_restriction"], gem["stat_text"],
                      gem["quality_stat_text"], gem["radius"],
                      gem["radius_description"], gem["radius_secondary"],
                      gem["radius_secondary_description"], gem["radius_tertiary"],
                      gem["radius_tertiary_description"], gem["skill_icon"],
                      gem["skill_screenshot"], stats,
                      True if int(gem['has_percentage_mana_cost']) else False,
                      vendors)
            final_list.append(gem)
        return final_list