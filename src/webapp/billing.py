"""Stripe Checkout, customer portal and verified webhook billing.

Entitlements are updated only from signed Stripe webhooks. Learner records are
never sent to Stripe; billing uses the authenticated parent/guardian account.
"""
from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, insert, select, update
from sqlalchemy.exc import IntegrityError

from .db import engine_options, normalise_database_url
from .account_store import (
    ensure_account,
    get_account_by_stripe_customer_id,
    get_active_subscription,
    set_stripe_customer,
    upsert_stripe_subscription,
)
from .runtime import run_blocking


class CheckoutRequest(BaseModel):
    plan: str


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
    candidates = {
        "homework_monthly": os.getenv("STRIPE_PRICE_HOMEWORK_MONTHLY", ""),
        "elevenplus_monthly": os.getenv("STRIPE_PRICE_ELEVENPLUS_MONTHLY", ""),
        "family_monthly": os.getenv("STRIPE_PRICE_FAMILY_MONTHLY", ""),
    }
    return {name: price for name, price in candidates.items() if price}


def _base_url() -> str:
    value = os.getenv("APP_BASE_URL", "http://localhost:5000").rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("APP_BASE_URL must be an absolute HTTP(S) URL")
    if os.getenv("DEV_MODE", "").lower() not in {"1", "true", "yes"} and parsed.scheme != "https":
        raise RuntimeError("APP_BASE_URL must use HTTPS in production")
    return value


def create_checkout(account: Dict[str, Any], plan: str) -> Dict[str, str]:
    plans = _plans()
    if plan not in plans:
        raise ValueError("Unknown or unavailable subscription plan")
    if get_active_subscription(account["id"]):
        raise ValueError("This account already has an active subscription")
    stripe = _stripe()
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
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": plans[plan], "quantity": 1}],
        success_url=f"{base}/pricing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/pricing?checkout=cancelled",
        client_reference_id=account["id"],
        metadata={"account_id": account["id"], "plan": plan},
        subscription_data={"metadata": {"account_id": account["id"], "plan": plan}},
        allow_promotion_codes=True,
        idempotency_key=f"checkout-{account['id']}-{plan}-{attempt}",
    )
    return {"checkout_url": session.url, "checkout_session_id": session.id}


def create_portal(account: Dict[str, Any]) -> Dict[str, str]:
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


def _object_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


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
    plan = metadata.get("plan") or "premium"
    return upsert_stripe_subscription(
        account_id=account_id,
        plan=plan,
        status=str(_object_value(subscription, "status", "incomplete")),
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(_object_value(subscription, "id")),
        price_id=str(price_id) if price_id else None,
        current_period_end=_timestamp(_object_value(subscription, "current_period_end")),
        cancel_at_period_end=bool(_object_value(subscription, "cancel_at_period_end", False)),
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
    expected_raw = os.getenv("STRIPE_EXPECTED_LIVEMODE")
    if expected_raw is None:
        expected_live = os.getenv("STRIPE_SECRET_KEY", "").startswith("sk_live_")
    else:
        expected_live = expected_raw.strip().lower() in {"1", "true", "yes", "on"}
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
        elif event_type == "checkout.session.completed":
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
        return {"success": True, "plans": list(_plans())}

    @router.post("/checkout")
    async def checkout(body: CheckoutRequest, request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(create_checkout, account, body.plan, limit_concurrency=False)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Billing is not configured yet.") from exc
        return {"success": True, **result}

    @router.post("/portal")
    async def portal(request: Request):
        account = await current_account(request)
        try:
            result = await run_blocking(create_portal, account, limit_concurrency=False)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"success": True, **result}

    return router
