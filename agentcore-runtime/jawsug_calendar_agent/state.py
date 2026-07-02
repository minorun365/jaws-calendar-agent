from __future__ import annotations

from decimal import Decimal
import time
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

from .models import ConnpassEvent


def _table(table_name: str):
    return boto3.resource("dynamodb").Table(table_name)


def get_event_state(table_name: str, event_id: str) -> dict[str, Any] | None:
    if not table_name:
        return None
    response = _table(table_name).get_item(Key={"pk": f"EVENT#{event_id}", "sk": "STATE"})
    item = response.get("Item")
    if item is None:
        return None
    return _json_safe(item)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_json_safe(nested) for nested in value]
    return value


def reserve_event_for_submission(table_name: str, event: ConnpassEvent) -> bool:
    if not table_name:
        return True
    table = _table(table_name)
    now = int(time.time())
    stale_reserved_before = now - 30 * 60
    item = {
        "pk": f"EVENT#{event.event_id}",
        "sk": "STATE",
        "event_id": event.event_id,
        "title": event.title,
        "event_url": event.url,
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "status": "RESERVED",
        "created_at_epoch": now,
        "updated_at_epoch": now,
    }
    try:
        table.put_item(
            Item=item,
            ConditionExpression=(
                Attr("pk").not_exists()
                | Attr("status").eq("DRY_RUN")
                | Attr("status").eq("FAILED")
                | (Attr("status").eq("RESERVED") & Attr("updated_at_epoch").lt(stale_reserved_before))
            ),
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def mark_event_submitted(table_name: str, event: ConnpassEvent, dry_run: bool) -> None:
    if not table_name:
        return
    _table(table_name).update_item(
        Key={"pk": f"EVENT#{event.event_id}", "sk": "STATE"},
        UpdateExpression="SET #status = :status, submitted_at_epoch = :now, dry_run = :dry_run, updated_at_epoch = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "DRY_RUN" if dry_run else "SUBMITTED",
            ":now": int(time.time()),
            ":dry_run": dry_run,
        },
    )


def mark_event_already_on_calendar(table_name: str, event: ConnpassEvent) -> None:
    if not table_name:
        return
    _table(table_name).update_item(
        Key={"pk": f"EVENT#{event.event_id}", "sk": "STATE"},
        UpdateExpression="SET #status = :status, calendar_checked_at_epoch = :now, updated_at_epoch = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "ALREADY_ON_CALENDAR",
            ":now": int(time.time()),
        },
    )


def mark_event_failed(table_name: str, event: ConnpassEvent, error_message: str) -> None:
    if not table_name:
        return
    _table(table_name).update_item(
        Key={"pk": f"EVENT#{event.event_id}", "sk": "STATE"},
        UpdateExpression="SET #status = :status, error_message = :error, updated_at_epoch = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "FAILED",
            ":error": error_message[:1000],
            ":now": int(time.time()),
        },
    )
