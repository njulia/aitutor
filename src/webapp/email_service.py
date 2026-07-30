"""Small SMTP email helper for support replies.

Email is optional. A reply is always saved to the in-app message box first.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from html import escape
import logging
from typing import Optional, Tuple


logger = logging.getLogger(__name__)

PLAN_DISPLAY_NAMES = {
    "trial_5day": "5-day Homework Magic trial",
    "homework_monthly": "Homework Premium",
    "elevenplus_monthly": "11+ Premium",
    "family_monthly": "Family (Years 1-6)",
    "family_11plus_monthly": "Family (Years 1-6 + 11+)",
}


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def password_reset_email_configuration_issues() -> list[str]:
    """Return password-email configuration problems without exposing secrets."""
    issues: list[str] = []
    host = (os.getenv("SMTP_HOST") or "").strip()
    sender = (os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME") or "").strip()
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""

    if not host:
        issues.append("SMTP_HOST must be configured for password reset email")
    if not sender:
        issues.append("SMTP_FROM must be configured for password reset email")
    if username and not password:
        issues.append("SMTP_PASSWORD must be configured when SMTP_USERNAME is set")
    try:
        port = int(os.getenv("SMTP_PORT") or (465 if _as_bool("SMTP_USE_SSL") else 587))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        issues.append("SMTP_PORT must be a valid TCP port")
    return issues


def password_reset_email_is_configured() -> bool:
    return not password_reset_email_configuration_issues()


def _public_link(path: str) -> str:
    base_url = (os.getenv("PUBLIC_BASE_URL") or os.getenv("APP_BASE_URL") or "").rstrip("/")
    return f"{base_url}{path}" if base_url else path


def _deliver_transactional_email(email: EmailMessage, purpose: str) -> Tuple[str, Optional[str]]:
    """Deliver a transactional email without exposing addresses or SMTP details in logs."""
    host = (os.getenv("SMTP_HOST") or "").strip()
    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    sender = (os.getenv("SMTP_FROM") or username).strip()
    if not host or not sender:
        logger.warning("%s email skipped because SMTP is not configured", purpose)
        return "skipped", "SMTP is not configured."

    try:
        email["From"] = sender
        port = int(os.getenv("SMTP_PORT") or (465 if _as_bool("SMTP_USE_SSL") else 587))
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS") or "15")
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
    except Exception as exc:  # Never expose SMTP credentials or the recipient.
        logger.warning("%s email delivery failed: %s", purpose, type(exc).__name__)
        return "failed", f"Email delivery failed: {type(exc).__name__}"


def send_registration_confirmation_email(*, to_email: str) -> Tuple[str, Optional[str]]:
    """Confirm that a parent or guardian account was created successfully."""
    app_link = _public_link("/app")
    safe_app_link = escape(app_link, quote=True)
    email = EmailMessage()
    email["To"] = to_email
    email["Subject"] = "Welcome to Homework Magic"
    email.set_content(
        "Hello,\n\n"
        "Your Homework Magic parent or guardian account has been created successfully.\n\n"
        f"Start using Homework Magic: {app_link}\n\n"
        "To help protect children’s privacy, use a nickname for each learner and do not enter "
        "a child’s full name, school, home address, phone number or other private details.\n\n"
        "Homework Magic"
    )
    email.add_alternative(
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#263238;line-height:1.55\">"
        "<div style=\"max-width:600px;margin:auto;padding:24px\">"
        "<h1 style=\"color:#6b46c1\">Welcome to Homework Magic</h1>"
        "<p>Your Homework Magic parent or guardian account has been created successfully.</p>"
        f"<p><a href=\"{safe_app_link}\" style=\"background:#6b46c1;color:#fff;padding:12px 18px;"
        "text-decoration:none;border-radius:8px;display:inline-block\">Start using Homework Magic</a></p>"
        "<p style=\"font-size:14px;color:#52606d\"><strong>Privacy reminder:</strong> Use a nickname "
        "for each learner and do not enter a child’s full name, school, home address, phone number "
        "or other private details.</p><p>Homework Magic</p></div></body></html>",
        subtype="html",
    )
    return _deliver_transactional_email(email, "Registration confirmation")


def _format_period_end(value: object) -> Optional[str]:
    if not value:
        return None
    parsed: Optional[datetime]
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def send_subscription_confirmation_email(
    *,
    to_email: str,
    plan: str,
    current_period_end: object = None,
) -> Tuple[str, Optional[str]]:
    """Confirm access after a verified Stripe checkout grants an entitlement."""
    plan_name = PLAN_DISPLAY_NAMES.get(plan, "Homework Magic Premium")
    period_end = _format_period_end(current_period_end)
    app_link = _public_link("/app")
    pricing_link = _public_link("/pricing")
    date_text = f" Your current access period runs until {period_end}." if period_end else ""

    email = EmailMessage()
    email["To"] = to_email
    email["Subject"] = "Your Homework Magic subscription is active"
    email.set_content(
        "Hello,\n\n"
        f"Your {plan_name} access is now active.{date_text}\n\n"
        f"Start practising: {app_link}\n"
        f"View or manage your plan: {pricing_link}\n\n"
        "This confirmation contains no learner details or payment-card information.\n\n"
        "Homework Magic"
    )
    safe_app_link = escape(app_link, quote=True)
    safe_pricing_link = escape(pricing_link, quote=True)
    safe_plan_name = escape(plan_name)
    safe_date_text = escape(date_text)
    email.add_alternative(
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#263238;line-height:1.55\">"
        "<div style=\"max-width:600px;margin:auto;padding:24px\">"
        "<h1 style=\"color:#6b46c1\">Your access is active</h1>"
        f"<p>Your <strong>{safe_plan_name}</strong> access is now active.{safe_date_text}</p>"
        f"<p><a href=\"{safe_app_link}\" style=\"background:#6b46c1;color:#fff;padding:12px 18px;"
        "text-decoration:none;border-radius:8px;display:inline-block\">Start practising</a></p>"
        f"<p><a href=\"{safe_pricing_link}\">View or manage your plan</a></p>"
        "<p style=\"font-size:14px;color:#52606d\">This confirmation contains no learner details "
        "or payment-card information.</p><p>Homework Magic</p></div></body></html>",
        subtype="html",
    )
    return _deliver_transactional_email(email, "Subscription confirmation")


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


def send_xp_digest_email(
    *,
    to_email: str,
    digest: dict,
) -> Tuple[str, Optional[str]]:
    """发送每日 XP 收益摘要邮件给家长。"""
    kids = digest.get("kids", [])
    if not kids:
        return "skipped", "No XP activity in the digest period."

    # 构建纯文本内容
    lines = ["Hello,\n\nHere is your family's learning summary from the past 24 hours:\n"]
    for kid in kids:
        name = kid.get("name", "Your child")
        xp = kid.get("total_xp", 0)
        events = kid.get("event_count", 0)
        lines.append(f"  - {name}: earned {xp} XP from {events} activities")
    lines.append("\nKeep encouraging your children to learn every day!")
    lines.append("\nView the full dashboard: " + _public_link("/parent-dashboard"))
    lines.append("\nHomework Magic")

    email = EmailMessage()
    email["To"] = to_email
    email["Subject"] = "Your family's learning summary from Homework Magic"
    email.set_content("\n".join(lines))

    # 构建 HTML 内容
    kid_rows = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb'>"
        f"{escape(kid.get('name', 'Your child'))}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right'>"
        f"<strong>{kid.get('total_xp', 0)}</strong> XP</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right'>"
        f"{kid.get('event_count', 0)} activities</td></tr>"
        for kid in kids
    )
    dashboard_link = _public_link("/parent-dashboard")
    safe_dashboard_link = escape(dashboard_link, quote=True)

    html_content = (
        "<!doctype html><html><body style='font-family:Arial,sans-serif;color:#263238;line-height:1.55'>"
        "<div style='max-width:600px;margin:auto;padding:24px'>"
        "<h1 style='color:#6b46c1'>Your family's learning summary</h1>"
        "<p>Here is what your children achieved in the past 24 hours:</p>"
        f"<table style='width:100%;border-collapse:collapse;margin:16px 0'>"
        f"<thead><tr style='background:#f3f4f6'>"
        "<th style='padding:8px 12px;text-align:left'>Child</th>"
        "<th style='padding:8px 12px;text-align:right'>XP earned</th>"
        "<th style='padding:8px 12px;text-align:right'>Activities</th>"
        "</tr></thead><tbody>{kid_rows}</tbody></table>"
        "<p>Keep encouraging your children to learn every day!</p>"
        f"<p><a href='{safe_dashboard_link}' style='background:#6b46c1;color:#fff;padding:12px 18px;"
        "text-decoration:none;border-radius:8px;display:inline-block'>View full dashboard</a></p>"
        "<p>Homework Magic</p></div></body></html>"
    )
    email.add_alternative(html_content, subtype="html")

    return _deliver_transactional_email(email, "XP digest")
