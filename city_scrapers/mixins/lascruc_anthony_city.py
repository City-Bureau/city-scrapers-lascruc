import re
from datetime import datetime

import scrapy
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import ParserError
from dateutil.parser import parse as dateparse


class LascrucAnthonyCityMixin(CityScrapersSpider):
    """
    Mixin for City of Anthony NM AgendaCenter scrapers.

    Subclasses must define:
        name: Scrapy spider name
        agency: Agency display name
        cat_ids: list of integer category IDs from the AgendaCenter portal
        classification: city_scrapers_core classification constant

    Subclasses may optionally define:
        calendar_cid: integer CID for the CivicPlus calendar URL used to
            supplement future meetings that have not yet appeared on the
            AgendaCenter.  When set, the spider fetches the next 12 months
            of calendar pages and yields any meeting whose date is strictly
            after today (so AgendaCenter always owns "today" and past dates,
            and the calendar supplies future-only entries without overlap).
    """

    timezone = "America/Denver"
    location = {"name": "", "address": ""}
    base_url = "https://www.cityofanthonynm.gov"
    api_url = base_url + "/AgendaCenter/UpdateCategoryList"
    calendar_cid = None  # override in subclass to enable secondary calendar

    _LINK_TITLE_MAP = {
        "html": "Agenda (HTML)",
        "pdf": "Agenda (PDF)",
        "packet": "Agenda Packet",
    }
    # Matches the end time in "6:00 PM - 8:00 PM" from the calendar date div
    _CALENDAR_END_RE = re.compile(r"-\s*(\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)
    time_notes = (
        "Meeting times are not published on the AgendaCenter. "
        "Refer to the agenda document for the exact time."
    )

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        now = datetime.now()
        for cat_id in self.cat_ids:
            yield self._category_request(
                cat_id=cat_id,
                year=now.year,
                callback=self._parse_category_years,
                meta={"cat_id": cat_id, "current_year": now.year},
            )

        if self.calendar_cid:
            for i in range(13):  # current month + 12 future months
                month = ((now.month - 1 + i) % 12) + 1
                year = now.year + (now.month - 1 + i) // 12
                yield scrapy.Request(
                    url=(
                        f"{self.base_url}/calendar.aspx"
                        f"?month={month}&year={year}"
                        f"&CID={self.calendar_cid}&view=list"
                    ),
                    callback=self._parse_calendar_month,
                )

    def _category_request(self, cat_id, year, callback, meta=None):
        """Build a FormRequest to the AgendaCenter UpdateCategoryList endpoint."""
        return scrapy.FormRequest(
            url=self.api_url,
            formdata={
                "year": str(year),
                "catID": str(cat_id),
                "startDate": "",
                "endDate": "",
                "term": "",
                "prevVersionScreen": "false",
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.base_url + "/AgendaCenter",
            },
            callback=callback,
            meta=meta or {},
            dont_filter=True,
        )

    def _parse_category_years(self, response):
        """Parse meetings for the current year and request all other available years."""
        cat_id = response.meta["cat_id"]
        current_year = response.meta["current_year"]

        yield from self._parse_rows(response)

        for year_link in response.css("ul.years a"):
            year_text = year_link.css("::text").get("").strip()
            try:
                year = int(year_text)
            except ValueError:
                continue
            if year == current_year:
                continue
            yield self._category_request(
                cat_id=cat_id, year=year, callback=self._parse_rows
            )

    def _parse_rows(self, response):
        """Parse meeting rows from the category list HTML fragment."""
        for row in response.css("tr.catAgendaRow"):
            meeting = self._parse_row(row)
            if meeting:
                yield meeting

    def _parse_row(self, row):
        """Parse a single meeting row into a Meeting item."""
        start = self._parse_start(row)
        if not start:
            return None

        title = row.css("p a::text").get("").strip()
        if not title:
            return None

        meeting = Meeting(
            title=title,
            description="",
            classification=self.classification,
            start=start,
            end=None,
            all_day=False,
            time_notes=self.time_notes,
            location=self.location,
            links=self._parse_links(row),
            source=self._parse_source(),
        )
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_start(self, row):
        """Parse start date from the aria-label on the date heading."""
        aria_label = row.css("h3 strong::attr(aria-label)").get("")
        date_str = aria_label.replace("Agenda for ", "").strip()
        try:
            return dateparse(date_str)
        except (ParserError, ValueError):
            return None

    def _parse_links(self, row):
        """Extract and normalize all document links for the meeting."""
        links = []
        seen = set()

        for link in row.css("ol[role='menu'] a[href]"):
            link_text = link.css("::text").get("").strip()
            href = link.attrib.get("href", "").strip()
            if not href or not link_text or "previous version" in link_text.lower():
                continue
            href = self._full_url(href)
            if href in seen:
                continue
            title = self._LINK_TITLE_MAP.get(link_text.lower(), "Agenda")
            links.append({"href": href, "title": title})
            seen.add(href)

        # Fall back to the inline p > a link if dropdown had no entries
        if not links:
            agenda_href = self._full_url(row.css("p a::attr(href)").get(""))
            if agenda_href:
                links.append({"href": agenda_href, "title": "Agenda"})
                seen.add(agenda_href)

        minutes_href = self._full_url(row.css("td.minutes a::attr(href)").get(""))
        if minutes_href and minutes_href not in seen:
            links.append({"href": minutes_href, "title": "Minutes"})
            seen.add(minutes_href)

        media_href = self._full_url(row.css("td.media a::attr(href)").get("").strip())
        if media_href and media_href not in seen:
            links.append({"href": media_href, "title": "Media"})
            seen.add(media_href)

        return links

    def _parse_source(self):
        """Return the AgendaCenter search URL for this spider's categories."""
        cids = ",".join(str(c) for c in self.cat_ids)
        return (
            f"{self.base_url}/AgendaCenter/Search/?term=&CIDs={cids},"
            "&startDate=&endDate=&dateRange=&dateSelector="
        )

    def _parse_calendar_month(self, response):
        """Parse future meetings from one month of the CivicPlus calendar list view."""
        today = datetime.now().date()
        for item in response.css("div.calendars div.calendar ol li"):
            meeting = self._parse_calendar_item(item)
            if meeting and meeting["start"].date() > today:
                yield meeting

    def _parse_calendar_item(self, item):
        """Parse a single calendar list item into a Meeting."""
        title = item.css("h3 a span::text").get("").strip()
        start, end = self._parse_calendar_datetime(item)
        if not title or not start:
            return None

        meeting = Meeting(
            title=title,
            description="",
            classification=self.classification,
            start=start,
            end=end,
            all_day=False,
            time_notes="",
            location=self.location,
            links=[],
            source=f"{self.base_url}/calendar.aspx?CID={self.calendar_cid}",
        )
        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_calendar_datetime(self, item):
        """Return (start, end) from schema.org ISO start + end time in the date div."""
        iso = item.css("span[itemprop='startDate']::text").get("").strip()
        try:
            start = dateparse(iso)
        except (ParserError, ValueError):
            return None, None

        # "April\xa01,\xa02026,\xa06:00 PM\u2009-\u20098:00 PM" — normalize whitespace
        date_text = (
            item.css("div.subHeader div.date::text")
            .get("")
            .replace("\xa0", " ")
            .replace("\u2009", " ")
        )
        m = self._CALENDAR_END_RE.search(date_text)
        end = None
        if m:
            try:
                end = dateparse(f"{start.date()} {m.group(1)}")
            except (ParserError, ValueError):
                pass
        return start, end

    def _full_url(self, href):
        """Prepend base_url to relative paths; return absolute URLs unchanged."""
        if href.startswith("/"):
            return self.base_url + href
        return href
