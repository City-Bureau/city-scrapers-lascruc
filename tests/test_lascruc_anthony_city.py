from datetime import datetime
from pathlib import Path

import pytest
from city_scrapers_core.constants import BOARD, PASSED
from freezegun import freeze_time
from scrapy.http import HtmlResponse, Request

from city_scrapers.spiders.lascruc_anthony_city import LascrucAnthonyCityBotSpider

TEST_DATE = "2026-03-17"
FIXTURE_DIR = Path(__file__).parent / "files"
API_URL = "https://www.cityofanthonynm.gov/AgendaCenter/UpdateCategoryList"


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
@freeze_time(TEST_DATE)
def meetings(spider):
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

    assert len(direct_meetings) == 1  # row without HTML link yields directly
    assert len(year_requests) == 3  # 2025, 2024, 2023
    assert len(html_requests) == 1  # row with HTML link yields a follow-up request


@freeze_time(TEST_DATE)
def test_meeting_fields(meetings):
    first = meetings[0]
    assert first["title"] == "BOT Regular Meeting"
    assert first["start"] == datetime(2026, 3, 4, 0, 0)
    assert first["classification"] == BOARD
    assert first["status"] == PASSED
    assert first["location"] == {"name": "", "address": ""}
    assert len(first["links"]) == 1
    assert first["links"][0]["title"] == "Agenda"
    assert first["links"][0]["href"].endswith("BOTMeeting.pdf")
    assert first["source"] == (
        "https://www.cityofanthonynm.gov/AgendaCenter/Search/?term=&CIDs=3,"
        "&startDate=&endDate=&dateRange=&dateSelector="
    )


@freeze_time(TEST_DATE)
def test_meeting_without_minutes(meetings):
    second = meetings[1]
    assert second["title"] == "Notice of Potential Quorum."
    assert second["start"] == datetime(2026, 2, 18, 0, 0)
    assert len(second["links"]) == 1
    assert second["links"][0]["title"] == "Agenda"
    assert "AgendaCenter/ViewFile/Agenda" in second["links"][0]["href"]
