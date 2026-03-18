"""
Spider factory for City of Anthony NM AgendaCenter portal.

Dynamically creates one spider per board/commission scraped from:
https://www.cityofanthonynm.gov/AgendaCenter

Category IDs are taken from the AgendaCenter portal:
    2   Planning & Zoning Commission
    3   Board of Trustees
"""

from city_scrapers_core.constants import BOARD, COMMISSION

from city_scrapers.mixins.lascruc_anthony_city import LascrucAnthonyCityMixin

spider_configs = [
    {
        "class_name": "LascrucAnthonyCityBotSpider",
        "name": "lascruc_anthony_city_bot",
        "agency": "City of Anthony NM Board of Trustees",
        "cat_ids": [3],
        "classification": BOARD,
    },
    {
        "class_name": "LascrucAnthonyCityPzSpider",
        "name": "lascruc_anthony_city_pz",
        "agency": "City of Anthony NM Planning & Zoning Commission",
        "cat_ids": [2],
        "classification": COMMISSION,
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
