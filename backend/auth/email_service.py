"""Password-reset email sending via SMTP (stdlib smtplib -- no new dependency)."""

import logging
import smtplib
from email.mime.text import MIMEText

from utils.config import config

logger = logging.getLogger(__name__)


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
    msg = MIMEText(body)
    msg["Subject"] = "Reset your Vaultly password"
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Password reset email sent to {to_email}")
    except Exception as exc:
        logger.error(f"Failed to send password reset email to {to_email}: {exc}")
