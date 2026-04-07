import json
from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, COMMISSION, COMMITTEE, NOT_CLASSIFIED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time
from scrapy.http import TextResponse

from city_scrapers.spiders.lascruc_dona_ana_county import (
    LascrucDonaAnaAirportAdvisoryBoardSpider,
    LascrucDonaAnaBoardOfCountyCommissionersSpider,
    LascrucDonaAnaComplianceOfficeSpider,
    LascrucDonaAnaCountyADAAdvisoryBoardSpider,
    LascrucDonaAnaDevelopmentReviewCommitteeSpider,
    LascrucDonaAnaLaborManagementRelationsSpider,
    LascrucDonaAnaPlanningAndZoningSpider,
)

FROZEN_DATE = "2026-03-18"


def _make_json_response(events):
    """Wrap events in the API response format."""
    body = json.dumps({"value": events}).encode("utf-8")
    return TextResponse(
        url="https://donaanaconm.api.civicclerk.com/v1/Events",
        body=body,
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def all_events():
    with open(
        join(
            dirname(__file__),
            "files",
            "lascruc_dona_ana_county_other_agencies.json",
        )
    ) as f:
        return json.load(f)["value"]


@pytest.fixture(scope="module")
def compliance_items():
    response = file_response(
        join(dirname(__file__), "files", "lascruc_dona_ana_compliance_office.html"),
        url="https://www.donaana.gov/government/agendas/compliance_office.php",
    )
    spider = LascrucDonaAnaComplianceOfficeSpider()
    with freeze_time(FROZEN_DATE):
        return list(spider.parse_compliance(response))


def _parse_single_event(spider_cls, raw_event):
    spider = spider_cls()
    with freeze_time(FROZEN_DATE):
        return list(spider.parse(_make_json_response([raw_event])))


@pytest.fixture(scope="module")
def bocc_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaBoardOfCountyCommissionersSpider,
        all_events[0],
    )


@pytest.fixture(scope="module")
def pz_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaPlanningAndZoningSpider,
        all_events[1],
    )


@pytest.fixture(scope="module")
def lmrb_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaLaborManagementRelationsSpider,
        all_events[2],
    )


@pytest.fixture(scope="module")
def airport_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaAirportAdvisoryBoardSpider,
        all_events[3],
    )


@pytest.fixture(scope="module")
def drc_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaDevelopmentReviewCommitteeSpider,
        all_events[4],
    )


@pytest.fixture(scope="module")
def ada_items(all_events):
    return _parse_single_event(
        LascrucDonaAnaCountyADAAdvisoryBoardSpider,
        all_events[5],
    )


@pytest.fixture(scope="module")
def all_json_items(
    bocc_items, pz_items, lmrb_items, airport_items, drc_items, ada_items
):  # noqa
    return (
        bocc_items + pz_items + lmrb_items + airport_items + drc_items + ada_items
    )  # noqa


# ===================== Compliance (HTML) Tests =====================


def test_compliance_count(compliance_items):
    assert len(compliance_items) == 2


def test_compliance_title(compliance_items):
    assert compliance_items[0]["title"] == "Meeting Notice and Agenda"


def test_compliance_title_second(compliance_items):
    assert compliance_items[1]["title"] == "Notice and Agenda"


def test_compliance_description(compliance_items):
    assert compliance_items[0]["description"] == ""


def test_compliance_start(compliance_items):
    assert compliance_items[0]["start"] == datetime(2024, 11, 22, 10, 0)


def test_compliance_start_second(compliance_items):
    assert compliance_items[1]["start"] == datetime(2014, 11, 27, 10, 0)


def test_compliance_end(compliance_items):
    assert compliance_items[0]["end"] is None


def test_compliance_time_notes(compliance_items):
    assert compliance_items[0]["time_notes"] == ""


def test_compliance_all_day(compliance_items):
    assert compliance_items[0]["all_day"] is False


def test_compliance_location(compliance_items):
    assert compliance_items[0]["location"] == {
        "name": "Dona Ana County",
        "address": "845 N Motel Blvd, Las Cruces, NM 88007",
    }


def test_compliance_source(compliance_items):
    assert (
        compliance_items[0]["source"]
        == "https://www.donaana.gov/government/agendas/compliance_office.php"
    )


def test_compliance_links_first(compliance_items):
    assert compliance_items[0]["links"] == [
        {
            "title": "Agenda",
            "href": "https://www.donaana.gov/Documents/Government/Agendas/Compliance%20Office/Meeting%20Notice%20and%20Agenda%20for%2011222024.pdf?t=202508281151240",  # noqa
        }
    ]


def test_compliance_links_second(compliance_items):
    links = compliance_items[1]["links"]
    assert len(links) == 1
    assert links[0]["title"] == "Agenda"


def test_compliance_classification(compliance_items):
    assert compliance_items[0]["classification"] == NOT_CLASSIFIED


def test_compliance_status(compliance_items):
    assert compliance_items[0]["status"] == "passed"


def test_compliance_id(compliance_items):
    assert compliance_items[0]["id"] is not None


def test_compliance_all_day_all(compliance_items):
    for item in compliance_items:
        assert item["all_day"] is False


# ===================== JSON (API) Tests =====================


def test_json_total_count(all_json_items):
    assert len(all_json_items) == 6


def test_bocc_title_and_start(bocc_items):
    assert bocc_items[0]["title"] == "BOCC Work Session"
    assert bocc_items[0]["start"] == datetime(2026, 1, 6, 9, 0)
    assert bocc_items[0]["classification"] == COMMISSION


def test_pz_links(pz_items):
    assert len(pz_items[0]["links"]) == 2
    assert pz_items[0]["links"][0]["title"] == "Agenda"
    assert pz_items[0]["links"][1]["title"] == "Agenda Packet"


def test_lmrb_classification(lmrb_items):
    assert lmrb_items[0]["classification"] == BOARD
    assert lmrb_items[0]["start"] == datetime(2020, 6, 22, 9, 0)


def test_airport_location_and_no_links(airport_items):
    assert airport_items[0]["location"] == {
        "name": "Dona Ana County",
        "address": "8012 Airport Rd Santa Teresa, New Mexico, 88008",
    }
    assert airport_items[0]["links"] == []
    assert airport_items[0]["description"] == "Meets monthly as needed."


def test_drc_classification(drc_items):
    assert drc_items[0]["classification"] == COMMITTEE
    assert drc_items[0]["start"] == datetime(2024, 5, 2, 9, 0)


def test_ada_title_and_classification(ada_items):
    assert ada_items[0]["title"] == "ADA Advisory Committee Meeting"
    assert ada_items[0]["classification"] == BOARD


def test_pz_null_location_uses_default(pz_items):
    assert pz_items[0]["location"] == {
        "name": "Dona Ana County",
        "address": "845 N Motel Blvd, Las Cruces, NM 88007",
    }


def test_json_all_day(all_json_items):
    for item in all_json_items:
        assert item["all_day"] is False
