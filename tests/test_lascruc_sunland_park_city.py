from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import CANCELLED, CITY_COUNCIL, COMMISSION, PASSED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.lascruc_sunland_park_city import (
    LascrucSunlandParkCityCouncilSpider,
    LascrucSunlandParkPlanningAndZoningSpider,
)

test_response = file_response(
    join(dirname(__file__), "files", "lascruc_sunland_park_city.html"),
    url="https://sunlandpark-nm.gov/city-clerk/#agenda",
)


@pytest.fixture
def council_items():
    with freeze_time("2026-03-30"):
        spider = LascrucSunlandParkCityCouncilSpider()
        return list(spider.parse(test_response))


@pytest.fixture
def pz_items():
    with freeze_time("2026-03-30"):
        spider = LascrucSunlandParkPlanningAndZoningSpider()
        return list(spider.parse(test_response))


# City Council Tests


def test_council_count(council_items):
    assert len(council_items) == 11


def test_council_title_closed_session(council_items):
    assert council_items[0]["title"] == "Closed Session"


def test_council_title_regular_meeting(council_items):
    assert council_items[1]["title"] == "Regular City Council Meeting"


def test_council_title_regular_meeting_agenda(council_items):
    assert council_items[4]["title"] == "Regular Meeting Agenda"


def test_council_title_cancellation(council_items):
    assert council_items[5]["title"] == "COUNCIL MEETING"


def test_council_title_special_meeting(council_items):
    assert council_items[8]["title"] == "Special Meeting Agenda"


def test_council_start_closed_session(council_items):
    assert council_items[0]["start"] == datetime(2026, 1, 7, 16, 0)


def test_council_start_regular_meeting_jan7(council_items):
    assert council_items[1]["start"] == datetime(2026, 1, 7, 18, 0)


def test_council_start_regular_meeting_jan20(council_items):
    assert council_items[2]["start"] == datetime(2026, 1, 20, 17, 30)


def test_council_start_cancellation(council_items):
    assert council_items[5]["start"] == datetime(2026, 2, 17, 0, 0)


def test_council_start_special_meeting(council_items):
    assert council_items[8]["start"] == datetime(2026, 3, 9, 9, 0)


def test_council_status_passed(council_items):
    assert council_items[0]["status"] == PASSED


def test_council_status_cancelled(council_items):
    assert council_items[5]["status"] == CANCELLED


def test_council_status_last_item_passed(council_items):
    assert council_items[10]["start"] == datetime(2026, 3, 17, 17, 30)
    assert council_items[10]["status"] == PASSED


def test_council_classification_city_council(council_items):
    assert council_items[1]["classification"] == CITY_COUNCIL


def test_council_classification_closed_session(council_items):
    assert council_items[0]["classification"] == CITY_COUNCIL


def test_council_links_with_video(council_items):
    assert council_items[1]["links"] == [
        {
            "href": "https://sunlandpark-nm.gov/wp-content/uploads/2026/01/01-07-2026-final-agenda.pdf",  # noqa
            "title": "Agenda",
        },
        {
            "href": "https://www.youtube.com/watch?v=45VqdOhG26w",
            "title": "Video",
        },
    ]


def test_council_links_without_video(council_items):
    assert council_items[0]["links"] == [
        {
            "href": "https://sunlandpark-nm.gov/wp-content/uploads/2026/01/1-07-26-Closed-session-agenda.pdf",  # noqa
            "title": "Agenda",
        },
    ]


def test_council_location(council_items):
    assert council_items[0]["location"] == {
        "name": "",
        "address": "",
    }


def test_council_time_notes(council_items):
    assert (
        council_items[0]["time_notes"]
        == "Please refer to the agenda for meeting location details"
    )  # noqa


def test_council_source(council_items):
    assert council_items[0]["source"] == "https://sunlandpark-nm.gov/city-clerk/#agenda"


def test_council_all_day(council_items):
    for item in council_items:
        assert item["all_day"] is False


def test_council_description(council_items):
    for item in council_items:
        assert item["description"] == ""


# Planning & Zoning Tests


def test_pz_count(pz_items):
    assert len(pz_items) == 6


def test_pz_title_commission(pz_items):
    assert pz_items[0]["title"] == "PLANNING AND ZONING COMMISSION"


def test_pz_title_regular_meeting(pz_items):
    assert pz_items[4]["title"] == "PLANNING & ZONING: Regular Meeting Agenda"


def test_pz_start_jan14(pz_items):
    assert pz_items[0]["start"] == datetime(2026, 1, 14, 17, 30)


def test_pz_start_jan28(pz_items):
    assert pz_items[1]["start"] == datetime(2026, 1, 28, 17, 30)


def test_pz_start_mar25(pz_items):
    assert pz_items[5]["start"] == datetime(2026, 3, 25, 17, 30)


def test_pz_classification(pz_items):
    assert pz_items[0]["classification"] == COMMISSION


def test_pz_links_with_video(pz_items):
    assert pz_items[0]["links"] == [
        {
            "href": "https://sunlandpark-nm.gov/wp-content/uploads/2026/01/01-14-2026-Agenda-E-S.pdf",  # noqa
            "title": "Agenda",
        },
        {
            "href": "https://www.youtube.com/watch?v=BmclI0JL92g",
            "title": "Video",
        },
    ]


def test_pz_links_without_video(pz_items):
    assert pz_items[4]["links"] == [
        {
            "href": "https://sunlandpark-nm.gov/wp-content/uploads/2026/03/03-11-2026-Agenda-E-S.pdf",  # noqa
            "title": "Agenda",
        },
    ]


def test_pz_location(pz_items):
    assert pz_items[0]["location"] == {
        "name": "",
        "address": "",
    }


def test_pz_time_notes(pz_items):
    assert (
        pz_items[0]["time_notes"]
        == "Please refer to the agenda for meeting location details"
    )  # noqa


def test_pz_all_day(pz_items):
    for item in pz_items:
        assert item["all_day"] is False


def test_pz_description(pz_items):
    for item in pz_items:
        assert item["description"] == ""
