import re
from datetime import datetime
from zoneinfo import ZoneInfo

import scrapy
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import ParserError
from dateutil.parser import parse as dateparse


class LascrucAnthonyCityMixinMeta(type):
    """Enforces required attributes on child spider classes."""

    def __init__(cls, name, bases, dct):
        if name == "LascrucAnthonyCityMixin":
            super().__init__(name, bases, dct)
            return
        if any(getattr(b, "__name__", "") == "LascrucAnthonyCityMixin" for b in bases):
            required = ["name", "agency", "cat_ids", "classification"]
            missing = [v for v in required if v not in dct]
            if missing:
                raise NotImplementedError(f"{name} must define: {', '.join(missing)}")
        super().__init__(name, bases, dct)


class LascrucAnthonyCityMixin(
    CityScrapersSpider, metaclass=LascrucAnthonyCityMixinMeta
):
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
        start_time: datetime.time applied to all past meetings from
            AgendaCenter, which does not publish a start time.  Defaults to
            None (midnight).
        location: dict with "name" and "address" keys used for all meetings.
            Defaults to {"name": "", "address": ""}.
    """

    timezone = "America/Denver"
    tzinfo = ZoneInfo(timezone)
    location = {"name": "", "address": ""}
    start_time = None  # override in subclass to hardcode start time for past meetings
    base_url = "https://www.cityofanthonynm.gov"
    api_url = base_url + "/AgendaCenter/UpdateCategoryList"
    calendar_cid = None  # override in subclass to enable secondary calendar

    # Matches the end time in "6:00 PM - 8:00 PM" from the calendar date div
    _CALENDAR_END_RE = re.compile(r"-\s*(\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)
    # Normalizes title variants from both sources to a clean display name
    _TITLE_NORMALIZE = [
        (re.compile(r"budget\s+workshop", re.IGNORECASE), "Budget Workshop"),
        (
            re.compile(r"special\s+meeting|special\s+virtual", re.IGNORECASE),
            "Special Meeting",
        ),
        (re.compile(r"public\s+hearing|\bPH\b", re.IGNORECASE), "Public Hearing"),
        (
            re.compile(
                r"regular\s+meeting|regular\s+bot|bot\s+regular|p&z\s+regular"
                r"|board\s+of\s+trustee|planning\s+&\s+zoning|regular\s+p&z"
                r"|\bmeeting\b",
                re.IGNORECASE,
            ),
            "Regular Meeting",
        ),
    ]
    time_notes = (
        "Start time is estimated based on prior meetings; "
        "refer to the agenda document for exact details."
    )
    time_notes_calendar = ""

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def handle_error(self, failure):
        self.logger.error("Request failed: %s", failure.request.url)

    def start_requests(self):
        now = datetime.now(tz=self.tzinfo)
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
                    errback=self.handle_error,
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
            errback=self.handle_error,
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
            if not year_text.isdigit():
                continue
            year = int(year_text)
            if year == current_year:
                continue
            yield self._category_request(
                cat_id=cat_id, year=year, callback=self._parse_rows
            )

    def _parse_rows(self, response):
        """Parse meeting rows from the category list HTML fragment."""
        for row in response.css("tr.catAgendaRow"):
            yield from self._parse_row(row)

    def _parse_row(self, row):
        """Parse a single meeting row, yielding a Request or a Meeting."""
        start = self._parse_start(row)
        raw_title = row.css("p a::text").get("").strip()
        if not start or not raw_title:
            return

        # Include the AgendaCenter row ID (e.g. "02052024-66") in the title
        # used for ID generation so that two rows with identical titles on the
        # same date (the site publishes multiple agenda versions) get unique IDs.
        row_id = row.css("p a::attr(id)").get("").strip()
        id_title = f"{raw_title} {row_id}" if row_id else raw_title

        meeting = Meeting(
            title=id_title,
            description="",
            classification=self.classification,
            start=start,
            end=None,
            all_day=False,
            time_notes=self.time_notes,
            location=self.location,
            links=[],
            source=self._parse_source(),
        )
        meeting["id"] = self._get_id(meeting)
        meeting["title"] = self._normalize_title(raw_title)
        meeting["status"] = self._get_status(meeting, text=raw_title)

        minutes_href = self._full_url(row.css("td.minutes a::attr(href)").get(""))
        minutes = [{"href": minutes_href, "title": "Minutes"}] if minutes_href else []

        html_href = self._find_html_href(row)
        if html_href:
            yield scrapy.Request(
                url=html_href,
                callback=self._parse_agenda_html,
                errback=self.handle_error,
                meta={"meeting": meeting, "minutes": minutes},
            )
        else:
            agenda_href = self._full_url(row.css("p a::attr(href)").get(""))
            links = []
            if agenda_href:
                links.append({"href": agenda_href, "title": "Agenda"})
            meeting["links"] = links + minutes
            yield meeting

    def _normalize_title(self, raw_title):
        """Map raw AgendaCenter title variants to a clean display name."""
        for pattern, clean in self._TITLE_NORMALIZE:
            if pattern.search(raw_title):
                return clean
        return raw_title.rstrip(".")

    def _find_html_href(self, row):
        """Return the HTML agenda link href from the dropdown, or None."""
        for link in row.css("ol[role='menu'] a[href]"):
            if link.css("::text").get("").strip().lower() == "html":
                href = link.attrib.get("href", "").strip()
                return self._full_url(href) if href else None
        return None

    def _parse_agenda_html(self, response):
        """Follow the HTML agenda page and collect all linked documents."""
        meeting = response.meta["meeting"]
        minutes = response.meta.get("minutes", [])
        links = []
        for a in response.css("a[href]"):
            href = a.attrib.get("href", "").strip()
            if not href or href.startswith("#"):
                continue
            links.append(
                {
                    "href": response.urljoin(href),
                    "title": f"Attachment {len(links) + 1}",
                }
            )
        meeting["links"] = links + minutes
        yield meeting

    def _parse_start(self, row):
        """Parse start date from the aria-label on the date heading."""
        aria_label = row.css("h3 strong::attr(aria-label)").get("")
        date_str = aria_label.replace("Agenda for ", "").strip()
        try:
            dt = dateparse(date_str)
            if self.start_time is not None:
                dt = dt.replace(
                    hour=self.start_time.hour,
                    minute=self.start_time.minute,
                    second=0,
                    microsecond=0,
                )
            return dt
        except (ParserError, ValueError):
            self.logger.warning("Could not parse start date from %r", date_str)
            return None

    def _parse_source(self):
        """Return the AgendaCenter search URL for this spider's categories."""
        cids = ",".join(str(c) for c in self.cat_ids)
        return (
            f"{self.base_url}/AgendaCenter/Search/?term=&CIDs={cids},"
            "&startDate=&endDate=&dateRange=&dateSelector="
        )

    def _parse_calendar_month(self, response):
        """Parse future meetings from one month of the CivicPlus calendar list view."""
        today = datetime.now(tz=self.tzinfo).date()
        for item in response.css("div.calendars div.calendar ol li"):
            meeting = self._parse_calendar_item(item)
            if meeting and meeting["start"].date() > today:
                yield meeting

    def _parse_calendar_item(self, item):
        """Parse a single calendar list item into a Meeting."""
        raw_title = item.css("h3 a span::text").get("").strip()
        start, end = self._parse_calendar_datetime(item)
        if not raw_title or not start:
            return None

        meeting = Meeting(
            title=raw_title,
            description="",
            classification=self.classification,
            start=start,
            end=end,
            all_day=False,
            time_notes=self.time_notes_calendar,
            location=self.location,
            links=[],
            source=f"{self.base_url}/calendar.aspx?CID={self.calendar_cid}",
        )
        meeting["id"] = self._get_id(meeting)
        meeting["title"] = self._normalize_title(raw_title)
        meeting["status"] = self._get_status(meeting, text=raw_title)
        return meeting

    def _parse_calendar_datetime(self, item):
        """Return (start, end) from schema.org ISO start + end time in the date div."""
        iso = item.css("span[itemprop='startDate']::text").get("").strip()
        try:
            start = dateparse(iso)
        except (ParserError, ValueError):
            self.logger.warning("Could not parse calendar start date from %r", iso)
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
                self.logger.warning(
                    "Could not parse calendar end time from %r", m.group(1)
                )
        return start, end

    def _full_url(self, href):
        """Prepend base_url to relative paths; return absolute URLs unchanged."""
        if href.startswith("/"):
            return self.base_url + href
        return href
