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
    """

    timezone = "America/Denver"
    location = {"name": "", "address": ""}
    base_url = "https://www.cityofanthonynm.gov"
    api_url = base_url + "/AgendaCenter/UpdateCategoryList"

    _LINK_TITLE_MAP = {
        "html": "Agenda (HTML)",
        "pdf": "Agenda (PDF)",
        "packet": "Agenda Packet",
    }
    time_notes = (
        "Meeting times are not published on the AgendaCenter. "
        "Refer to the agenda document for the exact time."
    )

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        current_year = datetime.now().year
        for cat_id in self.cat_ids:
            yield self._category_request(
                cat_id=cat_id,
                year=current_year,
                callback=self._parse_category_years,
                meta={"cat_id": cat_id, "current_year": current_year},
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
            if agenda_href and agenda_href not in seen:
                links.append({"href": agenda_href, "title": "Agenda"})
                seen.add(agenda_href)

        minutes_href = self._full_url(row.css("td.minutes a::attr(href)").get(""))
        if minutes_href and minutes_href not in seen:
            links.append({"href": minutes_href, "title": "Minutes"})
            seen.add(minutes_href)

        media_href = row.css("td.media a::attr(href)").get("").strip()
        if media_href and media_href not in seen:
            links.append({"href": media_href, "title": "Media"})
            seen.add(media_href)

        return links

    def _parse_source(self):
        """Return the AgendaCenter search URL for this spider's categories."""
        cids = ",".join(str(c) for c in self.cat_ids)
        return (
            "{}/AgendaCenter/Search/?term=&CIDs={},".format(self.base_url, cids)
            + "&startDate=&endDate=&dateRange=&dateSelector="
        )

    def _full_url(self, href):
        """Prepend base_url to relative paths; return absolute URLs unchanged."""
        if href.startswith("/"):
            return self.base_url + href
        return href
