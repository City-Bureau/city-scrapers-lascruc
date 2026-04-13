import re
from datetime import datetime

import scrapy
from city_scrapers_core.constants import (
    CANCELLED,
    CITY_COUNCIL,
    COMMISSION,
    NOT_CLASSIFIED,
)
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class LasCrucesSunlandParkCityMixinMeta(type):
    """
    Metaclass that enforces required static variables on child spiders.
    """

    def __init__(cls, name, bases, dct):
        if name == "LasCrucesSunlandParkCityMixin":
            super().__init__(name, bases, dct)
            return

        if any(
            getattr(base, "__name__", "") == "LasCrucesSunlandParkCityMixin"
            for base in bases
        ):
            required_static_vars = ["agency", "name", "id", "meeting_type_label"]
            missing_vars = [var for var in required_static_vars if var not in dct]

            if missing_vars:
                missing_vars_str = ", ".join(missing_vars)
                raise NotImplementedError(
                    f"{name} must define the following static variable(s): "
                    f"{missing_vars_str}."
                )

        super().__init__(name, bases, dct)


class LasCrucesSunlandParkCityMixin(
    CityScrapersSpider, metaclass=LasCrucesSunlandParkCityMixinMeta
):
    timezone = "America/Denver"
    source_url = "https://sunlandpark-nm.gov/city-clerk/#agenda"

    custom_settings = {"ROBOTSTXT_OBEY": False}

    def start_requests(self):
        yield scrapy.Request(url=self.source_url, callback=self.parse)

    def parse(self, response):
        section = self._get_section_node(response)
        if not section:
            self.logger.warning(
                "Could not find section for %s", self.meeting_type_label
            )
            return
        month_nodes = section.css("ul.sub-menu > li.menu-item-has-children")
        for month_node in month_nodes:

            meeting_nodes = month_node.css("ul.sub-menu > li")
            for meeting_node in meeting_nodes:
                meeting = self._parse_meeting(meeting_node, response)
                if meeting:
                    yield meeting

    def _get_section_node(self, response):
        meeting_type_sections = response.css(
            "nav.elementor-nav-menu--main > ul.elementor-nav-menu > li.menu-item-has-children"  # noqa
        )

        for section in meeting_type_sections:
            meeting_type = section.css("a::text").get().strip()
            if meeting_type == self.meeting_type_label:
                return section

        return None

    def _parse_meeting(self, meeting_node, response):
        title = meeting_node.css("a")
        if not title:
            return None
        title_text = " ".join(
            part.strip() for part in title.css("::text").getall() if part.strip()
        ).strip()
        href = title.attrib.get("href")
        if not title_text or not href:
            return None

        start = self._parse_start(title_text)
        if not start:
            return None

        status = CANCELLED if self._is_cancelled(title_text) else None

        links = [{"href": response.urljoin(href), "title": "Agenda"}]

        video_url = meeting_node.css("ul.sub-menu li a::attr(href)").get()
        if video_url:
            links.append({"href": response.urljoin(video_url), "title": "Video"})

        meeting = Meeting(
            title=self._parse_title(title_text),
            description="",
            classification=self._parse_classification(),
            start=start,
            end=None,
            all_day=False,
            time_notes="Please refer to the agenda for meeting location details",
            location={"name": "", "address": ""},
            links=self._dedupe_links(links),
            source=self.source_url,
        )

        meeting["status"] = status or self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        return meeting

    def _parse_start(self, title_text):
        """Parse start datetime from title text"""
        patterns = [
            r"(\w+ \d{1,2},? \d{4},? \d{1,2}:\d{2} \w{2})",
            r"(\d{1,2}/\d{1,2}/\d{4},? \d{1,2}:\d{2} \w{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})\s*[–-]\s*(\d{1,2}:\d{2} \w{2})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        date_formats = [
            "%B %d %Y %I:%M %p",
            "%b %d %Y %I:%M %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y",
        ]

        for i, pattern in enumerate(patterns):
            date_match = re.search(pattern, title_text)
            if date_match:
                if i == 2:
                    date_str = date_match.group(1)
                    time_str = date_match.group(2)
                    combined_str = f"{date_str} {time_str}"
                else:
                    date_str = date_match.group(1).replace(",", "").strip()
                    combined_str = date_str

                for fmt in date_formats:
                    try:
                        return datetime.strptime(combined_str, fmt)
                    except ValueError:
                        self.logger.warning(
                            "Failed to parse date from '%s' in '%s'",
                            combined_str,
                            title_text,
                        )

        return None

    def _parse_title(self, title_text):
        date_patterns = [
            r"–?\s*\w+ \d{1,2},? \d{4},? \d{1,2}:\d{2} \w{2}",
            r"–?\s*\d{1,2}/\d{1,2}/\d{4},? \d{1,2}:\d{2} \w{2}",
            r"–?\s*\d{1,2}/\d{1,2}/\d{4}\s*[–-]\s*\d{1,2}:\d{2} \w{2}",
            r"–?\s*\d{1,2}/\d{1,2}/\d{4}",
        ]

        cleanup_patterns = [
            r"(?:NOTICE\s+OF\s+)?CANCELL(?:ATION|ED)\s+(?:OF\s+)?",
            r"\s+VIDEO:.*$",
            r"\s*\|\s*\w+ \d{1,2}(?:st|nd|rd|th).*$",
        ]

        title = title_text
        for pattern in date_patterns:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

        for pattern in cleanup_patterns:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

        title = re.sub(r":\s*$", "", title).strip()

        return title if title else title_text

    def _parse_classification(self):
        label = getattr(self, "meeting_type_label", "").lower()

        if "city council" in label:
            return CITY_COUNCIL
        elif "planning" in label and "zoning" in label:
            return COMMISSION
        else:
            return NOT_CLASSIFIED

    def _dedupe_links(self, links):
        seen = set()
        deduped = []

        for link in links:
            link_tuple = (link["href"], link["title"])
            if link_tuple not in seen:
                seen.add(link_tuple)
                deduped.append(link)

        return deduped

    def _is_cancelled(self, title_text):
        """Check if meeting is cancelled based on title text"""
        title_lower = title_text.lower()
        return (
            "cancellation" in title_lower
            or "cancelled" in title_lower
            or "canceled" in title_lower
        )
