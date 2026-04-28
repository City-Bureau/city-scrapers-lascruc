"""
Spider factory for City of Anthony NM scrapers.

Each spider pulls from two sources:
  Primary   https://www.cityofanthonynm.gov/AgendaCenter
            All past meetings with agendas, minutes, and media.
  Secondary https://www.cityofanthonynm.gov/calendar.aspx?CID=<calendar_cid>
            Future-only meetings (no documents). Used by both spiders via
            calendar_cid (BOT=23, P&Z=27).

AgendaCenter category IDs:
    2   Planning & Zoning Commission
    3   Board of Trustees
"""

from datetime import time as dt_time

from city_scrapers_core.constants import BOARD, COMMISSION

from city_scrapers.mixins.lascruc_anthony_city import LascrucAnthonyCityMixin

spider_configs = [
    {
        "class_name": "LascrucAnthonyCityBotSpider",
        "name": "lascruc_anthony_city_bot",
        "agency": "City of Anthony NM Board of Trustees",
        "cat_ids": [3],
        "classification": BOARD,
        "calendar_cid": 23,
        "start_time": dt_time(18, 0),
        "location": {
            "name": "Court Chambers",
            "address": "820 Highway 478 Anthony, NM 88021",
        },
    },
    {
        "class_name": "LascrucAnthonyCityPzSpider",
        "name": "lascruc_anthony_city_pz",
        "agency": "City of Anthony NM Planning & Zoning Commission",
        "cat_ids": [2],
        "classification": COMMISSION,
        "calendar_cid": 27,
        "start_time": dt_time(18, 30),
        "location": {
            "name": "Council Chambers",
            "address": "820 Highway 478 Anthony, NM 88021",
        },
    },
]


def _create_spiders():
    for config in spider_configs:
        class_name = config["class_name"]
        if class_name not in globals():
            attrs = {k: v for k, v in config.items() if k != "class_name"}
            spider_class = type(class_name, (LascrucAnthonyCityMixin,), attrs)
            globals()[class_name] = spider_class


_create_spiders()
