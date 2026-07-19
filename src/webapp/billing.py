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

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, insert, select, update
from sqlalchemy.exc import IntegrityError

from .db import engine_options, normalise_database_url
from .account_store import (
    account_has_used_plan,
    ensure_account,
    get_account_by_stripe_customer_id,
    get_active_subscription,
    set_stripe_customer,
    upsert_stripe_subscription,
)
from .runtime import run_blocking


logger = logging.getLogger(__name__)
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


class CheckoutRequest(BaseModel):
    plan: str


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
    if get_active_subscription(account["id"]):
        raise ValueError("This account already has an active subscription")
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
        customer=customer_id,
        line_items=[{"price": plans[plan], "quantity": 1}],
        success_url=f"{base}/pricing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/pricing?checkout=cancelled",
        client_reference_id=account["id"],
        metadata={"account_id": account["id"], "plan": plan},
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


def create_portal(account: Dict[str, Any]) -> Dict[str, str]:
    issues = billing_configuration_issues()
    if issues:
        raise RuntimeError("; ".join(issues))
    customer_id = account.get("stripe_customer_id")
    if not customer_id:
        raise ValueError("No Stripe customer exists for this account")
    stripe = _stripe()
    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{_base_url()}/pricing",
    )
    return {"portal_url": portal.url}


def _timestamp(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def sync_subscription(subscription: Any, fallback_account_id: Optional[str] = None) -> Dict[str, Any]:
    metadata = _object_value(subscription, "metadata", {}) or {}
    account_id = metadata.get("account_id") or fallback_account_id
    customer_id = _object_value(subscription, "customer")
    if not account_id and customer_id:
        account = get_account_by_stripe_customer_id(str(customer_id))
        account_id = account and account["id"]
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
    return upsert_stripe_subscription(
        account_id=account_id,
        plan=plan,
        status=str(_object_value(subscription, "status", "incomplete")),
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(_object_value(subscription, "id")),
        price_id=str(price_id) if price_id else None,
        current_period_end=_timestamp(period_end),
        cancel_at_period_end=bool(_object_value(subscription, "cancel_at_period_end", False)),
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
        kwargs: Dict[str, Any] = engine_options(url)
        self.engine = create_engine(url, **kwargs)
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


def process_webhook(payload: bytes, signature: str) -> str:
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
            sync_subscription(obj)
        elif event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            metadata = _object_value(obj, "metadata", {}) or {}
            if metadata.get("plan") == TRIAL_PLAN:
                # Card payments are normally paid at completion; delayed methods
                # are granted only by async_payment_succeeded.
                if str(_object_value(obj, "payment_status", "")).lower() == "paid":
                    sync_trial_checkout(obj)
                ledger().finish(event_id, "processed")
                return "processed"
            subscription_id = _object_value(obj, "subscription")
            account_id = _object_value(obj, "client_reference_id")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                sync_subscription(subscription, fallback_account_id=account_id)
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
    async def stripe_webhook(request: Request):
        signature = request.headers.get("Stripe-Signature", "")
        payload = await request.body()
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        try:
            status = await run_blocking(process_webhook, payload, signature, limit_concurrency=False)
        except Exception as exc:
            # Signature and processing failures must return non-2xx so Stripe retries.
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
        return {"received": True, "status": status}

    @router.get("/plans")
    async def plans():
        return {"success": True, **public_billing_status()}

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

    @router.post("/portal")
    async def portal(request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(create_portal, account, limit_concurrency=False)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Billing is not configured yet.") from exc
        except Exception as exc:
            logger.exception("Stripe billing portal session creation failed")
            raise HTTPException(
                status_code=502,
                detail="The Stripe billing portal is temporarily unavailable. Please try again.",
            ) from exc
        return {"success": True, **result}

    return router
