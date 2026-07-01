"""
emailer.py  -  send an answer by email (optional).

If EMAIL_ADDRESS + EMAIL_APP_PASSWORD are set in .env, this sends the email directly
via SMTP (defaults to Gmail). If not configured, the app falls back to opening a
pre-filled email in the user's mail app (handled on the web page). Never raises.
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def is_configured() -> bool:
    return bool(os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_APP_PASSWORD"))


def send_email(to: str, subject: str, body: str):
    """Return (ok, info). ok=False with info='not_configured' if no SMTP creds."""
    user = os.getenv("EMAIL_ADDRESS")
    pw = os.getenv("EMAIL_APP_PASSWORD")
    if not (user and pw):
        return (False, "not_configured")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("PNB Sahayak", user))
    msg["To"] = to
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, pw)
            server.sendmail(user, [to], msg.as_string())
        return (True, "sent")
    except Exception as e:
        return (False, str(e))
