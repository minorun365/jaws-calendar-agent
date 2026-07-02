from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from html import unescape
from zoneinfo import ZoneInfo

from strands import Agent
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser

from . import config
from .models import ConnpassEvent, FormPayload


SYSTEM_PROMPT = """You are a careful browser automation agent for JAWS-UG Tokyo calendar registration.
Extract only future events from the JAWS-UG Tokyo connpass event list.
Return compact JSON only. Never submit a Google Form unless the caller explicitly asks for submission."""


def _agent() -> Agent:
    browser = AgentCoreBrowser()
    model = BedrockModel(region_name=config.BEDROCK_REGION, model_id=config.BEDROCK_MODEL_ID)
    return Agent(model=model, tools=[browser.browser], system_prompt=SYSTEM_PROMPT)


def extract_future_events(now_iso: str) -> list[ConnpassEvent]:
    html_events = _extract_future_events_from_connpass_html(now_iso)
    if html_events:
        return html_events

    prompt = f"""
Open {config.CONNPASS_EVENTS_URL} with the browser tool.
Find JAWS-UG Tokyo future events after {now_iso}.
For each event, open the detail page if needed and extract:
event_id from the connpass URL, title, url, starts_at ISO8601 JST, ends_at ISO8601 JST, location.
Return JSON array only with keys event_id,title,url,starts_at,ends_at,location.
"""
    result = str(_agent()(prompt))
    data = _extract_json(result)
    return [ConnpassEvent(**item) for item in data]


def _extract_future_events_from_connpass_html(now_iso: str) -> list[ConnpassEvent]:
    now = datetime.fromisoformat(now_iso).astimezone(ZoneInfo("Asia/Tokyo"))
    html = _fetch_text(config.CONNPASS_EVENTS_URL)
    if not html:
        return []

    events: list[ConnpassEvent] = []
    blocks = re.findall(
        r'<div class="group_event_list vevent">(.*?)(?=<div class="group_event_list vevent">|\Z)',
        html,
        re.DOTALL,
    )
    for block in blocks:
        if "開催前" not in block:
            continue
        url_match = re.search(r'<a class="url summary" href="([^"]+)">(.*?)</a>', block, re.DOTALL)
        starts_match = re.search(r'dtstart.*?title="([^"]+)"', block, re.DOTALL)
        ends_match = re.search(r'dtend.*?title="([^"]+)"', block, re.DOTALL)
        if not url_match or not starts_match or not ends_match:
            continue

        starts = datetime.fromisoformat(starts_match.group(1)).astimezone(ZoneInfo("Asia/Tokyo"))
        if starts <= now:
            continue

        url = unescape(url_match.group(1))
        event_id_match = re.search(r"/event/(\d+)/", url)
        if not event_id_match:
            continue

        events.append(
            ConnpassEvent(
                event_id=event_id_match.group(1),
                title=_strip_tags(url_match.group(2)),
                url=url,
                starts_at=starts.isoformat(),
                ends_at=datetime.fromisoformat(ends_match.group(1)).astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
                location=_extract_location_from_connpass_detail(url),
            )
        )

    return events


def _extract_location_from_connpass_detail(url: str) -> str:
    html = _fetch_text(url)
    if not html:
        return ""
    match = re.search(r'<p class="place_name em"><span class="fn org">(.*?)</span></p>', html, re.DOTALL)
    if match:
        return _strip_tags(match.group(1))
    calendar_match = re.search(r"[?&]location=([^&\"]+)", html)
    if calendar_match:
        return urllib.parse.unquote(calendar_match.group(1))
    return ""


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        return ""


def _strip_tags(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text)
    return unescape(re.sub(r"\s+", " ", without_tags)).strip()


def is_probably_on_calendar(event: ConnpassEvent) -> bool:
    api_result = _is_on_public_google_calendar(event)
    if api_result is not None:
        return api_result

    prompt = f"""
Open {config.JAWSUG_CALENDAR_URL}.
Check whether this event already appears on the page:
title: {event.title}
url: {event.url}
starts_at: {event.starts_at}
Return JSON only: {{"exists": true}} or {{"exists": false}}.
"""
    result = str(_agent()(prompt))
    data = _extract_json(result)
    if isinstance(data, dict):
        return bool(data.get("exists"))
    return False


def _is_on_public_google_calendar(event: ConnpassEvent) -> bool | None:
    if not config.JAWSUG_CALENDAR_ID or not config.JAWSUG_CALENDAR_API_KEY:
        return None

    starts = datetime.fromisoformat(event.starts_at).astimezone(ZoneInfo("Asia/Tokyo"))
    time_min = starts.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + timedelta(days=1)
    calendar_id = urllib.parse.quote(config.JAWSUG_CALENDAR_ID, safe="")
    query = urllib.parse.urlencode(
        {
            "key": config.JAWSUG_CALENDAR_API_KEY,
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": "Asia/Tokyo",
            "singleEvents": "true",
            "maxResults": "100",
        }
    )
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?{query}"

    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.load(response)
    except Exception:
        return None

    event_names = {_normalize_title(event.title), _normalize_title(to_form_payload(event).event_name)}
    for item in data.get("items", []):
        summary = _normalize_title(str(item.get("summary", "")))
        description = str(item.get("description", ""))
        html_link = str(item.get("htmlLink", ""))
        if event.url and (event.url in description or event.url in html_link):
            return True
        if summary and any(name and (name == summary or name in summary or summary in name) for name in event_names):
            return True
    return False


def _normalize_title(title: str) -> str:
    normalized = re.sub(r"\s+", "", title)
    return normalized.lower()


def submit_form(payload: FormPayload) -> str:
    if not config.GOOGLE_FORM_URL:
        raise ValueError("GOOGLE_FORM_URL is required to submit the Google Form.")

    prompt = f"""
Open this Google Form: {config.GOOGLE_FORM_URL}
Fill fields exactly as follows:
開催地域名: {payload.region_name}
勉強会名: {payload.event_name}
日付: {payload.date}
開始時刻: {payload.start_time}
終了時刻: {payload.end_time}
場所: {payload.location}
イベントURL: {payload.event_url}
記入者氏名: {payload.submitter_name}
Submit the form and return JSON only: {{"submitted": true, "message": "..."}}
"""
    return str(_agent()(prompt))


def to_form_payload(event: ConnpassEvent) -> FormPayload:
    starts = datetime.fromisoformat(event.starts_at).astimezone(ZoneInfo("Asia/Tokyo"))
    ends = datetime.fromisoformat(event.ends_at).astimezone(ZoneInfo("Asia/Tokyo"))
    title = event.title
    event_name = re.sub(r"^\s*JAWS-UG\s*東京\s*", "", title, flags=re.IGNORECASE).strip()
    return FormPayload(
        region_name="東京",
        event_name=event_name or title,
        date=starts.strftime("%Y-%m-%d"),
        start_time=starts.strftime("%H:%M"),
        end_time=ends.strftime("%H:%M"),
        location=event.location,
        event_url=event.url,
        submitter_name=config.SUBMITTER_NAME,
    )


def now_jst_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()


def _extract_json(text: str):
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in agent response: {text[:500]}")
    return json.loads(match.group(1))
