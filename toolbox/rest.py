# 
# Author    : Manuel Bernal Llinares
# Project   : trackhub-creator
# Timestamp : 03-07-2017 13:36
# ---
# © 2017 Manuel Bernal Llinares <mbdebian@gmail.com>
# All rights reserved.
# 

"""
Toolbox related to REST services
"""

import requests


def make_rest_request(url):
    response = requests.get(url, headers={"Content-Type": "application/json"})
    if not response.ok:
        response.raise_for_status()
    return response.json()


if __name__ == '__main__':
    print("ERROR: This script is part of a pipeline collection and it is not meant to be run in stand alone mode")
