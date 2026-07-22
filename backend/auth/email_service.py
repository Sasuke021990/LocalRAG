"""Password-reset email sending via SMTP (stdlib smtplib -- no new dependency)."""

import logging
import smtplib
from email.mime.text import MIMEText

from utils.config import config

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body: str, reply_to: str = "") -> bool:
    """
    Send a plain-text email via SMTP. Never raises — callers treat email as
    best-effort. Returns True on success. Skips silently (returns False) when
    SMTP isn't configured, so local/dev installs without SMTP don't error.
    """
    if not config.SMTP_HOST:
        logger.warning(f"SMTP not configured — skipping email '{subject}' to {to_email}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email '{subject}' sent to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send email '{subject}' to {to_email}: {exc}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """
    Sends the reset-password email. Never raises -- a broken SMTP config
    should not surface to the caller, which (per the non-leaking design
    of the password-reset-request endpoint) always responds 200
    regardless of whether the email actually existed or the send
    succeeded.
    """
    body = (
        f"Click this link to reset your Vaultly password:\n\n{reset_link}\n\n"
        "This link expires in 1 hour. If you didn't request this, you can ignore this email."
    )
    _send_email(to_email, "Reset your Vaultly password", body)


def send_contact_lead_email(admin_email: str, lead: dict) -> None:
    """
    Notify the admin of a new Customize-plan enquiry. Best-effort: the lead is
    also persisted, so a failed send never loses it. ``Reply-To`` is set to the
    lead's email so the admin can reply directly.
    """
    body = (
        "New Vaultly 'Customize' plan enquiry:\n\n"
        f"Name:    {lead.get('name', '')}\n"
        f"Email:   {lead.get('email', '')}\n"
        f"Company: {lead.get('company', '') or '—'}\n\n"
        f"Message:\n{lead.get('message', '') or '—'}\n"
    )
    _send_email(admin_email, "Vaultly — new Customize plan enquiry", body, reply_to=lead.get("email", ""))
