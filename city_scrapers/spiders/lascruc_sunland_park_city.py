from city_scrapers.mixins.lascruc_sunland_park_city import LasCrucesSunlandParkCityMixin

spider_configs = [
    {
        "class_name": "LascrucSunlandParkCityCouncilSpider",
        "name": "lascruc_sunland_park_city_council",
        "agency": "Sunland Park City Council",
        "meeting_type_label": "City Council Meetings",
    },
    {
        "class_name": "LascrucSunlandParkPlanningAndZoningSpider",
        "name": "lascruc_sunland_park_planning_and_zoning",
        "agency": "Sunland Park Planning and Zoning Commission",
        "meeting_type_label": "Planning & Zoning Meetings",
    },
]


def create_spiders():
    """
    Dynamically create spider classes using the spider_configs list
    and register them in the global namespace.
    """
    for config in spider_configs:
        class_name = config["class_name"]

        if class_name not in globals():
            attrs = {k: v for k, v in config.items() if k != "class_name"}

            spider_class = type(
                class_name,
                (LasCrucesSunlandParkCityMixin,),
                attrs,
            )

            globals()[class_name] = spider_class


# Create all spider classes at module load
create_spiders()
