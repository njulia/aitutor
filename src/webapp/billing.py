"""Stripe Checkout, customer portal and verified webhook billing.

Entitlements are updated only from signed Stripe webhooks. Learner records are
never sent to Stripe; billing uses the authenticated parent/guardian account.
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, MetaData, String, Table, insert, update
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url
from .account_store import (
    BETA_PLAN,
    account_has_used_plan,
    beta_access_enabled,
    ensure_account,
    get_account,
    get_account_by_stripe_customer_id,
    get_active_subscription,
    get_subscription_by_stripe_id,
    redeem_beta_access,
    set_stripe_customer,
    upsert_stripe_subscription,
)
from .email_service import send_subscription_confirmation_email
from .privacy_metrics import record_marketing_event
from .runtime import run_blocking


logger = logging.getLogger(__name__)
DEFAULT_STRIPE_PRICING_TABLE_ID = "prctbl_1TvlP9A7C4P8kXJMSS8t4VRT"
DEFAULT_STRIPE_PUBLISHABLE_KEY = "pk_live_fYeIDSqsqYC6MDKau5eFsI0U"
TRIAL_PLAN = "trial_5day"
TRIAL_DURATION_DAYS = 5
PLAN_ENV_VARS = {
    TRIAL_PLAN: "STRIPE_PRICE_TRIAL_5DAY",
    "homework_monthly": "STRIPE_PRICE_HOMEWORK_MONTHLY",
    "elevenplus_monthly": "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
    "family_monthly": "STRIPE_PRICE_FAMILY_MONTHLY",
}
REQUIRED_PUBLIC_PLANS = (TRIAL_PLAN, "homework_monthly", "elevenplus_monthly")
PLAN_EXPECTATIONS = {
    TRIAL_PLAN: {"currency": "gbp", "unit_amount": 99, "interval": None},
    "homework_monthly": {"currency": "gbp", "unit_amount": 499, "interval": "month"},
    "elevenplus_monthly": {"currency": "gbp", "unit_amount": 999, "interval": "month"},
}
_validated_prices: set[tuple[str, bool]] = set()
_price_validation_lock = threading.Lock()
_cancellation_portal_configuration_id: Optional[str] = None
_cancellation_portal_lock = threading.Lock()


class CheckoutRequest(BaseModel):
    plan: str


class BetaAccessRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=128)


def _env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _object_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _expected_livemode() -> bool:
    configured = os.getenv("STRIPE_EXPECTED_LIVEMODE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("STRIPE_SECRET_KEY", "").startswith(("sk_live_", "rk_live_"))


def _billing_enabled() -> bool:
    configured = os.getenv("STRIPE_BILLING_ENABLED")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    # Preserve existing deployments: supplying a Stripe key enables billing
    # unless the operator explicitly switches it off.
    return bool(os.getenv("STRIPE_SECRET_KEY", "").strip())


def _stripe():
    try:
        import stripe
    except ImportError as exc:
        raise RuntimeError("Stripe SDK is not installed") from exc
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = key
    return stripe


def _plans() -> Dict[str, str]:
    candidates = {name: os.getenv(env_name, "") for name, env_name in PLAN_ENV_VARS.items()}
    return {name: price for name, price in candidates.items() if price}


def _pricing_table_id() -> str:
    return os.getenv(
        "STRIPE_PRICING_TABLE_ID",
        DEFAULT_STRIPE_PRICING_TABLE_ID,
    ).strip()


def _publishable_key() -> str:
    return os.getenv(
        "STRIPE_PUBLISHABLE_KEY",
        DEFAULT_STRIPE_PUBLISHABLE_KEY,
    ).strip()


def billing_configuration_issues(plan: Optional[str] = None) -> list[str]:
    """Return checkout blockers without ever exposing credential values."""
    if not _billing_enabled():
        return ["Stripe billing is disabled"]

    issues: list[str] = []
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    expected_live = _expected_livemode()
    if not key:
        issues.append("STRIPE_SECRET_KEY is not configured")
    elif expected_live and not key.startswith(("sk_live_", "rk_live_")):
        issues.append("STRIPE_SECRET_KEY must be a live key")
    elif not expected_live and not key.startswith(("sk_test_", "rk_test_")):
        issues.append("STRIPE_SECRET_KEY must be a test key for this deployment")

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret.startswith("whsec_"):
        issues.append("STRIPE_WEBHOOK_SECRET is not configured")

    requested_plans = (plan,) if plan else REQUIRED_PUBLIC_PLANS
    plans = _plans()
    for plan_name in requested_plans:
        env_name = PLAN_ENV_VARS.get(plan_name)
        if not env_name:
            issues.append(f"Unknown plan: {plan_name}")
            continue
        if not plans.get(plan_name, "").startswith("price_"):
            issues.append(f"{env_name} is not configured")

    configured_prices = [plans[name] for name in REQUIRED_PUBLIC_PLANS if name in plans]
    if len(configured_prices) != len(set(configured_prices)):
        issues.append("Each public plan must use a different Stripe Price ID")

    try:
        _base_url()
    except RuntimeError as exc:
        issues.append(str(exc))
    return issues


def portal_configuration_issues() -> list[str]:
    """Return only the settings needed to open Stripe's customer portal.

    Subscription cancellation must remain available even if a checkout Price
    or the webhook endpoint is temporarily misconfigured.  The portal needs
    only an enabled, mode-correct secret key and the canonical return URL.
    """
    if not _billing_enabled():
        return ["Stripe billing is disabled"]

    issues: list[str] = []
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    expected_live = _expected_livemode()
    if not key:
        issues.append("STRIPE_SECRET_KEY is not configured")
    elif expected_live and not key.startswith(("sk_live_", "rk_live_")):
        issues.append("STRIPE_SECRET_KEY must be a live key")
    elif not expected_live and not key.startswith(("sk_test_", "rk_test_")):
        issues.append("STRIPE_SECRET_KEY must be a test key for this deployment")
    try:
        _base_url()
    except RuntimeError as exc:
        issues.append(str(exc))
    return issues


def pricing_table_configuration_issues() -> list[str]:
    """Return blockers for the authenticated Stripe Pricing Table."""
    issues: list[str] = []
    for plan in ("homework_monthly", "elevenplus_monthly"):
        for issue in billing_configuration_issues(plan):
            if issue not in issues:
                issues.append(issue)
    monthly_prices = [
        _plans().get("homework_monthly"),
        _plans().get("elevenplus_monthly"),
    ]
    if all(monthly_prices) and len(set(monthly_prices)) != len(monthly_prices):
        issues.append("The monthly plans must use different Stripe Price IDs")
    pricing_table_id = _pricing_table_id()
    publishable_key = _publishable_key()
    expected_prefix = "pk_live_" if _expected_livemode() else "pk_test_"

    if not pricing_table_id.startswith("prctbl_"):
        issues.append("STRIPE_PRICING_TABLE_ID is not configured")
    if not publishable_key.startswith(expected_prefix):
        issues.append(
            "STRIPE_PUBLISHABLE_KEY does not match the configured Stripe mode"
        )
    return issues


def public_billing_status() -> Dict[str, Any]:
    plans = _plans()
    availability = {
        plan: not billing_configuration_issues(plan)
        for plan in REQUIRED_PUBLIC_PLANS
    }
    return {
        "enabled": _billing_enabled(),
        "live_mode": _expected_livemode(),
        "plans": [plan for plan in REQUIRED_PUBLIC_PLANS if plan in plans],
        "plan_availability": availability,
        "checkout_ready": all(availability.values()),
    }


def _base_url() -> str:
    value = os.getenv("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("APP_BASE_URL must be an absolute HTTP(S) URL")
    if os.getenv("DEV_MODE", "").lower() not in {"1", "true", "yes"} and parsed.scheme != "https":
        raise RuntimeError("APP_BASE_URL must use HTTPS in production")
    return value


def _configured_plan_for_price(price_id: Optional[str], declared_plan: Optional[str] = None) -> str:
    """Resolve an entitlement from its Price ID, rejecting metadata conflicts."""
    clean_price_id = str(price_id or "").strip()
    matches = [name for name, configured_id in _plans().items() if configured_id == clean_price_id]
    if len(matches) != 1:
        raise ValueError("Stripe subscription uses an unknown or ambiguous Price ID")
    resolved = matches[0]
    if declared_plan and declared_plan != resolved:
        raise ValueError("Stripe subscription plan metadata does not match its Price ID")
    return resolved


def _validate_stripe_price(stripe: Any, plan: str, price_id: str) -> None:
    """Check a Price once per process before allowing it into Checkout."""
    if _env_true("TESTING", False):
        return
    cache_key = (price_id, _expected_livemode())
    if cache_key in _validated_prices:
        return
    with _price_validation_lock:
        if cache_key in _validated_prices:
            return
        price = stripe.Price.retrieve(price_id)
        if not bool(_object_value(price, "active", False)):
            raise RuntimeError(f"Stripe Price for {plan} is inactive")
        if bool(_object_value(price, "livemode", False)) != _expected_livemode():
            raise RuntimeError(f"Stripe Price for {plan} is in the wrong mode")
        expected = PLAN_EXPECTATIONS.get(plan)
        if expected:
            recurring = _object_value(price, "recurring")
            interval = _object_value(recurring, "interval") if recurring else None
            if str(_object_value(price, "currency", "")).lower() != expected["currency"]:
                raise RuntimeError(f"Stripe Price for {plan} must use GBP")
            if _object_value(price, "unit_amount") != expected["unit_amount"]:
                raise RuntimeError(f"Stripe Price for {plan} does not match the advertised amount")
            if interval != expected["interval"]:
                raise RuntimeError(f"Stripe Price for {plan} has the wrong billing interval")
        _validated_prices.add(cache_key)


def create_checkout(account: Dict[str, Any], plan: str) -> Dict[str, str]:
    if plan not in PLAN_ENV_VARS:
        raise ValueError("Unknown or unavailable subscription plan")
    issues = billing_configuration_issues(plan)
    if issues:
        raise RuntimeError("; ".join(issues))
    plans = _plans()
    if plan not in plans:
        raise ValueError("Unknown or unavailable subscription plan")
    active_subscription = get_active_subscription(account["id"])
    if active_subscription and (
        active_subscription.get("plan") != BETA_PLAN or plan == TRIAL_PLAN
    ):
        raise ValueError("This account already has active access")
    is_trial = plan == TRIAL_PLAN
    if is_trial and account_has_used_plan(account["id"], TRIAL_PLAN):
        raise ValueError("The five-day trial has already been used on this account")
    stripe = _stripe()
    _validate_stripe_price(stripe, plan, plans[plan])
    base = _base_url()
    customer_id = account.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=account["email"],
            name=account.get("display_name") or None,
            metadata={"account_id": account["id"]},
            idempotency_key=f"customer-{account['id']}",
        )
        customer_id = customer.id
        set_stripe_customer(account["id"], customer_id)
    attempt = secrets.token_urlsafe(12)
    checkout_args: Dict[str, Any] = dict(
        mode="payment" if is_trial else "subscription",
        submit_type="pay" if is_trial else "subscribe",
        customer=customer_id,
        line_items=[{"price": plans[plan], "quantity": 1}],
        success_url=f"{base}/pricing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/pricing?checkout=cancelled",
        client_reference_id=account["id"],
        metadata={"account_id": account["id"], "plan": plan},
        custom_text={
            "submit": {
                "message": (
                    "This is a one-off five-day purchase and does not renew. "
                    if is_trial
                    else "This subscription renews monthly until cancelled. "
                )
                + "By paying, you agree to the Terms and Refund Policy at "
                + f"{base}/terms and {base}/refund-policy."
            }
        },
        consent_collection={"terms_of_service": "required"},
        allow_promotion_codes=not is_trial,
        idempotency_key=(
            f"checkout-{account['id']}-{plan}"
            if is_trial
            else f"checkout-{account['id']}-{plan}-{attempt}"
        ),
    )
    if is_trial:
        checkout_args["payment_intent_data"] = {
            "metadata": {"account_id": account["id"], "plan": plan}
        }
    else:
        checkout_args["subscription_data"] = {
            "metadata": {"account_id": account["id"], "plan": plan}
        }
    session = stripe.checkout.Session.create(**checkout_args)
    return {"checkout_url": session.url, "checkout_session_id": session.id}


def create_pricing_table_session(account: Dict[str, Any]) -> Dict[str, str]:
    """Create a short-lived Customer Session for Stripe's embedded table."""
    issues = pricing_table_configuration_issues()
    if issues:
        raise RuntimeError("; ".join(issues))
    active_subscription = get_active_subscription(account["id"])
    if active_subscription and active_subscription.get("plan") != BETA_PLAN:
        raise ValueError(
            "This account already has an active subscription. "
            "Manage it in the billing portal."
        )

    stripe = _stripe()
    customer_id = account.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=account["email"],
            name=account.get("display_name") or None,
            metadata={"account_id": account["id"]},
            idempotency_key=f"customer-{account['id']}",
        )
        customer_id = str(_object_value(customer, "id", ""))
        if not customer_id.startswith("cus_"):
            raise RuntimeError("Stripe did not return a valid Customer ID")
        set_stripe_customer(account["id"], customer_id)

    customer_session = stripe.CustomerSession.create(
        customer=customer_id,
        components={"pricing_table": {"enabled": True}},
    )
    client_secret = str(_object_value(customer_session, "client_secret", ""))
    if not client_secret:
        raise RuntimeError("Stripe did not return a Customer Session secret")
    return {
        "client_secret": client_secret,
        "client_reference_id": account["id"],
        "pricing_table_id": _pricing_table_id(),
        "publishable_key": _publishable_key(),
    }


