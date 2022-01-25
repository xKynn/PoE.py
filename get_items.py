import json
import html
import time

import requests

if __name__ == "__main__":
    counter = 0
    items = {"names": []}
    while True:
        try:
            url = f"https://poewiki.net/w/api.php?action=cargoquery&tables=items"
            url += f"&fields=_pageName=name&format=json&order_by=name&limit=500&offset={counter}"
            response = requests.get(url)
            response_json = response.json()
            if not response_json['cargoquery']:
                break
            for item in response_json['cargoquery']:
                items["names"].append(item["title"]["name"].replace("&quot;", ""))
            counter += 500
            print("Sleeping, counter is at ", counter)
            time.sleep(2)
        except Exception:
            break

    with open("items.json", "w") as file:
        json.dump(items, file)
