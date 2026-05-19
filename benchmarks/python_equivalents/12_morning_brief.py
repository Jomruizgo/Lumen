import imaplib
import email as email_lib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import openai

logger = logging.getLogger(__name__)
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"

def read_emails_last_24h() -> list[dict]:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login("user@example.com", "password")
    mail.select("inbox")
    since = (datetime.now() - timedelta(hours=24)).strftime("%d-%b-%Y")
    _, data = mail.search(None, f'(SINCE "{since}")')
    messages = []
    for num in data[0].split():
        _, msg_data = mail.fetch(num, "(RFC822)")
        msg = email_lib.message_from_bytes(msg_data[0][1])
        messages.append({"subject": msg["Subject"], "from": msg["From"], "priority": 0.5})
    return messages

def read_calendar_today(token: str) -> list[dict]:
    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow().replace(hour=23, minute=59)).isoformat() + "Z"
    resp = httpx.get(
        f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"timeMin": now, "timeMax": end, "singleEvents": True},
    )
    return resp.json().get("items", [])

def llm_summarize(emails: list[dict], events: list[dict]) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": (
                "Resume estos correos urgentes y eventos de hoy. "
                f"Correos: {json.dumps(emails)}. "
                f"Eventos: {json.dumps(events)}."
            ),
        }],
    )
    return response.choices[0].message.content or ""

def notify_user(message: str, priority: str = "normal") -> None:
    logger.info(f"[{priority.upper()}] {message}")

def morning_brief() -> None:
    emails = read_emails_last_24h()
    urgent = [e for e in emails if e.get("priority", 0) > 0.7]
    token = "oauth_token_placeholder"
    events = read_calendar_today(token)
    summary = llm_summarize(urgent, events)
    notify_user(summary, priority="high")

if __name__ == "__main__":
    morning_brief()
