from city_scrapers.mixins.lascruc_dona_ana_county import LascrucDonaAnaCountySpiderMixin

# list of agencies
# "BOCC Agendas" id = 26
# "Planning and Zoning" id = 27
# "Labor Management Relations" = id 30
# "Airport Advisory Board" id = 31
# "Development Review Committee" id = 29
# "County ADA Advisory Board" id =
# "Compliance Office" id = https://www.donaana.gov/government/agendas/compliance_office.php # noqa

spider_configs = [
    {
        "class_name": "LascrucDonaAnaBoardOfCountyCommissionersSpider",
        "name": "lascruc_dona_ana_county_board_of_county_commissioners",
        "agency": "Board of County Commissioners",
        "category_id": 26,
    },
    {
        "class_name": "LascrucDonaAnaPlanningAndZoningSpider",
        "name": "lascruc_dona_ana_county_planning_and_zoning",
        "agency": "Planning and Zoning",
        "category_id": 27,
    },
    {
        "class_name": "LascrucDonaAnaLaborManagementRelationsSpider",
        "name": "lascruc_dona_ana_county_labor_management_relations",
        "agency": "Labor Management Relations",
        "category_id": 30,
    },
    {
        "class_name": "LascrucDonaAnaAirportAdvisoryBoardSpider",
        "name": "lascruc_dona_ana_county_airport_advisory_board",
        "agency": "Airport Advisory Board",
        "category_id": 31,
    },
    {
        "class_name": "LascrucDonaAnaDevelopmentReviewCommitteeSpider",
        "name": "lascruc_dona_ana_county_development_review_committee",
        "agency": "Development Review Committee",
        "category_id": 29,
    },
    {
        "class_name": "LascrucDonaAnaCountyADAAdvisoryBoardSpider",
        "name": "lascruc_dona_ana_county_ada_advisory_board",
        "agency": "County ADA Advisory Board",
        "category_id": 28,
    },
    {
        "class_name": "LascrucDonaAnaComplianceOfficeSpider",
        "name": "lascruc_dona_ana_county_compliance_office",
        "agency": "Compliance Office",
        "compliance_url": "https://www.donaana.gov/government/agendas/compliance_office.php",  # noqa
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
                (LascrucDonaAnaCountySpiderMixin,),
                attrs,
            )

            globals()[class_name] = spider_class


# Create all spider classes at module load
create_spiders()
