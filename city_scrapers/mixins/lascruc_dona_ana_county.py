import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import scrapy
from city_scrapers_core.constants import BOARD, COMMISSION, COMMITTEE, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.relativedelta import relativedelta


class LascrucDonaAnaCountySpiderMeta(type):
    """
    Metaclass that enforces required static variables on child spiders.
    """

    def __init__(cls, name, bases, dct):
        if name == "LascrucDonaAnaCountySpiderMixin":
            super().__init__(name, bases, dct)
            return

        if any(
            getattr(base, "__name__", "") == "LascrucDonaAnaCountySpiderMixin"
            for base in bases
        ):
            required_static_vars = ["agency", "name"]
            missing_vars = [var for var in required_static_vars if var not in dct]

            if missing_vars:
                missing_vars_str = ", ".join(missing_vars)
                raise NotImplementedError(
                    f"{name} must define the following static variable(s): "
                    f"{missing_vars_str}."
                )

        super().__init__(name, bases, dct)


class LascrucDonaAnaCountySpiderMixin(
    CityScrapersSpider, metaclass=LascrucDonaAnaCountySpiderMeta
):
    agency = None
    timezone = "America/Denver"
    api_base_url = "https://donaanaconm.api.civicclerk.com"
    portal_base_url = "https://donaanaconm.portal.civicclerk.com"
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    # Default location - consistent across all Dona Ana County meetings
    location_name = "Dona Ana County"
    default_address = "845 N Motel Blvd, Las Cruces, NM 88007"

    # Date range configuration (can be overridden by subclasses)
    # First meeting in CivicClerk API: 2015-05-04
    start_date_str = "2019-01-01"
    months_ahead = 12

    def start_requests(self):
        """Generate API requests for past and upcoming events."""
        compliance_url = getattr(self, "compliance_url", None)
        if compliance_url:
            yield scrapy.Request(compliance_url, callback=self.parse_compliance)
            return
        else:
            today = datetime.now(tz=ZoneInfo(self.timezone))

            start_date = date.fromisoformat(self.start_date_str)
            end_date = today + relativedelta(months=self.months_ahead)

            start_date_str = start_date.isoformat()
            end_date_str = end_date.isoformat()
            today_str = today.isoformat()

            ids_str = self.category_id
            category_filter = f"categoryId+in+({ids_str})"

            urls = [
                # Past events (from start_date to today)
                f"{self.api_base_url}/v1/Events?$filter=startDateTime+ge+{start_date_str}+and+startDateTime+lt+{today_str}+and+{category_filter}&$orderby=startDateTime+desc,+eventName+desc",  # noqa
                # Upcoming events (today to end_date)
                f"{self.api_base_url}/v1/Events?$filter=startDateTime+ge+{today_str}+and+startDateTime+le+{end_date_str}+and+{category_filter}&$orderby=startDateTime+asc,+eventName+asc",  # noqa
            ]
            for url in urls:
                yield scrapy.Request(url, callback=self.parse)

    def parse_compliance(self, response):
        """Parse HTML response from Dona Ana County compliance office page."""
        entries = response.css("li.doc-center-entry")

        for entry in entries:
            date_text = entry.css("span.agenda-date::text").get("").strip()
            raw_title = entry.css("span.agenda-name::text").get("").strip()

            start = self._parse_compliance_date(date_text)
            if not start:
                continue

            title = self._parse_title(raw_title) if raw_title else self.agency

            links = self._parse_compliance_links(entry, response)

            yield self._build_meeting(
                title=title,
                description="",
                start=start,
                end=None,
                location={
                    "name": self.location_name,
                    "address": self.default_address,
                },
                links=links,
                source=self.compliance_url,
                raw_title=raw_title,
            )

    def parse(self, response):
        """
        Parse JSON response from CivicClerk API and yield Meeting items.
        """
        data = response.json()
        events = data.get("value", [])

        for raw_event in events:
            event_id = raw_event.get("id")
            if not event_id:
                continue

            raw_title = raw_event.get("eventName") or self.agency

            yield self._build_meeting(
                title=self._parse_title(raw_title),
                description=raw_event.get("eventDescription") or "",
                start=self._parse_start(raw_event),
                end=self._parse_end(raw_event),
                location=self._parse_location(raw_event),
                links=self._parse_links(raw_event),
                source=f"{self.portal_base_url}/event/{event_id}",
                raw_title=raw_title,
                category_name=raw_event.get("categoryName"),
            )

        # Handle pagination
        next_link = data.get("@odata.nextLink")
        if next_link:
            yield scrapy.Request(next_link, callback=self.parse)

    def _build_meeting(
        self,
        title,
        description,
        start,
        end,
        location,
        links,
        source,
        raw_title,
        category_name=None,  # noqa
    ):
        classification_text = f"{title} {category_name or self.agency}"
        meeting = Meeting(
            title=title,
            description=description,
            classification=self._parse_classification(classification_text),
            start=start,
            end=end,
            all_day=False,
            time_notes="",
            location=location,
            links=links,
            source=source,
        )
        meeting["status"] = self._get_status(meeting, text=raw_title)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_classification(self, title):
        """
        Parse classification from meeting title and agency name.
        """
        classification_map = {
            "commission": COMMISSION,
            "board": BOARD,
            "committee": COMMITTEE,
        }

        for keyword, classification in classification_map.items():
            if keyword in title.lower():
                return classification

        return NOT_CLASSIFIED

    def _parse_title(self, raw_title):
        if not raw_title:
            self.logger.warning(
                "Empty or missing title, falling back to agency: %s", self.agency
            )  # noqa
            return self.agency

        title = raw_title.strip()

        trailing_date_pattern = (
            r"\s*[,.]?\s*(?:"
            r"\d{1,2}[./]\d{1,2}[./]\d{2,4}|"
            r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|"
            r"[A-Za-z]{3,9}\s*\d{1,2}\s*[.,]?\s*\d{2,4}"
            r")\s*$"
        )

        title = re.sub(trailing_date_pattern, "", title)
        title = re.sub(r"[,.\s]+$", "", title)
        title = re.sub(r"\s+", " ", title).strip()

        if not title:
            self.logger.warning(
                "Title reduced to empty after stripping "
                "dates from '%s', falling back to "
                "agency: %s",
                raw_title,
                self.agency,
            )
        return title or self.agency

    def _parse_start(self, raw_event):
        """Parse start datetime as a naive datetime object."""
        start_str = raw_event.get("startDateTime")
        return self._parse_dt(start_str)

    def _parse_end(self, raw_event):
        """Parse end datetime as a naive datetime object. Added by pipeline if None"""
        end_str = raw_event.get("endDateTime")
        return self._parse_dt(end_str)

    def _parse_location(self, raw_event):
        """Parse or generate location."""
        event_location = raw_event.get("eventLocation") or {}

        address_parts = [
            event_location.get("address1") or "",
            event_location.get("address2") or "",
            ", ".join(
                part
                for part in [
                    event_location.get("city"),
                    event_location.get("state"),
                    event_location.get("zipCode"),
                ]
                if part
            ),
        ]
        address = " ".join(part for part in address_parts if part).strip()

        # Default address if none provided in the event
        if not address:
            address = self.default_address

        return {
            "name": self.location_name,
            "address": address,
        }

    def _parse_links(self, raw_event):
        """Parse published files into meeting links."""
        event_id = raw_event.get("id")
        if not event_id:
            return []

        links = []
        seen = set()

        for file_info in raw_event.get("publishedFiles", []):
            file_id = file_info.get("fileId")
            if not file_id:
                continue

            link = {
                "title": (file_info.get("type") or "Document").strip(),
                "href": f"{self.portal_base_url}/event/{event_id}/files/agenda/{file_id}",  # noqa
            }

            key = (link["title"], link["href"])
            if key in seen:
                continue
            seen.add(key)
            links.append(link)

        return links

    def _parse_compliance_date(self, date_text):
        """Parse a date string like '11/22/2024' into a naive datetime."""
        if not date_text:
            return None
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(date_text, fmt).replace(hour=10)
            except ValueError:
                continue
        return None

    def _parse_compliance_links(self, entry, response):
        """Extract agenda, minutes, packet, and video links from a compliance entry."""
        links = []
        link_columns = [
            ("td.agenda_doc a", "Agenda"),
            ("td.packet_doc a", "Packet"),
            ("td.minutes_doc a", "Minutes"),
            ("td.video_url a", "Video"),
        ]
        for selector, title in link_columns:
            link_el = entry.css(selector)
            href = link_el.attrib.get("href", "").strip() if link_el else ""
            if href:
                if not href.startswith(("http://", "https://", "/")):
                    href = "/" + href
                href = href.replace(" ", "%20")
                href = response.urljoin(href)
                links.append({"title": title, "href": href})
        return links

    def _parse_dt(self, dt_str):
        """Parse an ISO datetime string into a naive datetime object.

        CivicClerk API appends 'Z' but times are already local,
        not true UTC. We strip the timezone rather than converting.
        """
        if not dt_str:
            return None
        dt_str = dt_str.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(dt_str)
            # Return naive datetime (strip timezone)
            return dt.replace(tzinfo=None)
        except ValueError:
            return None
