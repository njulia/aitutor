"""Secure Stripe Pricing Table integration for Homework Magic.

The browser receives only Stripe's public Pricing Table configuration and a
short-lived Customer Session secret. Subscription access is stored locally
only after Stripe signs a webhook event. Learner names, answers, school data,
and learning-memory content are never sent to Stripe.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    and_,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine

logger = logging.getLogger(__name__)

# These values are public identifiers supplied by Stripe. Environment
# variables can override them without requiring another code deployment.
DEFAULT_PRICING_TABLE_ID = "prctbl_1TvlP9A7C4P8kXJMSS8t4VRT"
DEFAULT_PUBLISHABLE_KEY = "pk_live_fYeIDSqsqYC6MDKau5eFsI0U"
ACTIVE_STATUSES = ("active", "trialing")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_metadata = MetaData()
_engine_lock = threading.Lock()
_billing_engine: Optional[Engine] = None
_billing_engine_url: Optional[str] = None
_portal_configuration_lock = threading.Lock()
_portal_configuration_cache: Dict[str, str] = {}

billing_accounts = Table(
    "stripe_billing_accounts",
    _metadata,
    Column("username", String(254), primary_key=True),
    Column("account_ref", String(80), nullable=False, unique=True, index=True),
    Column("stripe_customer_id", String(100), nullable=True, unique=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

billing_subscriptions = Table(
    "stripe_billing_subscriptions",
    _metadata,
    Column("stripe_subscription_id", String(100), primary_key=True),
    Column("username", String(254), nullable=False, index=True),
    Column("stripe_customer_id", String(100), nullable=False, index=True),
    Column("plan", String(100), nullable=False),
    Column("price_id", String(100), nullable=True),
    Column("product_id", String(100), nullable=True),
    Column("status", String(30), nullable=False, index=True),
    Column("current_period_end", DateTime(timezone=True), nullable=True),
    Column("cancel_at_period_end", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _normalise_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("A valid parent or guardian email address is required")
    return email


def _normalise_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


def _database_url() -> str:
    # Test fixtures replace DATABASE_URL per test; honour that isolated store
    # without changing the dedicated billing database used in production.
    if os.getenv("TESTING", "").lower() in {"1", "true", "yes"}:
        configured = os.getenv("DATABASE_URL") or os.getenv("BILLING_DATABASE_URL")
    else:
        configured = os.getenv("BILLING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return _normalise_database_url(configured.strip())
    fallback = Path(__file__).resolve().parents[2] / "data" / "stripe_billing.db"
    return f"sqlite+pysqlite:///{fallback}"


def _engine() -> Engine:
    global _billing_engine, _billing_engine_url
    url = _database_url()
    if _billing_engine is not None and _billing_engine_url == url:
        return _billing_engine
    with _engine_lock:
        if _billing_engine is not None and _billing_engine_url == url:
            return _billing_engine
        if url.startswith("sqlite"):
            Path(url.split("///", 1)[-1]).parent.mkdir(parents=True, exist_ok=True)
        _billing_engine = get_engine(url)
        _billing_engine_url = url
        _metadata.create_all(_billing_engine)
        return _billing_engine


def _row_dict(row: Any) -> Optional[Dict[str, Any]]:
    return dict(row._mapping) if row is not None else None


def ensure_billing_account(username: str) -> Dict[str, Any]:
    email = _normalise_email(username)
    engine = _engine()
    with engine.begin() as connection:
        row = connection.execute(
            select(billing_accounts).where(billing_accounts.c.username == email)
        ).first()
    if row is None:
        now = _now()
        try:
            with engine.begin() as connection:
                connection.execute(
                    insert(billing_accounts).values(
                        username=email,
                        account_ref=f"acct_{uuid.uuid4().hex}",
                        stripe_customer_id=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            # Another worker may have created the same account concurrently.
            pass
        with engine.begin() as connection:
            row = connection.execute(
                select(billing_accounts).where(billing_accounts.c.username == email)
            ).first()
    account = _row_dict(row)
    if not account:
        raise RuntimeError("Unable to create the billing account")
    return account


def _account_by_reference(account_ref: str) -> Optional[Dict[str, Any]]:
    if not account_ref:
        return None
    with _engine().begin() as connection:
        return _row_dict(
            connection.execute(
                select(billing_accounts).where(
                    billing_accounts.c.account_ref == str(account_ref)
                )
            ).first()
        )


def _account_by_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        return None
    with _engine().begin() as connection:
        return _row_dict(
            connection.execute(
                select(billing_accounts).where(
                    billing_accounts.c.stripe_customer_id == str(customer_id)
                )
            ).first()
        )


def _set_customer(username: str, customer_id: str) -> Dict[str, Any]:
    if not str(customer_id or "").startswith("cus_"):
        raise ValueError("Stripe returned an invalid customer identifier")
    with _engine().begin() as connection:
        connection.execute(
            update(billing_accounts)
            .where(billing_accounts.c.username == _normalise_email(username))
            .values(stripe_customer_id=str(customer_id), updated_at=_now())
        )
        row = connection.execute(
            select(billing_accounts).where(
                billing_accounts.c.username == _normalise_email(username)
            )
        ).first()
    account = _row_dict(row)
    if not account:
        raise RuntimeError("Unable to link the Stripe customer")
    return account


def _object_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe():
    try:
        import stripe
    except ImportError as exc:
        raise RuntimeError("The Stripe Python package is not installed") from exc
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = secret_key
    return stripe


def _pricing_table_id() -> str:
    return os.getenv("STRIPE_PRICING_TABLE_ID", DEFAULT_PRICING_TABLE_ID).strip()


def _publishable_key() -> str:
    return os.getenv("STRIPE_PUBLISHABLE_KEY", DEFAULT_PUBLISHABLE_KEY).strip()


def _is_live_key(value: str) -> Optional[bool]:
    if value.startswith(("sk_live_", "rk_live_", "pk_live_")):
        return True
    if value.startswith(("sk_test_", "rk_test_", "pk_test_")):
        return False
    return None


def billing_configuration_issues() -> list[str]:
    issues: list[str] = []
    table_id = _pricing_table_id()
    publishable_key = _publishable_key()
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()

    if not table_id.startswith("prctbl_"):
        issues.append("STRIPE_PRICING_TABLE_ID is not configured")
    if _is_live_key(publishable_key) is None:
        issues.append("STRIPE_PUBLISHABLE_KEY is not configured")
    if _is_live_key(secret_key) is None:
        issues.append("STRIPE_SECRET_KEY is not configured")
    if _is_live_key(publishable_key) is not None and _is_live_key(secret_key) is not None:
        if _is_live_key(publishable_key) != _is_live_key(secret_key):
            issues.append("Stripe publishable and secret keys use different modes")
    if not webhook_secret.startswith("whsec_"):
        issues.append("STRIPE_WEBHOOK_SECRET is not configured")
    return issues


def _base_url() -> str:
    value = os.getenv("APP_BASE_URL", "http://localhost:5000").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("APP_BASE_URL must be an absolute HTTP(S) URL")
    dev_mode = os.getenv("DEV_MODE", "").strip().lower() in {"1", "true", "yes"}
    if not dev_mode and parsed.scheme != "https":
        raise RuntimeError("APP_BASE_URL must use HTTPS in production")
    return value


def _active_subscription(username: str) -> Optional[Dict[str, Any]]:
    email = _normalise_email(username)
    now = _now()
    with _engine().begin() as connection:
        row = connection.execute(
            select(billing_subscriptions)
            .where(
                and_(
                    billing_subscriptions.c.username == email,
                    billing_subscriptions.c.status.in_(ACTIVE_STATUSES),
                    billing_subscriptions.c.current_period_end.is_not(None),
                    billing_subscriptions.c.current_period_end > now,
                )
            )
            .order_by(billing_subscriptions.c.updated_at.desc())
            .limit(1)
        ).first()
    return _row_dict(row)


def billing_account_has_active_subscription(
    username: str,
    required_plans: Optional[list[str]] = None,
) -> bool:
    """Fast local entitlement check; this never calls Stripe.

    When a feature names a plan, a Homework Premium subscription must not
    unlock 11+ Premium (or the reverse). Family and introductory access remain
    valid across both learning areas.
    """
    try:
        subscription = _active_subscription(username)
        if subscription is None:
            return False
        if not required_plans:
            return True
        plan = str(subscription.get("plan") or "")
        # 家庭档含 11+ 套餐与五日体验覆盖全部学习区
        if plan in {"family_11plus_monthly", "trial_5day"}:
            return True
        # 家庭档不含 11+ 套餐仅覆盖 Years 1-6 家庭作业
        if plan == "family_monthly":
            return "homework_monthly" in {str(item) for item in required_plans if item}
        return plan in {str(item) for item in required_plans if item}
    except (TypeError, ValueError):
        return False


def _create_customer(account: Dict[str, Any]) -> Dict[str, Any]:
    stripe = _stripe()
    customer = stripe.Customer.create(
        email=account["username"],
        metadata={
            "homework_magic_account_ref": account["account_ref"],
            "service": "Homework Magic",
        },
        idempotency_key=f"homework-magic-customer-{account['account_ref']}",
    )
    return _set_customer(account["username"], str(_object_value(customer, "id", "")))


def create_pricing_table_session(username: str) -> Dict[str, Any]:
    issues = billing_configuration_issues()
    if issues:
        raise RuntimeError("; ".join(issues))
    if _active_subscription(username):
        raise ValueError("This account already has an active plan. Manage it in the billing portal.")

    account = ensure_billing_account(username)
    if not account.get("stripe_customer_id"):
        account = _create_customer(account)

    stripe = _stripe()
    customer_session = stripe.CustomerSession.create(
        customer=account["stripe_customer_id"],
        components={"pricing_table": {"enabled": True}},
    )
    client_secret = str(_object_value(customer_session, "client_secret", ""))
    if not client_secret:
        raise RuntimeError("Stripe did not return a Customer Session secret")
    return {
        "client_secret": client_secret,
        "account_ref": account["account_ref"],
        "pricing_table_id": _pricing_table_id(),
        "publishable_key": _publishable_key(),
    }


def _portal_price_ids() -> list[str]:
    """Return recurring plans that parents may switch between in Stripe."""
    configured = (
        os.getenv("STRIPE_PRICE_HOMEWORK_MONTHLY", "").strip(),
        os.getenv("STRIPE_PRICE_ELEVENPLUS_MONTHLY", "").strip(),
        os.getenv("STRIPE_PRICE_FAMILY_MONTHLY", "").strip(),
        os.getenv("STRIPE_PRICE_FAMILY_11PLUS_MONTHLY", "").strip(),
    )
    return list(
        dict.fromkeys(
            price_id for price_id in configured if price_id.startswith("price_")
        )
    )


def _portal_product_catalog(stripe: Any, price_ids: list[str]) -> list[Dict[str, Any]]:
    """Resolve Price IDs to the Product catalogue required by Stripe Portal."""
    grouped: Dict[str, list[str]] = {}
    for price_id in price_ids:
        price = stripe.Price.retrieve(price_id)
        if not bool(_object_value(price, "active", False)):
            raise RuntimeError("A Stripe plan configured for changes is inactive")
        recurring = _object_value(price, "recurring", {}) or {}
        if str(_object_value(recurring, "interval", "")) != "month":
            raise RuntimeError("Stripe plan changes require recurring monthly prices")
        product = _object_value(price, "product")
        product_id = str(_object_value(product, "id", product) or "")
        if not product_id.startswith("prod_"):
            raise RuntimeError("Stripe returned an invalid product for a monthly plan")
        grouped.setdefault(product_id, []).append(price_id)
    return [
        {
            "product": product_id,
            "prices": prices,
            "adjustable_quantity": {"enabled": False},
        }
        for product_id, prices in sorted(grouped.items())
    ]


def _portal_configuration(stripe: Any, *, enable_plan_changes: bool) -> str:
    """Create one idempotent, app-owned portal configuration per plan catalogue.

    Stripe's default portal can have plan switching disabled. Supplying this
    explicit configuration makes cancellation and switching predictable in
    every deployment while retaining Stripe's hosted confirmation screens.
    """
    price_ids = _portal_price_ids() if enable_plan_changes else []
    if enable_plan_changes and len(price_ids) < 2:
        raise RuntimeError(
            "At least two monthly Stripe Price IDs are required for plan changes"
        )

    configured_id = os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "").strip()
    if configured_id:
        if not configured_id.startswith("bpc_"):
            raise RuntimeError("STRIPE_PORTAL_CONFIGURATION_ID is invalid")
        return configured_id

    stripe_mode = "live" if _is_live_key(_publishable_key()) else "test"
    catalogue_key = f"{stripe_mode}:" + (",".join(sorted(price_ids)) or "cancel-only")
    fingerprint = hashlib.sha256(catalogue_key.encode("utf-8")).hexdigest()[:24]
    cached = _portal_configuration_cache.get(fingerprint)
    if cached:
        return cached

    with _portal_configuration_lock:
        cached = _portal_configuration_cache.get(fingerprint)
        if cached:
            return cached

        configurations = stripe.billing_portal.Configuration.list(limit=100)
        for existing in _object_value(configurations, "data", []) or []:
            metadata = _object_value(existing, "metadata", {}) or {}
            if (
                bool(_object_value(existing, "active", False))
                and str(_object_value(metadata, "catalogue_fingerprint", ""))
                == fingerprint
                and str(_object_value(metadata, "schema", ""))
                == "subscription_management_v1"
            ):
                configuration_id = str(_object_value(existing, "id", ""))
                if configuration_id.startswith("bpc_"):
                    _portal_configuration_cache[fingerprint] = configuration_id
                    return configuration_id

        products = _portal_product_catalog(stripe, price_ids) if price_ids else []
        subscription_update: Dict[str, Any] = {"enabled": bool(products)}
        if products:
            subscription_update.update(
                {
                    "default_allowed_updates": ["price"],
                    "proration_behavior": "create_prorations",
                    "products": products,
                }
            )
        base_url = _base_url()
        configuration = stripe.billing_portal.Configuration.create(
            name="Homework Magic subscription management",
            default_return_url=f"{base_url}/pricing",
            business_profile={
                "headline": "Manage your Homework Magic plan securely",
                "privacy_policy_url": f"{base_url}/privacy",
                "terms_of_service_url": f"{base_url}/terms",
            },
            features={
                "customer_update": {"enabled": False, "allowed_updates": []},
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
                "subscription_update": subscription_update,
            },
            metadata={
                "service": "homework_magic",
                "catalogue_fingerprint": fingerprint,
                "schema": "subscription_management_v1",
            },
            idempotency_key=f"homework-magic-portal-v1-{fingerprint}",
        )
        configuration_id = str(_object_value(configuration, "id", ""))
        if not configuration_id.startswith("bpc_"):
            raise RuntimeError("Stripe did not return a valid portal configuration")
        _portal_configuration_cache[fingerprint] = configuration_id
        return configuration_id


def create_customer_portal(username: str, action: str = "manage") -> str:
    if action not in {"manage", "change", "cancel"}:
        raise ValueError("Unknown billing action")
    account = ensure_billing_account(username)
    customer_id = account.get("stripe_customer_id")
    if not customer_id:
        raise ValueError("No Stripe billing account exists yet")
    subscription = _active_subscription(username)
    if action in {"change", "cancel"} and not subscription:
        raise ValueError("No active subscription is available to change or cancel")

    stripe = _stripe()
    return_url = f"{_base_url()}/pricing?billing=returned"
    can_change_plan = len(_portal_price_ids()) >= 2
    session_params: Dict[str, Any] = {
        "customer": customer_id,
        "return_url": return_url,
        "configuration": _portal_configuration(
            stripe,
            enable_plan_changes=action == "change"
            or (action == "manage" and can_change_plan),
        ),
    }
    if action in {"change", "cancel"}:
        flow_type = (
            "subscription_update" if action == "change" else "subscription_cancel"
        )
        subscription_id = str(subscription["stripe_subscription_id"])
        completion = "changed" if action == "change" else "cancelled"
        session_params["flow_data"] = {
            "type": flow_type,
            flow_type: {"subscription": subscription_id},
            "after_completion": {
                "type": "redirect",
                "redirect": {
                    "return_url": f"{_base_url()}/pricing?billing={completion}"
                },
            },
        }

    portal = stripe.billing_portal.Session.create(**session_params)
    portal_url = str(_object_value(portal, "url", ""))
    if not portal_url.startswith("https://"):
        raise RuntimeError("Stripe did not return a secure billing portal URL")
    return portal_url


def _timestamp(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def _plan_for_price(price_id: Optional[str], product_id: Optional[str]) -> str:
    configured = {
        "trial_5day": os.getenv("STRIPE_PRICE_TRIAL_5DAY", "").strip(),
        "homework_monthly": os.getenv("STRIPE_PRICE_HOMEWORK_MONTHLY", "").strip(),
        "elevenplus_monthly": os.getenv("STRIPE_PRICE_ELEVENPLUS_MONTHLY", "").strip(),
        "family_monthly": os.getenv("STRIPE_PRICE_FAMILY_MONTHLY", "").strip(),
        "family_11plus_monthly": os.getenv("STRIPE_PRICE_FAMILY_11PLUS_MONTHLY", "").strip(),
    }
    for plan, configured_price in configured.items():
        if configured_price and configured_price == price_id:
            return plan
    # The current application uses a single premium entitlement. Keeping the
    # Stripe identifier preserves an audit trail until optional plan-specific
    # Price IDs are configured.
    return str(product_id or price_id or "premium")[:100]


def _upsert_subscription(
    subscription: Any,
    *,
    fallback_account_ref: Optional[str] = None,
) -> Dict[str, Any]:
    subscription_id = str(_object_value(subscription, "id", ""))
    customer_id = str(_object_value(subscription, "customer", ""))
    if not subscription_id.startswith("sub_") or not customer_id.startswith("cus_"):
        raise ValueError("Stripe subscription identifiers are missing")

    account = _account_by_customer(customer_id)
    reference_account = (
        _account_by_reference(fallback_account_ref) if fallback_account_ref else None
    )
    if account and reference_account and account["username"] != reference_account["username"]:
        raise ValueError("Stripe Checkout reference does not match its customer")
    if account is None and fallback_account_ref:
        account = reference_account
        if account and account.get("stripe_customer_id") not in (None, customer_id):
            raise ValueError("Stripe customer does not match the Homework Magic account")
        if account and not account.get("stripe_customer_id"):
            account = _set_customer(account["username"], customer_id)
    if account is None:
        raise ValueError("Stripe subscription is not linked to a Homework Magic account")

    items = _object_value(_object_value(subscription, "items", {}), "data", []) or []
    price_id: Optional[str] = None
    product_id: Optional[str] = None
    if items:
        price = _object_value(items[0], "price", {})
        price_id = str(_object_value(price, "id", "") or "") or None
        product = _object_value(price, "product")
        product_id = str(_object_value(product, "id", product) or "") or None

    period_end = _object_value(subscription, "current_period_end")
    if not period_end and items:
        period_end = max(
            (int(_object_value(item, "current_period_end", 0) or 0) for item in items),
            default=0,
        ) or None
    status = str(_object_value(subscription, "status", "incomplete")).strip().lower()
    if status == "canceled":
        status = "cancelled"
    allowed_statuses = {
        "active",
        "trialing",
        "past_due",
        "unpaid",
        "cancelled",
        "incomplete",
        "incomplete_expired",
        "paused",
    }
    if status not in allowed_statuses:
        status = "incomplete"
    if status in ACTIVE_STATUSES and not period_end:
        raise ValueError("Active Stripe subscription has no current period end")

    now = _now()
    values = {
        "username": account["username"],
        "stripe_customer_id": customer_id,
        "plan": _plan_for_price(price_id, product_id),
        "price_id": price_id,
        "product_id": product_id,
        "status": status,
        "current_period_end": _timestamp(period_end),
        "cancel_at_period_end": bool(
            _object_value(subscription, "cancel_at_period_end", False)
        ),
        "updated_at": now,
    }
    engine = _engine()
    try:
        with engine.begin() as connection:
            result = connection.execute(
                update(billing_subscriptions)
                .where(billing_subscriptions.c.stripe_subscription_id == subscription_id)
                .values(**values)
            )
            if not result.rowcount:
                connection.execute(
                    insert(billing_subscriptions).values(
                        stripe_subscription_id=subscription_id,
                        created_at=now,
                        **values,
                    )
                )
    except IntegrityError:
        # Two webhook deliveries can race across Cloud Run instances. The
        # unique subscription id makes the second delivery a safe update.
        with engine.begin() as connection:
            connection.execute(
                update(billing_subscriptions)
                .where(billing_subscriptions.c.stripe_subscription_id == subscription_id)
                .values(**values)
            )
    with engine.begin() as connection:
        row = connection.execute(
            select(billing_subscriptions).where(
                billing_subscriptions.c.stripe_subscription_id == subscription_id
            )
        ).first()
    saved = _row_dict(row)
    if not saved:
        raise RuntimeError("Unable to save the Stripe subscription")
    return saved


def process_stripe_webhook(payload: bytes, signature: str) -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret.startswith("whsec_"):
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
    stripe = _stripe()
    event = stripe.Webhook.construct_event(payload, signature, secret)
    event_live = bool(_object_value(event, "livemode", False))
    expected_live = bool(_is_live_key(_publishable_key()))
    if event_live != expected_live:
        raise ValueError("Stripe webhook mode does not match this deployment")

    event_type = str(_object_value(event, "type", ""))
    event_object = _object_value(_object_value(event, "data", {}), "object")
    subscription_events = {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
    }
    if event_type in subscription_events:
        _upsert_subscription(event_object)
        return "processed"

    if event_type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        subscription_id = _object_value(event_object, "subscription")
        account_ref = _object_value(event_object, "client_reference_id")
        if subscription_id:
            subscription = stripe.Subscription.retrieve(str(subscription_id))
            _upsert_subscription(subscription, fallback_account_ref=str(account_ref or ""))
            return "processed"
        # Pricing Tables are subscription-only. Never grant access for an
        # unexpected one-off Checkout Session.
        return "ignored_non_subscription_checkout"

    if event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
        subscription_id = _object_value(event_object, "subscription")
        if subscription_id:
            subscription = stripe.Subscription.retrieve(str(subscription_id))
            _upsert_subscription(subscription)
            return "processed"
    return "ignored"


def build_stripe_pricing_router(
    resolve_username: Callable[[Request], Optional[str]],
) -> APIRouter:
    router = APIRouter(prefix="/api/billing", tags=["billing"])

    def require_parent(request: Request) -> str:
        username = resolve_username(request)
        if not username:
            raise HTTPException(
                status_code=401,
                detail="A parent or guardian must sign in before checkout.",
            )
        return username

    @router.post("/pricing-table-session")
    async def pricing_table_session(request: Request):
        username = require_parent(request)
        try:
            result = await asyncio.to_thread(create_pricing_table_session, username)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Stripe Pricing Table is not ready: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Secure checkout is temporarily unavailable.",
            ) from exc
        except Exception as exc:
            logger.exception("Unable to create Stripe Customer Session")
            raise HTTPException(
                status_code=502,
                detail="Stripe checkout is temporarily unavailable. Please try again.",
            ) from exc
        return JSONResponse(
            {"success": True, **result},
            headers={"Cache-Control": "no-store, private"},
        )

    @router.get("/status")
    async def billing_status(request: Request):
        username = require_parent(request)
        subscription = await asyncio.to_thread(_active_subscription, username)
        public_subscription = None
        if subscription:
            public_subscription = {
                "plan": subscription["plan"],
                "status": subscription["status"],
                "current_period_end": subscription["current_period_end"].isoformat()
                if subscription.get("current_period_end")
                else None,
                "cancel_at_period_end": bool(subscription["cancel_at_period_end"]),
            }
        return JSONResponse(
            {
                "success": True,
                "has_subscription": bool(subscription),
                "subscription": public_subscription,
                "management": {
                    "can_change": bool(subscription) and len(_portal_price_ids()) >= 2,
                    "can_cancel": bool(subscription)
                    and not bool(subscription.get("cancel_at_period_end")),
                },
            },
            headers={"Cache-Control": "no-store, private"},
        )

    async def portal_response(request: Request, action: str):
        username = require_parent(request)
        try:
            portal_url = await asyncio.to_thread(
                create_customer_portal, username, action
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Stripe customer portal is not ready: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Subscription management is temporarily unavailable.",
            ) from exc
        except Exception as exc:
            logger.exception("Unable to create Stripe customer portal session")
            raise HTTPException(
                status_code=502,
                detail="The billing portal is temporarily unavailable. Please try again.",
            ) from exc
        return JSONResponse(
            {"success": True, "portal_url": portal_url, "action": action},
            headers={"Cache-Control": "no-store, private"},
        )

    @router.post("/portal")
    async def customer_portal(request: Request):
        return await portal_response(request, "manage")

    @router.post("/portal/{action}")
    async def customer_portal_action(action: str, request: Request):
        if action not in {"change", "cancel"}:
            raise HTTPException(status_code=404, detail="Unknown billing action")
        return await portal_response(request, action)

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        signature = request.headers.get("Stripe-Signature", "")
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        payload = await request.body()
        try:
            webhook_status = await asyncio.to_thread(
                process_stripe_webhook, payload, signature
            )
        except Exception as exc:
            # A non-2xx response tells Stripe to retry a valid event that could
            # not be persisted. Raw payloads and signatures are never logged.
            logger.exception("Stripe webhook verification or processing failed")
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
        return {"received": True, "status": webhook_status}

    return router
