import requests
import time
import json
if __name__ == "__main__":
    counter = 0
    l = {"names": []}
    while 1:
        try:
            r = requests.get(f"https://pathofexile.gamepedia.com/api.php?action=cargoquery&tables=items&fields=_pageName=name&format=json&order_by=name&limit=500&offset={counter}")
            j = r.json()
            if not j['cargoquery']:
                break
            for item in j['cargoquery']:
                l["names"].append(item["title"]["name"])
            counter += 500
            print("Sleeping, counter is at ", counter)
            time.sleep(2)
        except:
            break
    with open("items.json", "w") as f:
        json.dump(l, f)