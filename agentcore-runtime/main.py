from __future__ import annotations

from dataclasses import asdict
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from jawsug_calendar_agent import config
from jawsug_calendar_agent.browser_workflow import (
    extract_future_events,
    is_probably_on_calendar,
    now_jst_iso,
    submit_form,
    to_form_payload,
)
from jawsug_calendar_agent.models import ConnpassEvent, FormPayload
from jawsug_calendar_agent.state import (
    get_event_state,
    mark_event_already_on_calendar,
    mark_event_failed,
    mark_event_submitted,
    reserve_event_for_submission,
)

app = BedrockAgentCoreApp()

FINAL_STATUSES = {"SUBMITTED", "ALREADY_ON_CALENDAR"}


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any) -> dict[str, Any]:
    mode = payload.get("mode", "daily_check")
    if mode == "health":
        return {
            "ok": True,
            "mode": mode,
            "form_submit_enabled": config.FORM_SUBMIT_ENABLED,
            "state_table": config.STATE_TABLE_NAME,
        }

    if mode == "preview_event":
        event = _event_from_payload(payload)
        form_payload = to_form_payload(event)
        return {
            "ok": True,
            "mode": mode,
            "event": asdict(event),
            "form_payload": asdict(form_payload),
            "current_state": get_event_state(config.STATE_TABLE_NAME, event.event_id),
        }

    if mode == "submit_approved_event":
        return _submit_approved_event(payload)

    if mode not in {"daily_check", "manual_check"}:
        return {"ok": False, "error": f"Unsupported mode: {mode}"}

    dry_run = payload.get("dry_run")
    if dry_run is None:
        dry_run = not config.FORM_SUBMIT_ENABLED
    dry_run = bool(dry_run)

    now_iso = payload.get("now_iso") or now_jst_iso()
    events = extract_future_events(now_iso)
    results: list[dict[str, Any]] = []

    for event in events:
        current_state = get_event_state(config.STATE_TABLE_NAME, event.event_id)
        if current_state and current_state.get("status") in FINAL_STATUSES:
            results.append(
                {
                    "event_id": event.event_id,
                    "status": "already_seen",
                    "state_status": current_state.get("status"),
                    "title": event.title,
                }
            )
            continue

        if not dry_run:
            reserved = reserve_event_for_submission(config.STATE_TABLE_NAME, event)
            if not reserved:
                results.append({"event_id": event.event_id, "status": "already_seen", "title": event.title})
                continue

        if is_probably_on_calendar(event):
            if not dry_run:
                mark_event_already_on_calendar(config.STATE_TABLE_NAME, event)
            results.append({"event_id": event.event_id, "status": "already_on_calendar", "title": event.title})
            continue

        form_payload = to_form_payload(event)
        if dry_run:
            mark_event_submitted(config.STATE_TABLE_NAME, event, dry_run=True)
            results.append(
                {
                    "event_id": event.event_id,
                    "status": "dry_run",
                    "title": event.title,
                    "form_payload": form_payload.__dict__,
                }
            )
            continue

        response = submit_form(form_payload)
        mark_event_submitted(config.STATE_TABLE_NAME, event, dry_run=False)
        results.append({"event_id": event.event_id, "status": "submitted", "title": event.title, "response": response})

    return {
        "ok": True,
        "mode": mode,
        "dry_run": dry_run,
        "checked_at": now_iso,
        "event_count": len(events),
        "results": results,
    }


def _event_from_payload(payload: dict[str, Any]) -> ConnpassEvent:
    event_payload = payload.get("event")
    if not isinstance(event_payload, dict):
        raise ValueError("payload.event is required")
    return ConnpassEvent(**event_payload)


def _form_payload_from_payload(payload: dict[str, Any], event: ConnpassEvent) -> FormPayload:
    form_payload = payload.get("form_payload")
    if form_payload is None:
        return to_form_payload(event)
    if not isinstance(form_payload, dict):
        raise ValueError("payload.form_payload must be an object")
    return FormPayload(**form_payload)


def _submit_approved_event(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("approved"):
        return {"ok": False, "mode": "submit_approved_event", "error": "approved=true is required"}
    if not config.FORM_SUBMIT_ENABLED:
        return {
            "ok": False,
            "mode": "submit_approved_event",
            "error": "FORM_SUBMIT_ENABLED is false. Refusing to submit the Google Form.",
        }

    event = _event_from_payload(payload)
    form_payload = _form_payload_from_payload(payload, event)
    current_state = get_event_state(config.STATE_TABLE_NAME, event.event_id)
    if current_state and current_state.get("status") in FINAL_STATUSES:
        return {
            "ok": True,
            "mode": "submit_approved_event",
            "status": "already_seen",
            "state_status": current_state.get("status"),
            "event": asdict(event),
            "form_payload": asdict(form_payload),
        }

    reserved = reserve_event_for_submission(config.STATE_TABLE_NAME, event)
    if not reserved:
        return {
            "ok": True,
            "mode": "submit_approved_event",
            "status": "already_seen",
            "event": asdict(event),
            "form_payload": asdict(form_payload),
        }

    if is_probably_on_calendar(event):
        mark_event_already_on_calendar(config.STATE_TABLE_NAME, event)
        return {
            "ok": True,
            "mode": "submit_approved_event",
            "status": "already_on_calendar",
            "event": asdict(event),
            "form_payload": asdict(form_payload),
        }

    try:
        response = submit_form(form_payload)
    except Exception as exc:
        mark_event_failed(config.STATE_TABLE_NAME, event, str(exc))
        return {
            "ok": False,
            "mode": "submit_approved_event",
            "status": "submit_failed",
            "error": str(exc),
            "event": asdict(event),
            "form_payload": asdict(form_payload),
        }

    mark_event_submitted(config.STATE_TABLE_NAME, event, dry_run=False)
    return {
        "ok": True,
        "mode": "submit_approved_event",
        "status": "submitted",
        "event": asdict(event),
        "form_payload": asdict(form_payload),
        "response": response,
    }


if __name__ == "__main__":
    app.run()
