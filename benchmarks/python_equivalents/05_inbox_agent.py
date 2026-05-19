import imaplib
import email as email_lib
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

class InboxMonitorAgent:
    def __init__(self):
        self.seen_threads: list[str] = []
        self.poll_interval = 5 * 60  # 5 minutes in seconds

    def _read_unread_emails(self) -> list[dict[str, Any]]:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login("user@example.com", "password")
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        emails = []
        for num in data[0].split():
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            emails.append({
                "subject": msg["Subject"],
                "from": msg["From"],
                "thread_id": msg.get("Message-ID", ""),
                "priority": 0.5,  # placeholder scoring
            })
        return emails

    def _summarize_email(self, email: dict, max_lines: int = 3) -> str:
        return f"From: {email['from']}\nSubject: {email['subject']}"

    def _notify_user(self, message: str, priority: str = "normal") -> None:
        logger.info(f"[{priority.upper()}] NOTIFY: {message}")
        print(f"[NOTIFICATION ({priority})] {message}")

    def on_email(self, email: dict) -> None:
        if email["priority"] <= 0.7:
            return
        thread_id = email["thread_id"]
        if thread_id in self.seen_threads:
            return
        self.seen_threads.append(thread_id)
        summary = self._summarize_email(email, max_lines=3)
        self._notify_user(summary, priority="high")

    def run(self) -> None:
        logger.info("InboxMonitor agent started")
        while True:
            try:
                emails = self._read_unread_emails()
                for e in emails:
                    self.on_email(e)
            except Exception as exc:
                logger.error(f"Error polling inbox: {exc}")
            time.sleep(self.poll_interval)

if __name__ == "__main__":
    agent = InboxMonitorAgent()
    agent.run()
