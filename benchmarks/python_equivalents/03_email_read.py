import imaplib
import email as email_lib
from datetime import datetime, timedelta

def read_recent_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login("user@example.com", "password")
    mail.select("inbox")

    since = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
    _, data = mail.search(None, f'(SINCE "{since}")')

    emails = []
    for num in data[0].split():
        _, msg_data = mail.fetch(num, "(RFC822)")
        msg = email_lib.message_from_bytes(msg_data[0][1])
        emails.append({"subject": msg["Subject"], "from": msg["From"], "priority": 0.5})

    urgent = [e for e in emails if e.get("priority", 0) > 0.7]
    print(f"Tienes {len(urgent)} correos urgentes")

if __name__ == "__main__":
    read_recent_emails()
