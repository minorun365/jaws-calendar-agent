from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnpassEvent:
    event_id: str
    title: str
    url: str
    starts_at: str
    ends_at: str
    location: str = ""


@dataclass(frozen=True)
class FormPayload:
    region_name: str
    event_name: str
    date: str
    start_time: str
    end_time: str
    location: str
    event_url: str
    submitter_name: str
