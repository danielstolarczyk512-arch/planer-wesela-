# ruff: noqa: E501
"""Wysyłka e-maili. Nadawane zawsze przez kolejkę zadań (worker), nigdy w trakcie żądania HTTP."""

import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import LOCAL_SMTP_HOSTS, get_settings
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


class DeliveryError(Exception):
    """Wynik wysyłki zapytań do firm: rozróżniamy to, co wolno ponowić, od tego, czego nie wolno."""


class DeliveryTemporary(DeliveryError):
    """Serwer na pewno NIE przyjął wiadomości (brak połączenia, 4xx) — ponowienie jest bezpieczne."""


class DeliveryRejected(DeliveryError):
    """Serwer odrzucił wiadomość definitywnie (5xx, odrzucony adresat) — ponowienie nie pomoże."""


class DeliveryUncertain(DeliveryError):
    """Awaria w trakcie przekazywania: wiadomość MOGŁA zostać przyjęta. Nie ponawiamy automatycznie."""


def deliver(msg: EmailMessage) -> None:
    """Wysyła jedną wiadomość i klasyfikuje niepowodzenia (SMTP nie gwarantuje exactly-once)."""
    settings = get_settings()
    try:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    except (OSError, smtplib.SMTPException) as exc:  # nic nie zostało przekazane
        raise DeliveryTemporary(type(exc).__name__) from exc
    try:
        with smtp:
            try:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            except smtplib.SMTPAuthenticationError as exc:
                raise DeliveryRejected("SMTPAuthenticationError") from exc
            except (OSError, smtplib.SMTPException) as exc:
                raise DeliveryTemporary(type(exc).__name__) from exc
            try:
                smtp.send_message(msg)
            except smtplib.SMTPRecipientsRefused as exc:
                raise DeliveryRejected("SMTPRecipientsRefused") from exc
            except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
                code = int(getattr(exc, "smtp_code", 0) or 0)
                if 400 <= code < 500:
                    raise DeliveryTemporary(f"SMTP {code}") from exc
                raise DeliveryRejected(f"SMTP {code}") from exc
            except smtplib.SMTPHeloError as exc:
                raise DeliveryTemporary("SMTPHeloError") from exc
            except (TimeoutError, smtplib.SMTPException, OSError) as exc:
                raise DeliveryUncertain(type(exc).__name__) from exc
    except DeliveryError:
        raise
    except (smtplib.SMTPException, OSError) as exc:
        # Błąd przy zamykaniu połączenia po udanym przekazaniu nie unieważnia wysyłki.
        raise DeliveryUncertain(type(exc).__name__) from exc


def outbound_allowed() -> bool:
    """Etap MVP: poczta do firm trafia wyłącznie do lokalnego serwera (Mailpit), chyba że
    właściciel jawnie włączy prawdziwą wysyłkę (`WP_INQUIRY_REAL_SMTP`, etap 4)."""
    settings = get_settings()
    return settings.inquiry_real_smtp or settings.smtp_host in LOCAL_SMTP_HOSTS
