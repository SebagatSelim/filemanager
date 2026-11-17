"""Sends the verification-code emails.

If SMTP_HOST is not set (DEMO MODE), nothing is emailed: the code is printed in the backend
window instead and the API also returns it, so the app can be demonstrated without an email account.
"""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

from ..errors import APIError

log = logging.getLogger(__name__)

SUBJECTS = {
    "register": "Your FileAI verification code",
    "login": "Your FileAI sign-in code",
}
REASONS = {
    "register": "Use this code to confirm your email address and finish creating your FileAI account.",
    "login": "Use this code to finish signing in to FileAI. If this wasn't you, change your password.",
}


def email_configured() -> bool:
    return bool(current_app.config["SMTP_HOST"])


def send_code(email: str, name: str, code: str, purpose: str) -> bool:
    """Email the code. Returns True if it was emailed, False in demo mode (code printed in the log)."""
    cfg = current_app.config
    if not email_configured():
        log.warning("DEMO MODE (no SMTP_HOST set) - %s code for %s: %s", purpose, email, code)
        return False

    message = EmailMessage()
    message["Subject"] = SUBJECTS[purpose]
    message["From"] = cfg["MAIL_FROM"]
    message["To"] = email
    message.set_content(
        f"Hi {name or 'there'},\n\n{REASONS[purpose]}\n\n"
        f"    {code}\n\n"
        f"The code expires in {cfg['OTP_EXPIRES_MIN']} minutes.\n\n— FileAI"
    )
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=20) as smtp:
            if cfg["SMTP_USE_TLS"]:
                smtp.starttls()
            if cfg["SMTP_USERNAME"]:
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send the %s code email to %s", purpose, email)
        raise APIError(502, "EMAIL_FAILED", "We couldn't send the verification email. Please try again later.")
    return True
