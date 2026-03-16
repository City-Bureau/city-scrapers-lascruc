"""
A Mixin & Mixin Meta template for scrapers that share a common data source.

Required class variables (enforced by metaclass):
    name (str): Spider name/slug (e.g., "tulok_city_council")
    agency (str): Full agency name (e.g., "Tulsa City Council")
    id (str): Usually a unique ID different between agencies of the same website. This field # noqa
    can also be any other string that helps uniquely identify the spider.

    any_other_required_var (type): You can use this space to describe any other required
    static variable that must be defined in child classes.
"""

from datetime import date, datetime, timezone
from urllib.parse import urlencode

import scrapy
from city_scrapers_core.constants import (
    BOARD,
    CITY_COUNCIL,
    COMMISSION,
    COMMITTEE,
    NOT_CLASSIFIED,
)
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.relativedelta import relativedelta


class SpiderFactoryTemplateMixinMeta(type):
    """
    Metaclass that enforces the implementation of required static
    variables in child classes that inherit from the "Mixin" class.
    """

    def __init__(cls, name, bases, dct):
        if not any(base.__name__ == "SpiderFactoryTemplateMixin" for base in bases if hasattr(base, '__name__')):
            super().__init__(name, bases, dct)
            return
            
        required_static_vars = ["agency", "name", "id"]
        missing_vars = [var for var in required_static_vars if var not in dct]

        if missing_vars:
            missing_vars_str = ", ".join(missing_vars)
            raise NotImplementedError(
                f"{name} must define the following static variable(s): "
                f"{missing_vars_str}."
            )

        super().__init__(name, bases, dct)


class SpiderFactoryTemplateMixin(
    CityScrapersSpider, metaclass=SpiderFactoryTemplateMixinMeta
):

    timezone = "America/Chicago"
    base_url = "https://lascruces.civicweb.net/Portal/MeetingSchedule.aspx"
    meetings_api_url = (
        "https://lascruces.civicweb.net/Services/MeetingsService.svc/meetings"
    )
    source_url = "https://lascruces.civicweb.net/Portal/MeetingSchedule.aspx"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        """
        Request meetings from two years in the past through one year in the future.
        """
        today = date.today()
        from_date = (today - relativedelta(years=2)).isoformat()
        to_date = (today + relativedelta(years=1)).isoformat()

        params = {
            "from": from_date,
            "to": to_date,
            "_": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

        url = f"{self.meetings_api_url}?{urlencode(params)}"
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):

        prefixes = getattr(self, "name_prefixes", None) or [self.agency]
        excludes = getattr(self, "name_excludes", None) or []
        for item in response.json():
            if not any(item["Name"].startswith(p) for p in prefixes):
                continue
            if any(item["Name"].startswith(e) for e in excludes):
                continue
            title = self._parse_title(item)
            meeting = Meeting(
                title=title,
                description="",
                classification=self._parse_classification(title),
                start=self._parse_start(item),
                end=None,
                all_day=False,
                time_notes=self._parse_time_notes(item),
                location=self._parse_location(item),
                links=self._parse_links(item),
                source=self.source_url,
            )

            meeting["status"] = self._get_status(meeting)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_title(self, item):
        """Parse or generate meeting title."""
        title = item.get("Name", "")
        title = title.replace("- ", " - ")
        parts = title.rsplit(" - ", 1)
        title = parts[0] if len(parts) > 1 else title
        title = title.replace("  ", " ")
        return title


    def _parse_classification(self, title):
        """Parse or generate classification from allowed options."""
        if "Board" in title or "Utilities" in title:
            return BOARD
        if "City Council" in title:
            return CITY_COUNCIL
        if "CIAC" in title:
            return COMMITTEE
        if "Planning" in title:
            return COMMISSION

        return NOT_CLASSIFIED

    def _parse_start(self, item):
        """Parse start datetime as a naive datetime object."""
        dt_str = item.get("MeetingDateTime", "")
        if dt_str:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return None


    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        start_time = self._parse_start(item)
        if start_time and start_time.hour == 0 and start_time.minute == 0:
            return "Please check meeting details for more accurate time"
        return ""


    def _parse_location(self, item):
        """Parse or generate location."""
        location = item.get("MeetingLocation", "").strip()
        if location.startswith("Utilities") or location.startswith("680"):
            return {
                "address": "680 N Motel Blvd, Las Cruces NM",
                "name": "Utilities Center",
            }
        if (
            "City Hall" in location
            or "City Clerk" in location
            or "Council Chambers" in location
            or "Convention Center" in location
            or "NMSU Fulton Center" in location
        ):
            return {
                "address": "700 N. Main St., Las Cruces, NM 88001",
                "name": location,
            }
        return {
            "address": "",
            "name": location,
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        meeting_id = item.get("Id", "")
        if meeting_id:
            return [
                {
                    "href": f"https://lascruces.civicweb.net/Portal/MeetingInformation.aspx?Id={meeting_id}",  # noqa
                    "title": "Meeting Details",
                }
            ]
        return [{"href": "", "title": ""}]
