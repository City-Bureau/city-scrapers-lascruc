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


def _html_response(filename, meta=None):
    request = Request(url=API_URL, meta=meta or {})
    return HtmlResponse(
        url=API_URL,
        body=(FIXTURE_DIR / filename).read_bytes(),
        encoding="utf-8",
        request=request,
    )


@pytest.fixture()
def spider():
    return LascrucAnthonyCityBotSpider()


@freeze_time(TEST_DATE)
def test_year_discovery(spider):
    meta = {"cat_id": 3, "current_year": 2026}
    response = _html_response("lascruc_anthony_city_cat3_2026.html", meta=meta)
    results = list(spider._parse_category_years(response))
    meetings = [r for r in results if not hasattr(r, "url")]
    requests = [r for r in results if hasattr(r, "url")]

    assert len(meetings) == 2
    # 3 additional years discovered: 2025, 2024, 2023
    assert len(requests) == 3


@freeze_time(TEST_DATE)
def test_meeting_fields(spider):
    meta = {"cat_id": 3, "current_year": 2026}
    response = _html_response("lascruc_anthony_city_cat3_2026.html", meta=meta)
    meetings = [
        r for r in spider._parse_category_years(response) if not hasattr(r, "url")
    ]

    first = meetings[0]
    assert first["title"] == "BOT Regular Meeting"
    assert first["start"] == datetime(2026, 3, 4, 0, 0)
    assert first["classification"] == BOARD
    assert first["status"] == PASSED
    assert first["location"] == {"name": "", "address": ""}

    link_titles = [link["title"] for link in first["links"]]
    assert "Agenda (HTML)" in link_titles
    assert "Agenda (PDF)" in link_titles
    assert "Agenda Packet" in link_titles
    assert "Minutes" in link_titles
    assert "Media" in link_titles
    assert "Previous Versions" not in link_titles

    pdf_link = next(l for l in first["links"] if l["title"] == "Agenda (PDF)")
    assert "AgendaCenter/ViewFile/Agenda" in pdf_link["href"]

    minutes_link = next(l for l in first["links"] if l["title"] == "Minutes")
    assert "AgendaCenter/ViewFile/Minutes" in minutes_link["href"]

    media_link = next(link for link in first["links"] if link["title"] == "Media")
    assert media_link["href"].startswith("https://teams.microsoft.com")

    assert first["source"] == (
        "https://www.cityofanthonynm.gov/AgendaCenter/Search/?term=&CIDs=3,"
        "&startDate=&endDate=&dateRange=&dateSelector="
    )


@freeze_time(TEST_DATE)
def test_meeting_without_minutes(spider):
    meta = {"cat_id": 3, "current_year": 2026}
    response = _html_response("lascruc_anthony_city_cat3_2026.html", meta=meta)
    meetings = [
        r for r in spider._parse_category_years(response) if not hasattr(r, "url")
    ]

    second = meetings[1]
    assert second["title"] == "Notice of Potential Quorum."
    assert second["start"] == datetime(2026, 2, 18, 0, 0)
    assert len(second["links"]) == 1
    assert second["links"][0]["title"] == "Agenda"
    assert "AgendaCenter/ViewFile/Agenda" in second["links"][0]["href"]
