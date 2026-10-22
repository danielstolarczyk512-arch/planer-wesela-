"""Wysyłka e-maili. Nadawane zawsze przez kolejkę zadań (worker), nigdy w trakcie żądania HTTP."""

import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.mail_templates import Email
from app.jobs.queue import enqueue

SEND_EMAIL_JOB = "send_email"


def queue_email(db: Session, to: str, subject: str, body: str, html: str | None = None) -> None:
    # Payload może zawierać jednorazowy link, więc worker czyści go po wysyłce.
    payload = {"to": to, "subject": subject, "body": body}
    if html:
        payload["html"] = html
    enqueue(db, SEND_EMAIL_JOB, payload)


def queue_mail(db: Session, to: str, mail: Email) -> None:
    """Wiadomość z szablonu (`mail_templates.build`): tekst + HTML."""
    queue_email(db, to, mail.subject, mail.text, mail.html)


def build_message(to: str, subject: str, body: str, html: str | None = None) -> EmailMessage:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        # multipart/alternative: klient bez HTML pokaże tekst.
        msg.add_alternative(html, subtype="html")
    return msg


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    settings = get_settings()
    msg = build_message(to, subject, body, html)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(msg)
