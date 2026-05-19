import logging
import time
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"

def read_calendar_today(token: str) -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat() + "Z"
    end_of_day = datetime.utcnow().replace(hour=23, minute=59, second=59).isoformat() + "Z"
    resp = httpx.get(
        f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"timeMin": now, "timeMax": end_of_day, "singleEvents": True},
    )
    return resp.json().get("items", [])

def notify_user(message: str, priority: str = "normal") -> None:
    logger.info(f"[{priority.upper()}] NOTIFY: {message}")
    print(f"[NOTIFY ({priority})] {message}")

def _get_event_titles(events: list[dict]) -> str:
    return ", ".join(e.get("summary", "Sin título") for e in events)

class DailyReminderAgent:
    """Runs at 8am every day (cron: 0 8 * * *)."""

    def __init__(self, calendar_token: str = "oauth_token_placeholder"):
        self.calendar_token = calendar_token

    def on_tick(self) -> None:
        events = read_calendar_today(self.calendar_token)
        if len(events) > 0:
            titles = _get_event_titles(events)
            summary = f"Hoy tienes {len(events)} eventos: {titles}"
            notify_user(summary, priority="normal")

    def run_forever(self, interval_seconds: int = 60) -> None:
        logger.info("DailyReminder agent started")
        while True:
            now = datetime.now()
            if now.hour == 8 and now.minute == 0:
                try:
                    self.on_tick()
                except Exception as exc:
                    logger.error(f"Error in on_tick: {exc}")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    agent = DailyReminderAgent()
    agent.run_forever()
