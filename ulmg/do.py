import os

import ujson as json
import requests


def base_request(*args, **kwargs):
    base_url = "https://api.digitalocean.com/v2/"
    do_token = os.environ.get('DIGITAL_OCEAN_ACCESS_TOKEN')

    app = kwargs.get('app')

    if do_token and app:
        headers = {}
        headers['Content-Type'] = "application/json"
        headers['Authorization'] = f"Bearer {do_token}"

        r = requests.get(f"{base_url}{app}", headers=headers)
        return r.json()