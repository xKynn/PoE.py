#!/usr/bin/env python3

import poe.client

client = poe.client.Client()
items = client.find_items({'name': 'freezing pulse'})
for item in items:
	print(item.__dict__)
