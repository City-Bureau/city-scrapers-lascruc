from datetime import datetime
from pathlib import Path

import pytest
from city_scrapers_core.constants import BOARD, PASSED, TENTATIVE
from freezegun import freeze_time
from scrapy.http import HtmlResponse, Request

from city_scrapers.spiders.lascruc_anthony_city import LascrucAnthonyCityBotSpider

TEST_DATE = "2026-03-17"
FIXTURE_DIR = Path(__file__).parent / "files"
API_URL = "https://www.cityofanthonynm.gov/AgendaCenter/UpdateCategoryList"
CALENDAR_URL = (
    "https://www.cityofanthonynm.gov/calendar.aspx"
    "?month=4&year=2026&CID=23&view=list"
)


def _html_response(filename, meta=None, url=None):
    url = url or API_URL
    request = Request(url=url, meta=meta or {})
    return HtmlResponse(
        url=url,
        body=(FIXTURE_DIR / filename).read_bytes(),
        encoding="utf-8",
        request=request,
    )


@pytest.fixture()
def spider():
    return LascrucAnthonyCityBotSpider()


@pytest.fixture()
def meetings(spider):
    with freeze_time(TEST_DATE):
        meta = {"cat_id": 3, "current_year": 2026}
        response = _html_response("lascruc_anthony_city_cat3_2026.html", meta=meta)
        results = list(spider._parse_category_years(response))

        resolved = [r for r in results if not hasattr(r, "url")]
        for r in results:
            if hasattr(r, "url") and "ViewFile/Agenda" in r.url:
                agenda_response = _html_response(
                    "lascruc_anthony_city_agenda.html", meta=r.meta, url=r.url
                )
                resolved.extend(spider._parse_agenda_html(agenda_response))

        return sorted(resolved, key=lambda m: m["start"], reverse=True)


@pytest.fixture()
def calendar_meetings(spider):
    with freeze_time(TEST_DATE):
        response = _html_response(
            "lascruc_anthony_city_calendar_month.html", url=CALENDAR_URL
        )
        return list(spider._parse_calendar_month(response))


@freeze_time(TEST_DATE)
def test_year_discovery(spider):
    meta = {"cat_id": 3, "current_year": 2026}
    response = _html_response("lascruc_anthony_city_cat3_2026.html", meta=meta)
    results = list(spider._parse_category_years(response))

    direct_meetings = [r for r in results if not hasattr(r, "url")]
    year_requests = [
        r for r in results if hasattr(r, "url") and "ViewFile" not in r.url
    ]
    html_requests = [r for r in results if hasattr(r, "url") and "ViewFile" in r.url]

    assert len(direct_meetings) == 1
    assert len(year_requests) == 3
    assert len(html_requests) == 1


def test_meeting_fields(meetings):
    first = meetings[0]
    assert first["title"] == "Regular Meeting"
    assert first["start"] == datetime(2026, 3, 4, 18, 0)
    assert first["classification"] == BOARD
    assert first["status"] == PASSED
    assert first["location"] == {
        "name": "Court Chambers",
        "address": "820 Highway 478 Anthony, NM 88021",
    }
    assert len(first["links"]) == 2
    assert first["links"][0]["title"] == "Attachment 1"
    assert first["links"][0]["href"].endswith("BOTMeeting.pdf")
    assert first["links"][1]["title"] == "Minutes"
    assert first["links"][1]["href"] == (
        "https://www.cityofanthonynm.gov/AgendaCenter/ViewFile/Minutes/_03042026-178"
    )
    assert first["source"] == (
        "https://www.cityofanthonynm.gov/AgendaCenter/Search/?term=&CIDs=3,"
        "&startDate=&endDate=&dateRange=&dateSelector="
    )


def test_meeting_without_minutes(meetings):
    second = meetings[1]
    assert second["title"] == "Notice of Potential Quorum"
    assert second["start"] == datetime(2026, 2, 18, 18, 0)
    assert len(second["links"]) == 1
    assert second["links"][0]["title"] == "Agenda"
    assert second["links"][0]["href"] == (
        "https://www.cityofanthonynm.gov/AgendaCenter/ViewFile/Agenda/_02182026-168"
    )


def test_title_normalize_ph_abbreviation(spider):
    assert (
        spider._normalize_title("Board of Trustees PH Meeting Agenda")
        == "Public Hearing"
    )


def test_meeting_ids_are_unique(meetings):
    ids = [m["id"] for m in meetings]
    assert len(ids) == len(set(ids))


def test_calendar_filters_past_meetings(calendar_meetings):
    assert len(calendar_meetings) == 1


def test_calendar_meeting_fields(calendar_meetings):
    m = calendar_meetings[0]
    assert m["title"] == "Regular Meeting"
    assert m["start"] == datetime(2026, 4, 15, 18, 0)
    assert m["end"] == datetime(2026, 4, 15, 20, 0)
    assert m["classification"] == BOARD
    assert m["status"] == TENTATIVE
    assert m["time_notes"] == ""
    assert m["source"] == "https://www.cityofanthonynm.gov/calendar.aspx?CID=23"
    assert m["links"] == []
    assert m["location"] == {
        "name": "Court Chambers",
        "address": "820 Highway 478 Anthony, NM 88021",
    }
