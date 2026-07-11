"""SMTP email delivery for support replies."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional


def send_support_reply(
    *,
    recipient: str,
    original_subject: str,
    original_message: str,
    reply: str,
    admin_name: str,
) -> tuple[str, Optional[str]]:
    """Return (status, error). Status is sent, skipped or failed."""
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        return "skipped", "SMTP_HOST or SMTP_FROM is not configured"

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    email = EmailMessage()
    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = f"Re: {original_subject}"
    email.set_content(
        f"Hello,\n\n{admin_name} replied to your message:\n\n"
        f"{reply}\n\n--- Your original message ---\n{original_message}\n\n"
        "You can also view this reply in your Homework Magic message inbox."
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(email)
        return "sent", None
    except Exception as exc:  # delivery failure must not lose the in-system reply
        return "failed", str(exc)
