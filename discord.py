"""Interaction with Discord API

This module allows for interaction with the Discord API
"""

from urllib.request import urlopen
from urllib.request import Request
from urllib.error import HTTPError

import urllib
import json

import time
import math

API_BASE = 'https://discordapp.com/api/'
"""The base URL for discord api requests"""

USER_AGENT = 'python urllib3 reddit u/tjstretchalot'
"""The user agent for interacting with discord"""

def get_invite_from_code(code):
    """Fetch the invite object given just its code.

    Args:
        code (str): The invite code, unique to the invitation

    Returns:
        A tuple of three values.

        The first is a bool that indicates whether or not we successfully
        fetched the invite object.

        The second is a bool that is True if we did not successfully fetch the
        invite object but this may be a temporary issue, and False in all other
        situations.

        The third is a dictionary of the fetched invite object, if successful,
        and None in other cases.

        Example Invite Object:
            {
                "code": "0vCdhLbwjZZTWZLD",
                "guild": {
                    "id": "165176875973476352",
                    "name": "CS:GO Fraggers Only",
                    "splash": null,
                    "icon": null,
                    "features": {}
                },
                "channel": {
                    "id": "165176875973476352",
                    "name": "illuminati",
                    "type": 0
                }
            }
    """
    global API_BASE
    global USER_AGENT

    req = Request(f'{API_BASE}invites/{code}')
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('User-Agent', USER_AGENT)
    try:
        with urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if data['code'] == '10006':
                # This is a special code to indicate the link just expired
                return False, False, None
            return True, False, data
    except HTTPError as err:
        if err.code == 404:
            return False, False, None
        if err.code == 429:
            if 'X-RateLimit-Reset' in err.headers:
                reset_time = err.headers['X-RateLimit-Reset']
                time_to_wait = math.ceil(reset_time - time.time())
                if time_to_wait <= 0:
                    print(f'got ratelimited when checking {code} but the reset time is in the past, trying again')
                    return False, True, None
                print(f'got ratelimited when checking {code}, need to wait {time_to_wait} seconds before trying again')
                time.sleep(time_to_wait)
                return False, True, None

        print(f'Got error code {err.code} in HTTPResponse for code {code}')
        return False, True, None