def refresh_stripe_subscriptions(account: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reconcile this parent's known Stripe customer with the local cache.

    Normal learning requests continue to use the fast local entitlement
    lookup.  The pricing page may explicitly request this bounded repair so a
    missed or delayed webhook cannot make an existing subscriber look signed
    out or hide subscription management.
    """
    customer_id = str(account.get("stripe_customer_id") or "")
    if not customer_id.startswith("cus_"):
        return get_active_subscription(account["id"])
    if not _billing_enabled():
        return get_active_subscription(account["id"])

    stripe = _stripe()
    response = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=10,
    )
    for stripe_subscription in _object_value(response, "data", []) or []:
        try:
            subscription_id = str(
                _object_value(stripe_subscription, "id") or ""
            )
            previous = (
                get_subscription_by_stripe_id(subscription_id)
                if subscription_id
                else None
            )
            saved = sync_subscription(
                stripe_subscription,
                fallback_account_id=account["id"],
            )
            _record_subscription_transition(previous, saved)
        except ValueError:
            # A Stripe customer can contain an old or unrelated product. Only
            # configured Homework Magic Price IDs may grant local access.
            logger.warning(
                "Skipped an unrecognised subscription while refreshing billing status"
            )
    return get_active_subscription(account["id"])


def refresh_stripe_subscription_catalog(limit: int = 100) -> Dict[str, Any]:
    """Reconcile a bounded Stripe subscription page for the admin dashboard.

    The signed webhook remains the normal update path. This repair pass lets an
    administrator recover a delayed or missed webhook without making ordinary
    learner requests wait for Stripe.
    """
    bounded_limit = max(1, min(int(limit), 100))
    if not _billing_enabled():
        return {
            "attempted": False,
            "succeeded": True,
            "received": 0,
            "synced": 0,
            "skipped": 0,
            "has_more": False,
        }

    stripe = _stripe()
    response = stripe.Subscription.list(
        status="all",
        limit=bounded_limit,
    )
    stripe_subscriptions = list(
        _object_value(response, "data", []) or []
    )[:bounded_limit]
    synced = 0
    skipped = 0
    for stripe_subscription in stripe_subscriptions:
        try:
            subscription_id = str(
                _object_value(stripe_subscription, "id") or ""
            )
            previous = (
                get_subscription_by_stripe_id(subscription_id)
                if subscription_id
                else None
            )
            saved = sync_subscription(stripe_subscription)
            _record_subscription_transition(previous, saved)
            synced += 1
        except ValueError:
            # Ignore unrelated Stripe products or records that cannot be linked
            # to an authenticated Homework Magic parent account.
            skipped += 1
            logger.warning(
                "Skipped an unrecognised or unlinked Stripe subscription "
                "during the admin refresh"
            )
    return {
        "attempted": True,
        "succeeded": True,
        "received": len(stripe_subscriptions),
        "synced": synced,
        "skipped": skipped,
        "has_more": bool(_object_value(response, "has_more", False)),
    }


def _cancellation_portal_configuration(stripe: Any) -> str:
    """Return an app-owned Stripe Portal configuration with cancellation on."""
    global _cancellation_portal_configuration_id

    configured = os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "").strip()
    if configured:
        if not configured.startswith("bpc_"):
            raise RuntimeError("STRIPE_PORTAL_CONFIGURATION_ID is invalid")
        return configured
    if _cancellation_portal_configuration_id:
        return _cancellation_portal_configuration_id

    with _cancellation_portal_lock:
        if _cancellation_portal_configuration_id:
            return _cancellation_portal_configuration_id
        configurations = stripe.billing_portal.Configuration.list(limit=100)
        for existing in _object_value(configurations, "data", []) or []:
            metadata = _object_value(existing, "metadata", {}) or {}
            existing_id = str(_object_value(existing, "id") or "")
            if (
                bool(_object_value(existing, "active", False))
                and metadata.get("service") == "homework_magic"
                and metadata.get("schema") == "cancellation_v1"
                and existing_id.startswith("bpc_")
            ):
                _cancellation_portal_configuration_id = existing_id
                return existing_id

        base_url = _base_url()
        created = stripe.billing_portal.Configuration.create(
            name="Homework Magic cancellation",
            default_return_url=f"{base_url}/pricing",
            business_profile={
                "headline": "Manage your Homework Magic subscription securely",
                "privacy_policy_url": f"{base_url}/privacy",
                "terms_of_service_url": f"{base_url}/terms",
            },
            features={
                "customer_update": {
                    "enabled": False,
                    "allowed_updates": [],
                },
                "invoice_history": {"enabled": True},
                "payment_method_update": {"enabled": True},
                "subscription_cancel": {
                    "enabled": True,
                    "mode": "at_period_end",
                    "proration_behavior": "none",
                    "cancellation_reason": {
                        "enabled": True,
                        "options": [
                            "too_expensive",
                            "missing_features",
                            "switched_service",
                            "unused",
                            "other",
                        ],
                    },
                },
                "subscription_update": {"enabled": False},
            },
            metadata={
                "service": "homework_magic",
                "schema": "cancellation_v1",
            },
            idempotency_key="homework-magic-cancellation-portal-v1",
        )
        created_id = str(_object_value(created, "id") or "")
        if not created_id.startswith("bpc_"):
            raise RuntimeError(
                "Stripe did not return a valid portal configuration"
            )
        _cancellation_portal_configuration_id = created_id
        return created_id


def create_portal(
    account: Dict[str, Any],
    action: str = "manage",
) -> Dict[str, str]:
    if action not in {"manage", "change", "cancel"}:
        raise ValueError("Unknown billing action")
    issues = portal_configuration_issues()
    if issues:
        raise RuntimeError("; ".join(issues))
    customer_id = account.get("stripe_customer_id")
    if not customer_id:
        raise ValueError("No Stripe customer exists for this account")

    stripe = _stripe()
    base_url = _base_url()
    portal_args: Dict[str, Any] = {
        "customer": customer_id,
        "return_url": f"{base_url}/pricing?billing=returned",
    }
    if action in {"change", "cancel"}:
        subscription = get_active_subscription(account["id"])
        if not subscription:
            subscription = refresh_stripe_subscriptions(account)
        subscription_id = str(
            (subscription or {}).get("stripe_subscription_id") or ""
        )
        if not subscription_id.startswith("sub_"):
            raise ValueError(
                "No active monthly subscription is available to change or cancel"
            )
        flow_type = (
            "subscription_update"
            if action == "change"
            else "subscription_cancel"
        )
        completion = "changed" if action == "change" else "cancelled"
        portal_args["flow_data"] = {
            "type": flow_type,
            flow_type: {"subscription": subscription_id},
            "after_completion": {
                "type": "redirect",
                "redirect": {
                    "return_url": (
                        f"{base_url}/pricing?billing={completion}"
                    )
                },
            },
        }
        if action == "cancel":
            portal_args["configuration"] = (
                _cancellation_portal_configuration(stripe)
            )

    portal = stripe.billing_portal.Session.create(**portal_args)
    portal_url = str(_object_value(portal, "url") or "")
    parsed_portal = urlparse(portal_url)
    if (
        parsed_portal.scheme != "https"
        or parsed_portal.hostname != "billing.stripe.com"
    ):
        raise RuntimeError("Stripe did not return a secure billing portal URL")
    return {"portal_url": portal_url}


def _timestamp(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def sync_subscription(subscription: Any, fallback_account_id: Optional[str] = None) -> Dict[str, Any]:
    metadata = _object_value(subscription, "metadata", {}) or {}
    metadata_account_id = metadata.get("account_id")
    if (
        fallback_account_id
        and metadata_account_id
        and str(metadata_account_id) != str(fallback_account_id)
    ):
        raise ValueError("Stripe subscription account reference does not match")
    account_id = metadata_account_id or fallback_account_id
    customer_id = _object_value(subscription, "customer")
    customer_account = (
        get_account_by_stripe_customer_id(str(customer_id))
        if customer_id
        else None
    )
    if (
        customer_account
        and account_id
        and str(customer_account["id"]) != str(account_id)
    ):
        raise ValueError("Stripe customer does not match the parent account")
    if not account_id and customer_account:
        account_id = customer_account["id"]
    if not account_id:
        raise ValueError("Stripe subscription is not linked to an account")
    items = _object_value(_object_value(subscription, "items", {}), "data", []) or []
    price_id = None
    if items:
        price = _object_value(items[0], "price", {})
        price_id = _object_value(price, "id")
    plan = _configured_plan_for_price(price_id, metadata.get("plan"))
    period_end = _object_value(subscription, "current_period_end")
    if not period_end and items:
        period_end = max(
            (int(_object_value(item, "current_period_end", 0) or 0) for item in items),
            default=0,
        ) or None
    status = str(_object_value(subscription, "status", "incomplete"))
    parsed_period_end = _timestamp(period_end)
    if status.lower() in {"active", "trialing"} and parsed_period_end is None:
        raise ValueError("Active Stripe subscription has no current period end")
    scheduled_cancellation = bool(
        _object_value(subscription, "cancel_at_period_end", False)
        or _object_value(subscription, "cancel_at")
    )
    return upsert_stripe_subscription(
        account_id=account_id,
        plan=plan,
        status=status,
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(_object_value(subscription, "id")),
        price_id=str(price_id) if price_id else None,
        current_period_end=parsed_period_end,
        cancel_at_period_end=scheduled_cancellation,
    )


def sync_trial_checkout(session: Any) -> Dict[str, Any]:
    """Grant the paid one-off trial for five days after a verified webhook."""
    metadata = _object_value(session, "metadata", {}) or {}
    account_id = metadata.get("account_id") or _object_value(session, "client_reference_id")
    if not account_id:
        raise ValueError("Trial checkout is not linked to an account")
    if metadata.get("plan") != TRIAL_PLAN:
        raise ValueError("Checkout is not a recognised trial")
    if str(_object_value(session, "payment_status", "")).lower() != "paid":
        raise ValueError("Trial checkout has not been paid")

    session_id = str(_object_value(session, "id") or "")
    if not session_id:
        raise ValueError("Trial checkout has no session ID")
    now = datetime.now(UTC)
    customer_id = _object_value(session, "customer")
    return upsert_stripe_subscription(
        account_id=str(account_id),
        plan=TRIAL_PLAN,
        status="active",
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=f"trial_{session_id}",
        price_id=_plans().get(TRIAL_PLAN),
        current_period_end=now + timedelta(days=TRIAL_DURATION_DAYS),
        cancel_at_period_end=True,
    )


class WebhookLedger:
    def __init__(self) -> None:
        url = normalise_database_url(os.getenv("BILLING_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite+pysqlite:///data/billing.db")
        self.engine = get_engine(url)
        self.metadata = MetaData()
        self.events = Table(
            "stripe_webhook_events", self.metadata,
            Column("event_id", String(100), primary_key=True),
            Column("event_type", String(100), nullable=False),
            Column("received_at", DateTime(timezone=True), nullable=False),
            Column("processed_at", DateTime(timezone=True), nullable=True),
            Column("status", String(30), nullable=False),
        )
        self.metadata.create_all(self.engine)

    def begin(self, event_id: str, event_type: str) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(self.events).values(
                    event_id=event_id, event_type=event_type,
                    received_at=datetime.now(UTC), processed_at=None, status="processing",
                ))
            return True
        except IntegrityError:
            return False

    def finish(self, event_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(self.events).where(self.events.c.event_id == event_id).values(
                processed_at=datetime.now(UTC), status=status[:30]
            ))


_ledger: Optional[WebhookLedger] = None


def ledger() -> WebhookLedger:
    global _ledger
    if _ledger is None:
        _ledger = WebhookLedger()
    return _ledger


def _queue_subscription_confirmation(
    subscription: Dict[str, Any],
    notifications: Optional[list[Dict[str, Any]]],
) -> None:
    """Prepare an email only when checkout has granted usable access."""
    if notifications is None or subscription.get("status") not in {"active", "trialing"}:
        return
    account = get_account(str(subscription.get("account_id") or ""))
    if not account or not account.get("email"):
        logger.warning("Subscription confirmation skipped because its account email is unavailable")
        return
    notifications.append({
        "to_email": account["email"],
        "plan": subscription.get("plan") or "premium",
        "current_period_end": subscription.get("current_period_end"),
    })


def _record_subscription_transition(
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
) -> None:
    """Increment coarse counters once per local entitlement transition."""
    plan = str(current.get("plan") or "")
    previous_status = str((previous or {}).get("status") or "")
    current_status = str(current.get("status") or "")
    previous_active = previous_status in {"active", "trialing"}
    current_active = current_status in {"active", "trialing"}
    if plan == TRIAL_PLAN and current_active and not previous_active:
        record_marketing_event(
            "five_day_pass_purchased",
            source="unknown",
            page="pricing",
        )
    elif (
        plan.endswith("_monthly")
        and current_active
        and not previous_active
    ):
        record_marketing_event(
            "monthly_subscription_started",
            source="unknown",
            page="pricing",
        )

    was_cancelling = bool(
        (previous or {}).get("cancel_at_period_end")
        or previous_status in {"cancelled", "canceled", "expired"}
    )
    is_cancelling = bool(
        current.get("cancel_at_period_end")
        or current_status in {"cancelled", "canceled", "expired"}
    )
    if plan.endswith("_monthly") and is_cancelling and not was_cancelling:
        record_marketing_event(
            "subscription_cancelled",
            source="unknown",
            page="pricing",
        )


def process_webhook(
    payload: bytes,
    signature: str,
    notifications: Optional[list[Dict[str, Any]]] = None,
) -> str:
    stripe = _stripe()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
    event = stripe.Webhook.construct_event(payload, signature, secret)
    expected_live = _expected_livemode()
    event_live = bool(_object_value(event, "livemode", False))
    if event_live != expected_live:
        raise ValueError("Stripe webhook mode does not match this deployment")
    event_id = str(_object_value(event, "id"))
    event_type = str(_object_value(event, "type"))
    if not ledger().begin(event_id, event_type):
        return "duplicate"
    try:
        obj = _object_value(_object_value(event, "data", {}), "object")
        if event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "customer.subscription.paused",
            "customer.subscription.resumed",
        }:
            subscription_id = str(_object_value(obj, "id") or "")
            previous = (
                get_subscription_by_stripe_id(subscription_id)
                if subscription_id
                else None
            )
            saved_subscription = sync_subscription(obj)
            _record_subscription_transition(previous, saved_subscription)
        elif event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            metadata = _object_value(obj, "metadata", {}) or {}
            if metadata.get("plan") == TRIAL_PLAN:
                # Card payments are normally paid at completion; delayed methods
                # are granted only by async_payment_succeeded.
                if str(_object_value(obj, "payment_status", "")).lower() == "paid":
                    trial_record_id = f"trial_{str(_object_value(obj, 'id') or '')}"
                    previous = get_subscription_by_stripe_id(trial_record_id)
                    saved_subscription = sync_trial_checkout(obj)
                    _record_subscription_transition(previous, saved_subscription)
                    _queue_subscription_confirmation(saved_subscription, notifications)
                ledger().finish(event_id, "processed")
                return "processed"
            subscription_id = _object_value(obj, "subscription")
            account_id = _object_value(obj, "client_reference_id")
            if subscription_id:
                previous = get_subscription_by_stripe_id(str(subscription_id))
                subscription = stripe.Subscription.retrieve(subscription_id)
                saved_subscription = sync_subscription(subscription, fallback_account_id=account_id)
                _record_subscription_transition(previous, saved_subscription)
                _queue_subscription_confirmation(saved_subscription, notifications)
        ledger().finish(event_id, "processed")
        return "processed"
    except Exception:
        ledger().finish(event_id, "failed")
        raise


def build_billing_router(resolve_username):
    router = APIRouter(prefix="/api/billing", tags=["billing"])

    async def current_account(request: Request):
        username = resolve_username(request)
        if not username:
            raise HTTPException(status_code=401, detail="A parent or guardian must sign in.")
        return await run_blocking(ensure_account, username, limit_concurrency=False)

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
        signature = request.headers.get("Stripe-Signature", "")
        payload = await request.body()
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        try:
            notifications: list[Dict[str, Any]] = []
            status = await run_blocking(
                process_webhook,
                payload,
                signature,
                notifications,
                limit_concurrency=False,
            )
        except Exception as exc:
            # Signature and processing failures must return non-2xx so Stripe retries.
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
        for notification in notifications:
            background_tasks.add_task(send_subscription_confirmation_email, **notification)
        return {"received": True, "status": status}

    @router.get("/plans")
    async def plans():
        return {"success": True, **public_billing_status()}

    @router.get("/status")
    async def status(request: Request, refresh: bool = False):
        """Return the signed-in parent's subscription and management state.

        ``refresh=true`` is reserved for the parent billing page. It reconciles
        the linked Stripe customer before responding, while ordinary learning
        requests continue to use the low-latency local entitlement cache.
        """
        account = await current_account(request)
        subscription = await run_blocking(
            get_active_subscription,
            account["id"],
            limit_concurrency=False,
        )
        refresh_failed = False
        if refresh and account.get("stripe_customer_id"):
            try:
                subscription = await run_blocking(
                    refresh_stripe_subscriptions,
                    account,
                    timeout=12,
                    limit_concurrency=False,
                )
            except Exception:
                refresh_failed = True
                logger.exception(
                    "Could not refresh the signed-in parent's Stripe status"
                )
        public_subscription = None
        if subscription:
            period_end = subscription.get("current_period_end")
            public_subscription = {
                "plan": subscription.get("plan"),
                "status": subscription.get("status"),
                "current_period_end": (
                    period_end.isoformat()
                    if isinstance(period_end, datetime)
                    else period_end
                ),
                "cancel_at_period_end": bool(
                    subscription.get("cancel_at_period_end")
                ),
            }
        plan = str(subscription.get("plan") or "") if subscription else ""
        is_monthly = plan.endswith("_monthly")
        is_beta = plan == BETA_PLAN
        has_stripe_customer = bool(account.get("stripe_customer_id"))
        return JSONResponse(
            {
                "success": True,
                "has_subscription": bool(subscription),
                "subscription": public_subscription,
                "management": {
                    "can_change": is_monthly,
                    "can_cancel": is_monthly
                    and not bool(subscription.get("cancel_at_period_end")),
                    "can_manage": has_stripe_customer,
                    "can_purchase": not subscription or is_beta,
                    "is_beta": is_beta,
                },
                "refresh": {
                    "attempted": bool(
                        refresh and account.get("stripe_customer_id")
                    ),
                    "succeeded": not refresh_failed,
                },
                **public_billing_status(),
            },
            headers={"Cache-Control": "no-store, private"},
        )

    @router.get("/beta/status")
    async def beta_status():
        return {
            "success": True,
            "enabled": beta_access_enabled(),
            "requires_parent_account": True,
            "payment_required": False,
        }

    @router.post("/beta/redeem")
    async def beta_redeem(body: BetaAccessRequest, request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(
                redeem_beta_access,
                account["id"],
                body.invite_code,
                limit_concurrency=False,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Parent beta access is not configured: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="The parent beta is temporarily unavailable.",
            ) from exc
        subscription = result.get("subscription") or {}
        if not result.get("already_redeemed"):
            record_marketing_event(
                "beta_access_started",
                source="community",
                page="beta",
            )
        period_end = subscription.get("current_period_end")
        return {
            "success": True,
            "already_redeemed": bool(result.get("already_redeemed")),
            "plan": subscription.get("plan"),
            "current_period_end": (
                period_end.isoformat()
                if isinstance(period_end, datetime)
                else period_end
            ),
            "renews": False,
            "payment_required": False,
        }

    @router.post("/checkout")
    async def checkout(body: CheckoutRequest, request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(create_checkout, account, body.plan, limit_concurrency=False)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Billing is not configured yet.") from exc
        except Exception as exc:
            logger.exception("Stripe Checkout session creation failed")
            raise HTTPException(
                status_code=502,
                detail="Stripe checkout is temporarily unavailable. Please try again.",
            ) from exc
        return {"success": True, **result}

    @router.post("/pricing-table-session")
    async def pricing_table_session(request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(
                create_pricing_table_session,
                account,
                limit_concurrency=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Stripe Pricing Table is not ready: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Secure checkout is temporarily unavailable.",
            ) from exc
        except Exception as exc:
            logger.exception("Stripe Customer Session creation failed")
            raise HTTPException(
                status_code=502,
                detail="Stripe checkout is temporarily unavailable. Please try again.",
            ) from exc
        return JSONResponse(
            {"success": True, **result},
            headers={"Cache-Control": "no-store, private"},
        )

    async def portal_response(request: Request, action: str):
        account = await current_account(request)
        try:
            result = await run_blocking(
                create_portal,
                account,
                action,
                timeout=15,
                limit_concurrency=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Billing is not configured yet.") from exc
        except Exception as exc:
            logger.exception("Stripe billing portal session creation failed")
            raise HTTPException(
                status_code=502,
                detail="The Stripe billing portal is temporarily unavailable. Please try again.",
            ) from exc
        return JSONResponse(
            {"success": True, "action": action, **result},
            headers={"Cache-Control": "no-store, private"},
        )

    @router.post("/portal")
    async def portal(request: Request):
        return await portal_response(request, "manage")

    @router.post("/portal/change")
    async def change_plan(request: Request):
        return await portal_response(request, "change")

    @router.post("/portal/cancel")
    async def cancel_plan(request: Request):
        return await portal_response(request, "cancel")

    return router
