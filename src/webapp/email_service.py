"""Small SMTP email helper for support replies.

Email is optional. A reply is always saved to the in-app message box first.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Tuple


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def send_support_reply(
    *,
    to_email: Optional[str],
    subject: str,
    reply: str,
    message_id: str,
) -> Tuple[str, Optional[str]]:
    """Send a support reply and return ``(status, error)``.

    Status is one of ``sent``, ``skipped`` or ``failed``. Raw message content is
    deliberately not copied into the email.
    """
    if not to_email:
        return "skipped", "No parent or guardian email is available."

    host = (os.getenv("SMTP_HOST") or "").strip()
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    sender = (os.getenv("SMTP_FROM") or username).strip()
    if not host or not sender:
        return "skipped", "SMTP is not configured. The reply is still in the message box."

    port = int(os.getenv("SMTP_PORT") or (465 if _as_bool("SMTP_USE_SSL") else 587))
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")
    message_link = f"{public_base_url}/messages" if public_base_url else "/messages"

    email = EmailMessage()
    email["From"] = sender
    email["To"] = to_email
    email["Subject"] = f"Homework Magic support reply: {subject[:120]}"
    email.set_content(
        "Hello,\n\n"
        "A member of the Homework Magic support team replied to your message:\n\n"
        f"{reply.strip()}\n\n"
        f"You can also read this reply in your message box: {message_link}\n"
        f"Reference: {message_id}\n\n"
        "For privacy, please do not reply with a child's full name, school, address, "
        "phone number or other private details.\n\n"
        "Homework Magic Support"
    )

    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS") or "15")
    try:
        if _as_bool("SMTP_USE_SSL"):
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(email)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                smtp.ehlo()
                if _as_bool("SMTP_USE_TLS", True):
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)
                smtp.send_message(email)
        return "sent", None
    except Exception as exc:  # Do not expose SMTP credentials or server details.
        return "failed", f"Email delivery failed: {type(exc).__name__}"


def send_password_reset_email(*, to_email: str, reset_url: str, expires_minutes: int) -> Tuple[str, Optional[str]]:
    """Send a password reset link without exposing whether an account exists."""
    host = (os.getenv("SMTP_HOST") or "").strip()
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    sender = (os.getenv("SMTP_FROM") or username).strip()
    if not host or not sender:
        return "skipped", "SMTP is not configured."

    port = int(os.getenv("SMTP_PORT") or (465 if _as_bool("SMTP_USE_SSL") else 587))
    email = EmailMessage()
    email["From"] = sender
    email["To"] = to_email
    email["Subject"] = "Reset your Homework Magic password"
    email.set_content(
        "Hello,\n\n"
        "A password reset was requested for your Homework Magic parent or guardian account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {expires_minutes} minutes and can be used once.\n"
        "If you did not request this, you can safely ignore this email. Your password has not changed.\n\n"
        "Homework Magic Support"
    )

    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS") or "15")
    try:
        if _as_bool("SMTP_USE_SSL"):
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(email)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                smtp.ehlo()
                if _as_bool("SMTP_USE_TLS", True):
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)
                smtp.send_message(email)
        return "sent", None
    except Exception as exc:
        return "failed", f"Email delivery failed: {type(exc).__name__}"
