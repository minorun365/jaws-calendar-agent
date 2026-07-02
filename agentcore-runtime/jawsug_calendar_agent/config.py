from __future__ import annotations

import os


CONNPASS_EVENTS_URL = os.environ.get("CONNPASS_EVENTS_URL", "https://jawsug.connpass.com/event/")
JAWSUG_CALENDAR_URL = os.environ.get("JAWSUG_CALENDAR_URL", "https://jaws-ug.jp/calendar/")
JAWSUG_CALENDAR_ID = os.environ.get(
    "JAWSUG_CALENDAR_ID",
    "bm4nl4f76dop3h66n7a4ea67r8@group.calendar.google.com",
)
JAWSUG_CALENDAR_API_KEY = os.environ.get("JAWSUG_CALENDAR_API_KEY", "")
GOOGLE_FORM_URL = os.environ.get("GOOGLE_FORM_URL", "")
STATE_TABLE_NAME = os.environ.get("STATE_TABLE_NAME", "")
FORM_SUBMIT_ENABLED = os.environ.get("FORM_SUBMIT_ENABLED", "false").lower() == "true"
SUBMITTER_NAME = os.environ.get("SUBMITTER_NAME", "みのるん（AgentCoreが代筆）")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
