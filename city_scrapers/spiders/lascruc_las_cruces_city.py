"""
This file dynamically creates spider classes for the spider factory mixin that agencies use. # noqa
"""

from city_scrapers.mixins.lascruc_las_cruces_city import LasCrucesMixin

spider_configs = [
    {
        "class_name": "LasCrucesAgendaSettingMeeting",
        "name": "las_cruces_agenda_setting_meeting",
        "agency": "Agenda Setting Meeting",
        "id": "las_cruces_agenda_setting_meeting",
    },
    {
        "class_name": "LasCrucesASCMV",
        "name": "las_cruces_ascmv",
        "agency": "ASCMV",
        "id": "las_cruces_ascmv",
    },
    {
        "class_name": "LasCrucesCIAC",
        "name": "las_cruces_ciac",
        "agency": "CIAC",
        "id": "las_cruces_ciac",
        "name_prefixes": ["CIAC", "Work Session - CIAC"],
    },
    {
        "class_name": "LasCrucesCityCouncil",
        "name": "las_cruces_city_council",
        "agency": "City Council",
        "id": "las_cruces_city_council",
        "name_prefixes": ["City Council", "Special City Council"],
    },
    {
        "class_name": "LasCrucesClosedMeeting",
        "name": "las_cruces_closed_meeting",
        "agency": "Closed Meeting",
        "id": "las_cruces_closed_meeting",
    },
    {
        "class_name": "LasCrucesPlanningZoning",
        "name": "las_cruces_planning_zoning",
        "agency": "Planning & Zoning",
        "id": "las_cruces_planning_zoning",
    },
    {
        "class_name": "LasCrucesPressConferencesForums",
        "name": "las_cruces_press_conferences_forums",
        "agency": "Press Conferences & Forums",
        "id": "las_cruces_press_conferences_forums",
    },
    {
        "class_name": "LasCrucesPublicHearing",
        "name": "las_cruces_public_hearing",
        "agency": "Public Hearing",
        "id": "las_cruces_public_hearing",
    },
    {
        "class_name": "LasCrucesStateOfTheCityAddress",
        "name": "las_cruces_state_of_the_city_address",
        "agency": "State of the City Address",
        "id": "las_cruces_state_of_the_city_address",
    },
    {
        "class_name": "LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting",
        "name": "las_cruces_tax_increment_development_district_board_meeting",
        "agency": "Tax Increment Development District Board Meeting",
        "id": "las_cruces_tax_increment_development_district_board_meeting",
    },
    {
        "class_name": "LasCrucesUtilities",
        "name": "las_cruces_utilities",
        "agency": "Utilities",
        "id": "las_cruces_utilities",
    },
    {
        "class_name": "LasCrucesWorkSession",
        "name": "las_cruces_work_session",
        "agency": "Work Session",
        "id": "las_cruces_work_session",
        "name_prefixes": ["Work Session", "Joint Work Session", "Special Work Session"],
        "name_excludes": ["Work Session - CIAC"],
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
            # Build attributes dict without class_name to avoid duplication.
            # We make sure that the class_name is not already in the global namespace
            # Because some scrapy CLI commands like `scrapy list` will inadvertently
            # declare the spider class more than once otherwise
            attrs = {k: v for k, v in config.items() if k != "class_name"}

            # Dynamically create the spider class
            spider_class = type(
                class_name,
                (LasCrucesMixin,),
                attrs,
            )

            globals()[class_name] = spider_class


# Create all spider classes at module load
create_spiders()
