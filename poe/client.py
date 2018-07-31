import urllib3

urllib3.disable_warnings()
import json

from .clientbase import ClientBase
from .exceptions import RequestException
from .exceptions import NotFoundException
from .exceptions import ServerException
from .models import Gem, Requirements


class Client(ClientBase):
    def __init__(self, pool: urllib3.PoolManager = None):
        self.pool = pool or urllib3.PoolManager()
        self.base_url = "https://pathofexile.gamepedia.com/api.php?action=cargoquery"
    def request_gen(self, url, params=None):
        http = self.pool
        params['format'] = 'json'
        final_url = f"{url}"
        for key, value in params.items():
            final_url = f"{final_url}&{key}={value.replace(' ', '%20')}"
        r = http.request('GET', final_url)
        # print(final_url)
        try:
            resp = json.loads(r.data.decode('utf-8'))
        except (urllib3.exceptions.TimeoutError, urllib3.exceptions.ConnectionError):
            raise RequestException(r, {})

        if 300 > r.status >= 200:
            return resp
        elif r.status == 404:
            raise NotFoundException(r, resp)
        elif r.status > 500:
            raise ServerException(r, resp)
        else:
            raise RequestException(r, resp)

    def get_items(self, where: dict):
        params = self.item_param_gen(where)
        data = self.request_gen(self.base_url, params=params)
        return self.item_list_gen(data, self.request_gen, self.base_url)

    def get_gems(self, where: dict):
        params = self.gem_param_gen(where)
        data = self.request_gen(self.base_url, params=params)
        result_list = self.extract_cargoquery(data)
        final_list = []
        for gem in result_list:
            vendor_params = {
                'tables': "vendor_rewards",
                'fields': "act,classes",
                'where': f'''reward=%22{gem['name']}%22'''
            }
            vendors_raw = self.request_gen(self.base_url, params=vendor_params)
            vendors = self.extract_cargoquery(vendors_raw)
            for act in vendors:
                act['classes'] = act['classes'].replace('�', ', ')
            stats_params = {
                'tables': "skill_levels",
                'fields': ','.join(self.valid_gem_level_filters),
                'where': f'''_pageName=%22{gem['name']}%22'''
            }
            stats_raw = self.request_gen(self.base_url, params=stats_params)
            stats_list = self.extract_cargoquery(stats_raw)
            stats = {}
            print(gem['has percentage mana cost'], gem['has reservation mana cost'])
            if int(gem['has percentage mana cost']) or int(gem['has reservation mana cost']):
                aura = True
            else:
                aura = False
            for stats_dict in stats_list:
                stats[int(stats_dict['level'])] = stats_dict
            req = Requirements(stats[1]['dexterity requirement'], stats[1]['strength requirement'],
                               stats[1]['intelligence requirement'], stats[1]['level requirement'])
            inv_icon = self.get_image_url(gem['inventory icon'], self.request_gen)
            if gem['skill icon']:
                skill_icon = self.get_image_url(gem['skill icon'], self.request_gen)
            else:
                skill_icon = None
            gem = Gem(gem["skill id"], gem["cast time"], gem["description"],
                      gem["name"], gem["item class restriction"], gem["stat text"],
                      gem["quality stat text"], gem["radius"],
                      gem["radius description"], gem["radius secondary"],
                      gem["radius secondary description"], gem["radius tertiary"],
                      gem["radius tertiary description"], skill_icon,
                      gem["skill screenshot"], inv_icon, gem['gem tags'], gem['tags'], stats,
                      aura, vendors, req)
            final_list.append(gem)
        return final_list

    def search(self, name: str):
        search_params = {
            'tables': 'skill, items',
            'join_on': 'skill._pageName=items._pageName',
            'fields': 'items._pageName=name,tags',
            'where': f'items._pageName%20LIKE%20%22{name}%%22'
        }
        results = self.extract_cargoquery(self.request_gen(self.base_url, params=search_params))
        fetched_results = []
        print(results)
        for result in results:
            if 'gem' in result['tags']:
                fetched_results.append(self.get_gems({'name': f'{result["name"]}'})[0])
            elif any(i_type in result['tags'] for i_type in ['ring', 'amulet', 'belt', 'armour']):
                fetched_results.append(self.get_items({'name': f'{name}%'})[0])
        return fetched_results
