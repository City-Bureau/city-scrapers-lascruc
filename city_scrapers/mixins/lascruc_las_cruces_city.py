"""
Mixin and metaclass template for Las Cruces spiders that share a common data
source.

Required class variables on child spiders:
    name (str): Spider name/slug
    agency (str): Full agency name
    id (str): Unique identifier for the spider
"""

import json
from datetime import date, datetime, timezone
from html import unescape
from urllib.parse import quote, urlencode

import scrapy
from city_scrapers_core.constants import (
    BOARD,
    CANCELLED,
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
    Metaclass that enforces required static variables on child spiders.
    """

    def __init__(cls, name, bases, dct):
        if name == "SpiderFactoryTemplateMixin":
            super().__init__(name, bases, dct)
            return

        if any(
            getattr(base, "__name__", "") == "SpiderFactoryTemplateMixin"
            for base in bases
        ):
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
    source_url = "https://lascruces.civicweb.net/Portal/MeetingSchedule.aspx"
    meetings_api_url = (
        "https://lascruces.civicweb.net/Services/MeetingsService.svc/meetings"
    )
    video_api_url = "https://lascruces.civicweb.net/api/videolink"

    custom_settings = {"ROBOTSTXT_OBEY": False}

    include_non_public_documents = True

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
            name = item.get("Name", "")

            if not any(name.startswith(prefix) for prefix in prefixes):
                continue
            if any(name.startswith(exclude) for exclude in excludes):
                continue

            title = self._parse_title(item)
            start = self._parse_start(item)
            meeting = Meeting(
                title=title,
                description="",
                classification=self._parse_classification(title),
                start=start,
                end=None,
                all_day=False,
                time_notes=self._parse_time_notes(start),
                location=self._parse_location(item),
                links=[],
                source=self.source_url,
            )

            meeting_id = item.get("Id")
            if not meeting_id:
                meeting["status"] = self._get_status(meeting)
                meeting["id"] = self._get_id(meeting)
                yield meeting
                continue

            docs_url = (
                f"{self.meetings_api_url}/{meeting_id}/meetingDocuments"
                f"?_={int(datetime.now(timezone.utc).timestamp() * 1000)}"
            )

            yield scrapy.Request(
                url=docs_url,
                callback=self.parse_meeting_documents,
                cb_kwargs={"meeting": meeting, "meeting_id": meeting_id},
            )

    def parse_meeting_documents(self, response, meeting, meeting_id):
        documents = response.json()

        meeting["links"].extend(self._parse_document_links(documents))
        meeting["links"] = self._dedupe_links(meeting["links"])

        if self._is_cancelled(documents):
            meeting["status"] = CANCELLED
        else:
            meeting["status"] = self._get_status(meeting)

        video_url = (
            f"{self.video_api_url}/{meeting_id}"
            f"?_={int(datetime.now(timezone.utc).timestamp() * 1000)}"
        )

        yield scrapy.Request(
            url=video_url,
            callback=self.parse_video_link,
            cb_kwargs={"meeting": meeting},
        )

    def parse_video_link(self, response, meeting):
        video_href = self._parse_video_link(response)

        if video_href:
            meeting["links"].append({"href": video_href, "title": "Video"})

        meeting["links"] = self._dedupe_links(meeting["links"])
        meeting["id"] = self._get_id(meeting)
        yield meeting

    def _parse_video_link(self, response):
        text = response.text.strip()

        if not text or text == '""':
            return None

        if text.startswith("http"):
            return text

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        # Handle double-encoded JSON
        if isinstance(data, str):
            data = data.strip()
            if not data:
                return None
            if data.startswith("http"):
                return data
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return None

        if isinstance(data, list):
            if not data:
                return None
            data = data[0]

        if not isinstance(data, dict) or not data.get("ShowVideoLink"):
            return None

        youtube_event_id = data.get("YouTubeEventId")
        if data.get("YouTube") and youtube_event_id:
            return f"https://www.youtube.com/watch?v={youtube_event_id}"

        document_id = data.get("DocumentId") or data.get("Id")
        if document_id:
            return (
                f"https://lascruces.civicweb.net/document/"
                f"{document_id}/?splitscreen=true&media=true"
            )

        return None

    def _is_cancelled(self, documents):
        for doc in documents:
            if not doc.get("IsPublic") and not self.include_non_public_documents:
                continue

            searchable_text = " ".join(
                [
                    str(doc.get("Html", "")),
                    str(doc.get("AgendaCover", "")),
                    str(doc.get("Name", "")),
                ]
            ).lower()

            if "cancelled" in searchable_text or "canceled" in searchable_text:
                return True

        return False

    def _parse_document_links(self, documents):
        agenda_by_name = {}
        other_links = []

        for doc in documents:
            if not doc.get("IsPublic") and not self.include_non_public_documents:
                continue

            href = self._build_document_url(doc)
            if not href:
                continue

            name = unescape((doc.get("Name") or "").strip())
            doc_type = doc.get("DocumentType")

            if doc_type in (1, 4):
                label = "Agenda"
            elif doc_type in (2, 10):
                label = "Minutes"
            else:
                label = "Document"

            title = f"{label}: {name}" if name else label
            link = {"href": href, "title": title}

            if label == "Agenda":
                existing = agenda_by_name.get(name)
                if existing is None or (
                    href.endswith(".pdf") and not existing["href"].endswith(".pdf")
                ):
                    agenda_by_name[name] = link
            else:
                other_links.append(link)

        return list(agenda_by_name.values()) + other_links

    def _build_document_url(self, doc):
        doc_id = doc.get("Id")
        name = (doc.get("Name") or "").strip()

        if not doc_id:
            return None

        if name:
            encoded_name = quote(unescape(name), safe="")
            if doc.get("Html"):
                return (
                    f"https://lascruces.civicweb.net/document/"
                    f"{doc_id}/{encoded_name}.html"
                )
            return (
                f"https://lascruces.civicweb.net/document/"
                f"{doc_id}/{encoded_name}.pdf"
            )

        return f"https://lascruces.civicweb.net/document/{doc_id}/"

    def _dedupe_links(self, links):
        seen = set()
        unique_links = []

        for link in links:
            key = (link.get("href", ""), link.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            unique_links.append(link)

        return unique_links

    def _parse_title(self, item):
        title = item.get("Name", "")
        title = title.replace("- ", " - ")
        parts = title.rsplit(" - ", 1)
        title = parts[0] if len(parts) > 1 else title
        title = title.replace("  ", " ")
        return title.strip()

    def _parse_classification(self, title):
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
        dt_str = item.get("MeetingDateTime", "")
        if dt_str:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return None

    def _parse_time_notes(self, start_time):
        if start_time and start_time.hour == 0 and start_time.minute == 0:
            return "Please check meeting details for more accurate time"
        return ""

    def _parse_location(self, item):
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

        return {"address": "", "name": location}
