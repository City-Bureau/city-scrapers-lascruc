from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, CITY_COUNCIL, COMMISSION, COMMITTEE
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.lascruc_las_cruces_city import (
    LasCrucesAgendaSettingMeeting,
    LasCrucesASCMV,
    LasCrucesCIAC,
    LasCrucesCityCouncil,
    LasCrucesClosedMeeting,
    LasCrucesPlanningZoning,
    LasCrucesPressConferencesForums,
    LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting,
    LasCrucesUtilities,
    LasCrucesWorkSession,
)


@pytest.fixture(scope="module")
def meetings_response():
    url = "https://lascruces.civicweb.net/Services/MeetingsService.svc/meetings?from=2024-01-01&to=2027-12-31&_=1234567890"  # noqa
    return file_response(
        join(dirname(__file__), "files", "lascruc_las_cruces_city.json"),
        url=url,
    )


def parse_items(spider, meetings_response):
    with freeze_time("2026-03-15"):
        return list(spider.parse(meetings_response))


@pytest.mark.parametrize(
    "spider_class, expected_count",
    [
        (LasCrucesAgendaSettingMeeting, 1),
        (LasCrucesASCMV, 1),
        (LasCrucesCIAC, 1),
        (LasCrucesCityCouncil, 1),
        (LasCrucesClosedMeeting, 1),
        (LasCrucesPlanningZoning, 1),
        (LasCrucesPressConferencesForums, 1),
        (LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting, 1),
        (LasCrucesUtilities, 1),
        (LasCrucesWorkSession, 1),
    ],
)
def test_spider_counts(spider_class, expected_count, meetings_response):
    items = parse_items(spider_class(), meetings_response)
    assert len(items) == expected_count


# City Council tests
def test_city_council_count(meetings_response):
    items = parse_items(LasCrucesCityCouncil(), meetings_response)
    assert len(items) == 1


def test_city_council_title(meetings_response):
    items = parse_items(LasCrucesCityCouncil(), meetings_response)
    assert items[0]["title"] == "Special City Council Meeting "


def test_city_council_classification(meetings_response):
    items = parse_items(LasCrucesCityCouncil(), meetings_response)
    assert items[0]["classification"] == CITY_COUNCIL


def test_city_council_start(meetings_response):
    items = parse_items(LasCrucesCityCouncil(), meetings_response)
    assert items[0]["start"] == datetime(2025, 1, 13, 9, 0)


def test_city_council_location(meetings_response):
    items = parse_items(LasCrucesCityCouncil(), meetings_response)
    assert items[0]["location"] == {
        "name": "City Council Chambers, City Hall",
        "address": "700 N. Main St., Las Cruces, NM 88001",
    }


# CIAC tests
def test_ciac_count(meetings_response):
    items = parse_items(LasCrucesCIAC(), meetings_response)
    assert len(items) == 1


def test_ciac_titles(meetings_response):
    items = parse_items(LasCrucesCIAC(), meetings_response)
    titles = [item["title"] for item in items]
    assert "Work Session - CIAC " in titles


def test_ciac_classification(meetings_response):
    items = parse_items(LasCrucesCIAC(), meetings_response)
    for item in items:
        assert item["classification"] == COMMITTEE


def test_ciac_location(meetings_response):
    items = parse_items(LasCrucesCIAC(), meetings_response)
    for item in items:
        assert item["location"] == {
            "name": "Utilities Center",
            "address": "680 N Motel Blvd, Las Cruces NM",
        }


# Planning & Zoning tests
def test_planning_zoning_count(meetings_response):
    items = parse_items(LasCrucesPlanningZoning(), meetings_response)
    assert len(items) == 1


def test_planning_zoning_title(meetings_response):
    items = parse_items(LasCrucesPlanningZoning(), meetings_response)
    assert items[0]["title"] == "Planning & Zoning "


def test_planning_zoning_classification(meetings_response):
    items = parse_items(LasCrucesPlanningZoning(), meetings_response)
    assert items[0]["classification"] == COMMISSION


# Agenda Setting Meeting tests
def test_agenda_setting_count(meetings_response):
    items = parse_items(LasCrucesAgendaSettingMeeting(), meetings_response)
    assert len(items) == 1


def test_agenda_setting_title(meetings_response):
    items = parse_items(LasCrucesAgendaSettingMeeting(), meetings_response)
    assert items[0]["title"] == "Agenda Setting Meeting "


# ASCMV tests
def test_ascmv_count(meetings_response):
    items = parse_items(LasCrucesASCMV(), meetings_response)
    assert len(items) == 1


def test_ascmv_title(meetings_response):
    items = parse_items(LasCrucesASCMV(), meetings_response)
    assert items[0]["title"] == "ASCMV Closed Meeting"


# Closed Meeting tests
def test_closed_meeting_count(meetings_response):
    items = parse_items(LasCrucesClosedMeeting(), meetings_response)
    assert len(items) == 1


def test_closed_meeting_title(meetings_response):
    items = parse_items(LasCrucesClosedMeeting(), meetings_response)
    assert items[0]["title"] == "Closed Meeting "


# Press Conferences & Forums tests
def test_press_conferences_count(meetings_response):
    items = parse_items(LasCrucesPressConferencesForums(), meetings_response)
    assert len(items) == 1


def test_press_conferences_title(meetings_response):
    items = parse_items(LasCrucesPressConferencesForums(), meetings_response)
    assert items[0]["title"] == "Press Conferences & Forums "


# Tax Increment Development District Board Meeting tests
def test_tid_board_count(meetings_response):
    items = parse_items(
        LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting(), meetings_response
    )
    assert len(items) == 1


def test_tid_board_title(meetings_response):
    items = parse_items(
        LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting(), meetings_response
    )
    assert items[0]["title"] == "Tax Increment Development District Board Meeting "


def test_tid_board_classification(meetings_response):
    items = parse_items(
        LasCrucesTaxIncrementDevelopmentDistrictBoardMeeting(), meetings_response
    )
    assert items[0]["classification"] == BOARD


# Work Session tests
def test_work_session_count(meetings_response):
    items = parse_items(LasCrucesWorkSession(), meetings_response)
    assert len(items) == 1


def test_work_session_title(meetings_response):
    items = parse_items(LasCrucesWorkSession(), meetings_response)
    assert items[0]["title"] == "Joint Work Session "


def test_work_session_excludes_ciac(meetings_response):
    items = parse_items(LasCrucesWorkSession(), meetings_response)
    titles = [item["title"] for item in items]
    assert "Work Session - CIAC " not in titles


# Utilities tests
def test_utilities_count(meetings_response):
    items = parse_items(LasCrucesUtilities(), meetings_response)
    assert len(items) == 1


def test_utilities_title(meetings_response):
    items = parse_items(LasCrucesUtilities(), meetings_response)
    assert items[0]["title"] == "Utilities - Regular Meeting "


def test_utilities_classification(meetings_response):
    items = parse_items(LasCrucesUtilities(), meetings_response)
    assert items[0]["classification"] == BOARD


def test_utilities_location(meetings_response):
    items = parse_items(LasCrucesUtilities(), meetings_response)
    assert items[0]["location"] == {
        "name": "Utilities Center",
        "address": "680 N Motel Blvd, Las Cruces NM",
    }
