"""Privacy-conscious quests, permanent XP and branded gift redemptions.

Lifetime XP measures a learner's progress and never decreases. The legacy
``spendable_xp`` database column stores a separate Gift Points balance.
Everyone can earn XP, while only learners covered by an active recurring
subscription can earn Gift Points or claim physical gifts.

Homework Magic stores no homework text, answers or marks in this subsystem.
An adult recipient's UK delivery address is accepted only during parent
approval, encrypted before it reaches the database, hidden from learner-facing
responses, and scheduled for deletion after dispatch.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    case,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

DEFAULT_REWARDS: tuple[dict[str, Any], ...] = (
    {
        "code": "homework_magic_stickers",
        "name": "Homework Magic sticker pack",
        "icon": "⭐",
        "points_cost": 500,
        "description": "A colourful pack of Homework Magic logo stickers.",
    },
    {
        "code": "homework_magic_pen",
        "name": "Homework Magic pen",
        "icon": "✏️",
        "points_cost": 1000,
        "description": "A Homework Magic logo pen for learning adventures.",
    },
    {
        "code": "homework_magic_notebook",
        "name": "Homework Magic notebook",
        "icon": "📓",
        "points_cost": 2000,
        "description": "A Homework Magic logo notebook for ideas and practice.",
    },
)

CERTIFICATES: tuple[dict[str, Any], ...] = (
    {
        "code": "brilliant_beginner",
        "title": "Brilliant Beginner",
        "threshold": 100,
        "icon": "🌱",
        "message": "for making a brilliant start and showing steady effort",
    },
    {
        "code": "curious_explorer",
        "title": "Curious Explorer",
        "threshold": 500,
        "icon": "🧭",
        "message": "for exploring learning quests with courage and curiosity",
    },
    {
        "code": "homework_hero",
        "title": "Homework Hero",
        "threshold": 1000,
        "icon": "🦸",
        "message": "for keeping going and building a strong learning habit",
    },
    {
        "code": "quest_champion",
        "title": "Quest Champion",
        "threshold": 2_000,
        "icon": "🏆",
        "message": "for completing many learning quests with wonderful effort",
    },
    {
        "code": "learning_legend",
        "title": "Learning Legend",
        "threshold": 5_000,
        "icon": "🌟",
        "message": "for an amazing journey of practice, patience and progress",
    },
)

LEVELS: tuple[dict[str, Any], ...] = (
    {"number": 1, "name": "Spark", "threshold": 0, "icon": "✨"},
    {"number": 2, "name": "Explorer", "threshold": 100, "icon": "🧭"},
    {"number": 3, "name": "Builder", "threshold": 500, "icon": "🧱"},
    {"number": 4, "name": "Champion", "threshold": 1000, "icon": "🏆"},
    {"number": 5, "name": "Superstar", "threshold": 2_000, "icon": "🌠"},
    {"number": 6, "name": "Legend", "threshold": 5_000, "icon": "🌟"},
)

AVATAR_CHARACTER_TYPES: dict[str, str] = {
    "girl": "Girl character",
    "boy": "Boy character",
}
AVATAR_CLOTHES: dict[str, str] = {
    "purple_hoodie": "Purple hoodie",
    "blue_tshirt": "Blue T-shirt",
    "green_jumper": "Green jumper",
    "pink_dress": "Pink dress",
}
AVATAR_SHOES: dict[str, str] = {
    "trainers": "Colourful trainers",
    "boots": "Adventure boots",
    "school_shoes": "Smart school shoes",
}
AVATAR_SKIN_TONES: dict[str, str] = {
    "light": "Light",
    "warm": "Warm",
    "tan": "Tan",
    "deep": "Deep",
}
AVATAR_HAIR_COLOURS: dict[str, str] = {
    "black": "Black",
    "brown": "Brown",
    "blonde": "Blonde",
    "red": "Red",
}
AVATAR_HAIR_LENGTHS: dict[str, str] = {
    "short": "Short",
    "medium": "Medium",
    "long": "Long",
}
AVATAR_HAIR_STYLES: dict[str, str] = {
    "straight": "Straight",
    "curly": "Curly",
    "ponytail": "Ponytail",
    "spiky": "Spiky",
}
AVATAR_EYE_SHAPES: dict[str, str] = {
    "round": "Round",
    "almond": "Almond",
    "smiling": "Smiling",
}
AVATAR_EYE_COLOURS: dict[str, str] = {
    "brown": "Brown",
    "blue": "Blue",
    "green": "Green",
    "grey": "Grey",
}
AVATAR_NOSE_SHAPES: dict[str, str] = {
    "button": "Button",
    "small": "Small",
    "round": "Round",
}
AVATAR_MOUTH_SHAPES: dict[str, str] = {
    "smile": "Smile",
    "grin": "Grin",
    "open": "Open smile",
    "calm": "Calm",
}
AVATAR_EYEBROW_SHAPES: dict[str, str] = {
    "soft": "Soft",
    "straight": "Straight",
    "arched": "Arched",
}
AVATAR_PROFILE_DEFAULTS: dict[str, str] = {
    "character": "girl",
    "clothes": "pink_dress",
    "shoes": "trainers",
    "skin_tone": "warm",
    "hair_colour": "brown",
    "hair_length": "long",
    "hair_style": "ponytail",
    "eye_shape": "round",
    "eye_colour": "green",
    "nose": "button",
    "mouth": "smile",
    "eyebrows": "arched",
}
AVATAR_GROWTH_NAMES: dict[int, str] = {
    1: "Little Learner",
    2: "Curious Explorer",
    3: "Growing Star",
    4: "Clever Champion",
    5: "Super Scholar",
    6: "Learning Legend",
}

DAILY_QUESTS: tuple[dict[str, Any], ...] = (
    {
        "code": "ready_set_learn",
        "name": "Ready, Set, Learn!",
        "description": "Finish and check 1 activity today.",
        "target": 1,
        "bonus_xp": 10,
        "icon": "🚀",
    },
    {
        "code": "double_explorer",
        "name": "Double Explorer",
        "description": "Finish and check 2 activities today.",
        "target": 2,
        "bonus_xp": 15,
        "icon": "🗺️",
    },
    {
        "code": "triple_star",
        "name": "Triple Star",
        "description": "Finish and check 3 activities today.",
        "target": 3,
        "bonus_xp": 20,
        "icon": "🌟",
    },
)

WEEKLY_QUESTS: tuple[dict[str, Any], ...] = (
    {
        "code": "three_day_team",
        "name": "Three-Day Team",
        "description": "Learn on 3 different days this week.",
        "target": 3,
        "progress_kind": "active_days",
        "bonus_xp": 30,
        "icon": "🌈",
    },
    {
        "code": "five_day_hero",
        "name": "Five-Day Hero",
        "description": "Learn on 5 different days this week.",
        "target": 5,
        "progress_kind": "active_days",
        "bonus_xp": 50,
        "icon": "🦸",
    },
    {
        "code": "subject_safari",
        "name": "Subject Safari",
        "description": "Explore 3 different subjects this week.",
        "target": 3,
        "progress_kind": "subjects",
        "bonus_xp": 25,
        "icon": "🦁",
    },
)

_UK_POSTCODE_RE = re.compile(
    r"^(GIR ?0AA|(?:[A-PR-UWYZ][A-HK-Y]?\d[\dA-HJKSTUW]?|"
    r"[A-PR-UWYZ]\d[A-HJKSTUW]?|[A-PR-UWYZ][A-HK-Y]\d[ABEHMNPRVWXY])"
    r" ?\d[ABD-HJLNP-UW-Z]{2})$",
    re.IGNORECASE,
)
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "rewards.db"
_DELIVERY_RETENTION_DAYS = 30


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _now() -> datetime:
    return datetime.now(UTC)


def _reward_timezone() -> ZoneInfo:
    configured = (os.getenv("REWARD_TIMEZONE") or "Europe/London").strip()
    try:
        return ZoneInfo(configured)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _local_day_and_week(value: datetime) -> tuple[str, str]:
    local_day = value.astimezone(_reward_timezone()).date()
    week_start = local_day - timedelta(days=local_day.weekday())
    return local_day.isoformat(), week_start.isoformat()


def _clean_id(value: Any, *, maximum: int = 100) -> str:
    return str(value or "").strip()[:maximum]


def _clean_subject(value: Any) -> str:
    cleaned = " ".join(str(value or "Homework").split())[:80]
    return cleaned or "Homework"


def _clean_delivery_address(value: Mapping[str, Any]) -> dict[str, str]:
    """Validate and minimise a UK address supplied by a parent or guardian."""

    def field(name: str, minimum: int, maximum: int, *, optional: bool = False) -> str:
        cleaned = " ".join(str(value.get(name) or "").split())
        if optional and not cleaned:
            return ""
        if not minimum <= len(cleaned) <= maximum:
            label = name.replace("_", " ")
            raise ValueError(f"Please enter a valid {label}")
        return cleaned

    if value.get("adult_recipient_confirmed") is not True:
        raise ValueError(
            "A parent or guardian must confirm that the delivery recipient is an adult"
        )
    country = str(value.get("country") or "GB").strip().upper()
    if country not in {"GB", "UK", "UNITED KINGDOM"}:
        raise ValueError("Homework Magic gifts can currently be posted only within the UK")

    postcode_compact = re.sub(r"\s+", "", str(value.get("postcode") or "")).upper()
    postcode = (
        f"{postcode_compact[:-3]} {postcode_compact[-3:]}"
        if len(postcode_compact) > 3
        else postcode_compact
    )
    if not _UK_POSTCODE_RE.fullmatch(postcode):
        raise ValueError("Please enter a valid UK postcode")

    return {
        "recipient_name": field("recipient_name", 2, 80),
        "address_line1": field("address_line1", 3, 100),
        "address_line2": field("address_line2", 0, 100, optional=True),
        "town_city": field("town_city", 2, 80),
        "postcode": postcode,
        "country": "United Kingdom",
    }


def _delivery_cipher(secret: str | None = None) -> Fernet:
    configured = (secret or os.getenv("REWARD_DELIVERY_SECRET") or "").strip()
    development = (
        os.getenv("DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        or os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    if len(configured) < 32:
        if not development:
            raise RuntimeError(
                "REWARD_DELIVERY_SECRET must contain at least 32 characters"
            )
        configured = configured or "development-only-reward-delivery-secret"
    key = base64.urlsafe_b64encode(
        hashlib.sha256(configured.encode("utf-8")).digest()
    )
    return Fernet(key)


def _serialise(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, bool):
            data[key] = bool(value)
    return data


def _public_wallet(row: Any) -> dict[str, int]:
    data = _serialise(row) or {}
    return {
        "lifetime_xp": max(0, int(data.get("lifetime_xp") or 0)),
        "gift_points": max(0, int(data.get("spendable_xp") or 0)),
    }


def _public_redemption(
    row: Any,
    *,
    delivery_address_supplied: bool = False,
    include_owner_ids: bool = False,
) -> dict[str, Any]:
    data = _serialise(row) or {}
    points_cost = int(data.pop("xp_cost", 0) or 0)
    if not include_owner_ids:
        data.pop("account_id", None)
        data.pop("student_id", None)
    data["points_cost"] = points_cost
    data["delivery_address_supplied"] = bool(delivery_address_supplied)
    return data


def _level_status(lifetime_xp: int) -> dict[str, Any]:
    points = max(0, int(lifetime_xp or 0))
    current = LEVELS[0]
    next_level: dict[str, Any] | None = None
    for index, level in enumerate(LEVELS):
        if points >= int(level["threshold"]):
            current = level
            next_level = LEVELS[index + 1] if index + 1 < len(LEVELS) else None
    if next_level is None:
        progress_percent = 100
        xp_to_next = 0
    else:
        lower = int(current["threshold"])
        upper = int(next_level["threshold"])
        progress_percent = round((points - lower) / max(1, upper - lower) * 100)
        xp_to_next = max(0, upper - points)
    return {
        "number": current["number"],
        "name": current["name"],
        "icon": current["icon"],
        "threshold": current["threshold"],
        "next": dict(next_level) if next_level else None,
        "xp_to_next": xp_to_next,
        "progress_percent": max(0, min(100, progress_percent)),
    }


def _avatar_payload(
    lifetime_xp: int,
    *,
    profile: Mapping[str, Any] | None = None,
    customised: bool = False,
) -> dict[str, Any]:
    points = max(0, int(lifetime_xp or 0))
    level = _level_status(points)
    next_level = level.get("next")
    supplied = profile or {}
    options = {
        "character": AVATAR_CHARACTER_TYPES,
        "clothes": AVATAR_CLOTHES,
        "shoes": AVATAR_SHOES,
        "skin_tone": AVATAR_SKIN_TONES,
        "hair_colour": AVATAR_HAIR_COLOURS,
        "hair_length": AVATAR_HAIR_LENGTHS,
        "hair_style": AVATAR_HAIR_STYLES,
        "eye_shape": AVATAR_EYE_SHAPES,
        "eye_colour": AVATAR_EYE_COLOURS,
        "nose": AVATAR_NOSE_SHAPES,
        "mouth": AVATAR_MOUTH_SHAPES,
        "eyebrows": AVATAR_EYEBROW_SHAPES,
    }
    safe_profile = {
        key: (
            str(supplied.get(key) or default)
            if str(supplied.get(key) or default) in options[key]
            else default
        )
        for key, default in AVATAR_PROFILE_DEFAULTS.items()
    }
    return {
        "profile": {
            **safe_profile,
            "customised": bool(customised),
        },
        "growth": {
            "stage": int(level["number"]),
            "name": AVATAR_GROWTH_NAMES[int(level["number"])],
            "lifetime_xp": points,
            "progress_percent": int(level["progress_percent"]),
            "xp_to_next": int(level["xp_to_next"]),
            "next_stage": (
                {
                    "stage": int(next_level["number"]),
                    "name": AVATAR_GROWTH_NAMES[int(next_level["number"])],
                    "threshold": int(next_level["threshold"]),
                }
                if next_level
                else None
            ),
        },
    }


def review_fingerprint(
    *,
    homework: str,
    answers: str,
    subject: str,
    reward_activity_id: str | None = None,
    homework_doc_id: str | None = None,
    question_index: int | None = None,
    session_id: str | None = None,
) -> str:
    """Return a non-reversible source key without retaining learner content."""
    if reward_activity_id:
        source = (
            f"activity:{_clean_id(reward_activity_id, maximum=100)}:"
            f"q:{question_index if question_index is not None else 'all'}:"
            f"{_clean_subject(subject)}"
        )
    elif homework_doc_id:
        source = (
            f"doc:{_clean_id(homework_doc_id, maximum=160)}:"
            f"q:{question_index if question_index is not None else 'all'}"
        )
    elif session_id:
        source = (
            f"session:{_clean_id(session_id, maximum=160)}:"
            f"{_clean_subject(subject)}"
        )
    else:
        source = "\x1f".join(
            (
                str(homework or "")[:50_000],
                str(answers or "")[:30_000],
                _clean_subject(subject),
            )
        )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class RewardStore:
    """Concurrency-safe reward persistence for SQLite and PostgreSQL."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        delivery_secret: str | None = None,
    ) -> None:
        self.database_url = normalise_database_url(
            database_url
            or os.getenv("REWARD_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or f"sqlite+pysqlite:///{_DEFAULT_DB}"
        )
        self.delivery_secret = delivery_secret
        self.engine: Engine = get_engine(self.database_url)
        self.metadata = MetaData()
        self.wallets = Table(
            "reward_wallets",
            self.metadata,
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("lifetime_xp", Integer, nullable=False, default=0),
            Column("spendable_xp", Integer, nullable=False, default=0),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.avatar_profiles = Table(
            "reward_avatar_profiles",
            self.metadata,
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("colour", String(20), nullable=False),
            Column("accessory", String(20), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        # Character profiles use a separate table so deployments that already
        # have the original capybara table do not need a blocking ALTER TABLE.
        self.character_profiles = Table(
            "reward_character_profiles",
            self.metadata,
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("character", String(20), nullable=False),
            Column("clothes", String(30), nullable=False),
            Column("shoes", String(30), nullable=False),
            Column("skin_tone", String(20), nullable=False),
            Column("hair_colour", String(20), nullable=False),
            Column("hair_length", String(20), nullable=False),
            Column("hair_style", String(20), nullable=False),
            Column("eye_shape", String(20), nullable=False),
            Column("eye_colour", String(20), nullable=False),
            Column("nose", String(20), nullable=False),
            Column("mouth", String(20), nullable=False),
            Column("eyebrows", String(20), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.events = Table(
            "reward_xp_events",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("student_id", String(80), nullable=False, index=True),
            Column("source_key", String(180), nullable=False),
            Column("event_type", String(40), nullable=False, index=True),
            Column("label", String(80), nullable=False),
            Column("lifetime_delta", Integer, nullable=False, default=0),
            Column("spendable_delta", Integer, nullable=False, default=0),
            Column("subject", String(80), nullable=True),
            Column("local_day", String(10), nullable=False, index=True),
            Column("week_start", String(10), nullable=False, index=True),
            Column("created_at", DateTime(timezone=True), nullable=False, index=True),
            UniqueConstraint("student_id", "source_key", name="uq_reward_event_source"),
        )
        self.certificates = Table(
            "reward_certificates",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("student_id", String(80), nullable=False, index=True),
            Column("certificate_code", String(60), nullable=False),
            Column("unlocked_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint(
                "student_id",
                "certificate_code",
                name="uq_reward_certificate_student_code",
            ),
        )
        self.catalog = Table(
            "reward_catalog_items",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("name", String(40), nullable=False),
            Column("icon", String(12), nullable=False),
            Column("xp_cost", Integer, nullable=False),
            Column("is_active", Boolean, nullable=False, default=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.redemptions = Table(
            "reward_redemptions",
            self.metadata,
            Column("id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("student_id", String(80), nullable=False, index=True),
            Column("reward_code", String(100), nullable=False),
            Column("reward_name", String(40), nullable=False),
            Column("reward_icon", String(12), nullable=False),
            Column("xp_cost", Integer, nullable=False),
            Column("status", String(20), nullable=False, index=True),
            Column("requested_at", DateTime(timezone=True), nullable=False),
            Column("decided_at", DateTime(timezone=True), nullable=True),
            Column("fulfilled_at", DateTime(timezone=True), nullable=True),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.delivery_addresses = Table(
            "reward_delivery_addresses",
            self.metadata,
            Column("redemption_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("student_id", String(80), nullable=False, index=True),
            Column("encrypted_payload", Text, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Column("purge_after", DateTime(timezone=True), nullable=True, index=True),
        )
        self.metadata.create_all(self.engine)

    def initialise(self) -> None:
        self.metadata.create_all(self.engine)

    def _encrypt_delivery_address(self, address: Mapping[str, Any]) -> str:
        clean = _clean_delivery_address(address)
        payload = json.dumps(
            clean,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return _delivery_cipher(self.delivery_secret).encrypt(payload).decode("ascii")

    def _decrypt_delivery_address(self, encrypted_payload: str) -> dict[str, str]:
        try:
            raw = _delivery_cipher(self.delivery_secret).decrypt(
                str(encrypted_payload).encode("ascii")
            )
            value = json.loads(raw.decode("utf-8"))
        except (InvalidToken, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("The delivery address could not be opened safely") from exc
        if not isinstance(value, dict):
            raise TypeError("The delivery address could not be opened safely")
        return {
            key: str(value.get(key) or "")
            for key in (
                "recipient_name",
                "address_line1",
                "address_line2",
                "town_city",
                "postcode",
                "country",
            )
        }

    def _save_delivery_address(
        self,
        conn: Connection,
        *,
        account_id: str,
        student_id: str,
        redemption_id: str,
        encrypted_payload: str,
        saved_at: datetime,
    ) -> None:
        conn.execute(
            delete(self.delivery_addresses).where(
                self.delivery_addresses.c.redemption_id == redemption_id
            )
        )
        conn.execute(
            insert(self.delivery_addresses).values(
                redemption_id=redemption_id,
                account_id=account_id,
                student_id=student_id,
                encrypted_payload=encrypted_payload,
                created_at=saved_at,
                updated_at=saved_at,
                purge_after=None,
            )
        )

    def purge_expired_delivery_addresses(
        self, *, now: datetime | None = None
    ) -> int:
        cutoff = now or _now()
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.delivery_addresses).where(
                    and_(
                        self.delivery_addresses.c.purge_after.is_not(None),
                        self.delivery_addresses.c.purge_after <= cutoff,
                    )
                )
            )
        return int(result.rowcount or 0)

    def _ensure_wallet(
        self,
        conn: Connection,
        account_id: str,
        student_id: str,
        *,
        lock: bool = False,
    ) -> Any:
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        if not account or not learner:
            raise ValueError("A valid account and learner are required")

        query = select(self.wallets).where(self.wallets.c.student_id == learner)
        if lock:
            query = query.with_for_update()
        row = conn.execute(query).first()
        if row is None:
            now = _now()
            try:
                with conn.begin_nested():
                    conn.execute(
                        insert(self.wallets).values(
                            student_id=learner,
                            account_id=account,
                            lifetime_xp=0,
                            spendable_xp=0,
                            created_at=now,
                            updated_at=now,
                        )
                    )
            except IntegrityError:
                pass
            query = select(self.wallets).where(self.wallets.c.student_id == learner)
            if lock:
                query = query.with_for_update()
            row = conn.execute(query).first()
        if row is None or row._mapping["account_id"] != account:
            raise PermissionError(
                "Learner reward wallet does not belong to this account"
            )
        return row

    def _event_exists(self, conn: Connection, student_id: str, source_key: str) -> bool:
        return conn.execute(
            select(self.events.c.id).where(
                and_(
                    self.events.c.student_id == student_id,
                    self.events.c.source_key == source_key,
                )
            )
        ).first() is not None

    def _add_event(
        self,
        conn: Connection,
        *,
        account_id: str,
        student_id: str,
        source_key: str,
        event_type: str,
        label: str,
        lifetime_delta: int,
        spendable_delta: int,
        subject: str | None,
        local_day: str,
        week_start: str,
        created_at: datetime,
    ) -> dict[str, Any] | None:
        if self._event_exists(conn, student_id, source_key):
            return None
        event_id = f"xpe_{uuid.uuid4().hex}"
        try:
            with conn.begin_nested():
                conn.execute(
                    insert(self.events).values(
                        id=event_id,
                        account_id=account_id,
                        student_id=student_id,
                        source_key=source_key[:180],
                        event_type=event_type[:40],
                        label=label[:80],
                        lifetime_delta=int(lifetime_delta),
                        spendable_delta=int(spendable_delta),
                        subject=_clean_subject(subject) if subject else None,
                        local_day=local_day,
                        week_start=week_start,
                        created_at=created_at,
                    )
                )
        except IntegrityError:
            return None
        conn.execute(
            update(self.wallets)
            .where(
                and_(
                    self.wallets.c.student_id == student_id,
                    self.wallets.c.account_id == account_id,
                )
            )
            .values(
                lifetime_xp=self.wallets.c.lifetime_xp + int(lifetime_delta),
                spendable_xp=self.wallets.c.spendable_xp + int(spendable_delta),
                updated_at=created_at,
            )
        )
        return {
            "event_type": event_type,
            "label": label,
            "xp": int(lifetime_delta),
            "gift_points": int(spendable_delta),
        }

    def _unlock_certificates(
        self,
        conn: Connection,
        *,
        account_id: str,
        student_id: str,
        unlocked_at: datetime,
    ) -> list[dict[str, Any]]:
        wallet = conn.execute(
            select(self.wallets.c.lifetime_xp).where(
                and_(
                    self.wallets.c.student_id == student_id,
                    self.wallets.c.account_id == account_id,
                )
            )
        ).first()
        lifetime_xp = int(wallet._mapping["lifetime_xp"] if wallet else 0)
        existing = set(
            conn.execute(
                select(self.certificates.c.certificate_code).where(
                    self.certificates.c.student_id == student_id
                )
            ).scalars()
        )
        unlocked: list[dict[str, Any]] = []
        for certificate in CERTIFICATES:
            code = str(certificate["code"])
            if lifetime_xp < int(certificate["threshold"]) or code in existing:
                continue
            try:
                with conn.begin_nested():
                    conn.execute(
                        insert(self.certificates).values(
                            id=f"cert_{uuid.uuid4().hex}",
                            account_id=account_id,
                            student_id=student_id,
                            certificate_code=code,
                            unlocked_at=unlocked_at,
                        )
                    )
            except IntegrityError:
                continue
            unlocked.append(dict(certificate))
            existing.add(code)
        return unlocked

    def _quest_progress(
        self,
        conn: Connection,
        *,
        student_id: str,
        local_day: str,
        week_start: str,
    ) -> tuple[int, int, int]:
        day_count = int(
            conn.execute(
                select(func.count())
                .select_from(self.events)
                .where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.event_type == "checked_activity",
                        self.events.c.local_day == local_day,
                    )
                )
            ).scalar_one()
            or 0
        )
        active_days = int(
            conn.execute(
                select(func.count(func.distinct(self.events.c.local_day)))
                .select_from(self.events)
                .where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.event_type == "checked_activity",
                        self.events.c.week_start == week_start,
                    )
                )
            ).scalar_one()
            or 0
        )
        subjects = int(
            conn.execute(
                select(func.count(func.distinct(self.events.c.subject)))
                .select_from(self.events)
                .where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.event_type == "checked_activity",
                        self.events.c.week_start == week_start,
                        self.events.c.subject.is_not(None),
                    )
                )
            ).scalar_one()
            or 0
        )
        return day_count, active_days, subjects

    def award_checked_activity(
        self,
        *,
        account_id: str,
        student_id: str,
        fingerprint: str,
        subject: str,
        is_tutor_mode: bool = False,
        gift_points_eligible: bool = False,
        awarded_at: datetime | None = None,
        accuracy: float | None = None,
    ) -> dict[str, Any]:
        """Award permanent XP, plus Gift Points for an eligible subscriber."""
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        digest = _clean_id(fingerprint, maximum=80)
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("A valid review fingerprint is required")

        now = awarded_at or _now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        local_day, week_start = _local_day_and_week(now)
        homework_activity_xp = _bounded_env_int(
            "REWARD_HOMEWORK_ACTIVITY_XP", 20, 1, 100
        )
        activity_xp = (
            max(1, homework_activity_xp // 10)
            if is_tutor_mode
            else homework_activity_xp
        )

        if accuracy is not None and accuracy <= 0.3:
            # 正确率 <= 30% 时 XP 减半
            activity_xp = max(1, activity_xp // 2)
        elif accuracy is not None and accuracy >= 1.0:
            # 正确率 >= 100% 时 XP 增加
            activity_xp = activity_xp + 10
        elif accuracy is not None and accuracy >= 0.8:
            # 正确率 >= 80% 时 XP 增加
            activity_xp = activity_xp + 5
        # Lifetime XP is an effort record for every authenticated learner and
        # must never depend on a plan or stop after a small number of
        # activities. Keep the configurable cap only for subscriber Gift
        # Points, which can be exchanged for physical rewards.
        daily_gift_activity_cap = _bounded_env_int(
            "REWARD_DAILY_ACTIVITY_CAP", 3, 1, 10
        )
        source_key = f"checked:{local_day}:{digest}"
        awarded_events: list[dict[str, Any]] = []
        already_awarded = False
        family_activity_count_before = 0
        family_active_days_before = 0
        family_activity_today_before = 0

        with self.engine.begin() as conn:
            self._ensure_wallet(conn, account, learner, lock=True)
            family_before = conn.execute(
                select(
                    func.count(),
                    func.count(func.distinct(self.events.c.local_day)),
                    func.sum(
                        case(
                            (self.events.c.local_day == local_day, 1),
                            else_=0,
                        )
                    ),
                )
                .select_from(self.events)
                .where(
                    and_(
                        self.events.c.account_id == account,
                        self.events.c.event_type == "checked_activity",
                    )
                )
            ).one()
            family_activity_count_before = int(family_before[0] or 0)
            family_active_days_before = int(family_before[1] or 0)
            family_activity_today_before = int(family_before[2] or 0)
            if self._event_exists(conn, learner, source_key):
                already_awarded = True
            else:
                day_count, _, _ = self._quest_progress(
                    conn,
                    student_id=learner,
                    local_day=local_day,
                    week_start=week_start,
                )
                event = self._add_event(
                    conn,
                    account_id=account,
                    student_id=learner,
                    source_key=source_key,
                    event_type="checked_activity",
                    label="Checked learning activity",
                    lifetime_delta=activity_xp,
                    spendable_delta=(
                        activity_xp
                        if gift_points_eligible and day_count < daily_gift_activity_cap
                        else 0
                    ),
                    subject=subject,
                    local_day=local_day,
                    week_start=week_start,
                    created_at=now,
                )
                if event:
                    awarded_events.append(event)

            day_count, active_days, subject_count = self._quest_progress(
                conn,
                student_id=learner,
                local_day=local_day,
                week_start=week_start,
            )
            if awarded_events and not is_tutor_mode:
                for quest in DAILY_QUESTS:
                    if day_count < int(quest["target"]):
                        continue
                    event = self._add_event(
                        conn,
                        account_id=account,
                        student_id=learner,
                        source_key=f"quest:day:{local_day}:{quest['code']}",
                        event_type="quest_bonus",
                        label=str(quest["name"]),
                        lifetime_delta=int(quest["bonus_xp"]),
                        spendable_delta=int(quest["bonus_xp"]) if gift_points_eligible else 0,
                        subject=None,
                        local_day=local_day,
                        week_start=week_start,
                        created_at=now,
                    )
                    if event:
                        awarded_events.append(event)
                for quest in WEEKLY_QUESTS:
                    progress = (
                        subject_count
                        if quest["progress_kind"] == "subjects"
                        else active_days
                    )
                    if progress < int(quest["target"]):
                        continue
                    event = self._add_event(
                        conn,
                        account_id=account,
                        student_id=learner,
                        source_key=f"quest:week:{week_start}:{quest['code']}",
                        event_type="quest_bonus",
                        label=str(quest["name"]),
                        lifetime_delta=int(quest["bonus_xp"]),
                        spendable_delta=int(quest["bonus_xp"]) if gift_points_eligible else 0,
                        subject=None,
                        local_day=local_day,
                        week_start=week_start,
                        created_at=now,
                    )
                    if event:
                        awarded_events.append(event)

            new_certificates = self._unlock_certificates(
                conn,
                account_id=account,
                student_id=learner,
                unlocked_at=now,
            )
            wallet_row = self._ensure_wallet(conn, account, learner, lock=False)
            wallet = _public_wallet(wallet_row)

        awarded_xp = sum(max(0, int(item["xp"])) for item in awarded_events)
        awarded_gift_points = sum(
            max(0, int(item["gift_points"])) for item in awarded_events
        )
        quest_completions = [
            item for item in awarded_events if item["event_type"] == "quest_bonus"
        ]
        activity_awarded = any(
            item["event_type"] == "checked_activity" for item in awarded_events
        )
        return {
            "awarded_xp": awarded_xp,
            "awarded_gift_points": awarded_gift_points,
            "gift_points_eligible": bool(gift_points_eligible),
            "activity_xp": activity_xp if activity_awarded else 0,
            "already_awarded": already_awarded,
            # Keep the old response fields for deployed clients. They now
            # describe the Gift Points activity cap; lifetime XP is uncapped.
            "daily_cap_reached": day_count >= daily_gift_activity_cap,
            "daily_reward_limit": daily_gift_activity_cap,
            "daily_gift_activity_cap_reached": (
                day_count >= daily_gift_activity_cap
            ),
            "xp_activity_cap": None,
            "lifetime_xp": wallet["lifetime_xp"],
            "gift_points": wallet["gift_points"],
            "level": _level_status(int(wallet.get("lifetime_xp") or 0)),
            "quest_completions": quest_completions,
            "new_certificates": new_certificates,
            # These booleans let the application increment aggregate-only
            # funnel counters without creating a separate user-level tracker.
            "is_first_family_activity": bool(
                activity_awarded and family_activity_count_before == 0
            ),
            "is_first_family_return_day": bool(
                activity_awarded
                and family_active_days_before == 1
                and family_activity_today_before == 0
            ),
        }

    def _quest_cards(
        self,
        conn: Connection,
        *,
        student_id: str,
        local_day: str,
        week_start: str,
    ) -> list[dict[str, Any]]:
        day_count, active_days, subject_count = self._quest_progress(
            conn,
            student_id=student_id,
            local_day=local_day,
            week_start=week_start,
        )
        event_sources = set(
            conn.execute(
                select(self.events.c.source_key).where(
                    and_(
                        self.events.c.student_id == student_id,
                        self.events.c.event_type == "quest_bonus",
                        self.events.c.week_start == week_start,
                    )
                )
            ).scalars()
        )
        cards: list[dict[str, Any]] = []
        for quest in DAILY_QUESTS:
            source = f"quest:day:{local_day}:{quest['code']}"
            cards.append(
                {
                    **dict(quest),
                    "period": "today",
                    "progress": min(day_count, int(quest["target"])),
                    "completed": source in event_sources,
                }
            )
        for quest in WEEKLY_QUESTS:
            progress = (
                subject_count if quest["progress_kind"] == "subjects" else active_days
            )
            source = f"quest:week:{week_start}:{quest['code']}"
            cards.append(
                {
                    **dict(quest),
                    "period": "this week",
                    "progress": min(progress, int(quest["target"])),
                    "completed": source in event_sources,
                }
            )
        return cards

    def _catalog_items(
        self, conn: Connection, account_id: str
    ) -> list[dict[str, Any]]:
        del conn, account_id
        return [
            {
                **dict(item),
                "is_branded": True,
                "requires_delivery": True,
                "is_active": True,
            }
            for item in DEFAULT_REWARDS
        ]

    def learner_summary(self, *, account_id: str, student_id: str) -> dict[str, Any]:
        """Return the compact reward data needed by the family overview."""
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        with self.engine.begin() as conn:
            wallet = _public_wallet(
                self._ensure_wallet(conn, account, learner, lock=False)
            )
            pending = conn.execute(
                select(func.count())
                .select_from(self.redemptions)
                .where(
                    and_(
                        self.redemptions.c.account_id == account,
                        self.redemptions.c.student_id == learner,
                        self.redemptions.c.status == "pending",
                    )
                )
            ).scalar() or 0
        lifetime_xp = int(wallet["lifetime_xp"])
        return {
            "lifetime_xp": lifetime_xp,
            "gift_points": int(wallet["gift_points"]),
            "level": _level_status(lifetime_xp),
            "pending_rewards": int(pending),
        }

    def avatar_summary(self, *, account_id: str, student_id: str) -> dict[str, Any]:
        """Return the small avatar payload used by role-aware navigation."""
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        profile_fields = tuple(AVATAR_PROFILE_DEFAULTS)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(
                    self.wallets.c.lifetime_xp,
                    *(getattr(self.character_profiles.c, key) for key in profile_fields),
                )
                .select_from(
                    self.wallets.outerjoin(
                        self.character_profiles,
                        and_(
                            self.character_profiles.c.student_id
                            == self.wallets.c.student_id,
                            self.character_profiles.c.account_id
                            == self.wallets.c.account_id,
                        ),
                    )
                )
                .where(
                    and_(
                        self.wallets.c.account_id == account,
                        self.wallets.c.student_id == learner,
                    )
                )
            ).first()
        if row is None:
            return _avatar_payload(0)
        data = row._mapping
        customised = bool(data.get("character"))
        return _avatar_payload(
            int(data.get("lifetime_xp") or 0),
            profile={
                key: data.get(key) or AVATAR_PROFILE_DEFAULTS[key]
                for key in profile_fields
            },
            customised=customised,
        )

    def update_avatar(
        self,
        *,
        account_id: str,
        student_id: str,
        character: str,
        clothes: str,
        shoes: str,
        skin_tone: str,
        hair_colour: str,
        hair_length: str,
        hair_style: str,
        eye_shape: str,
        eye_colour: str,
        nose: str,
        mouth: str,
        eyebrows: str,
    ) -> dict[str, Any]:
        """Persist a bounded, child-safe avatar choice for one learner."""
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        raw_profile = {
            "character": character,
            "clothes": clothes,
            "shoes": shoes,
            "skin_tone": skin_tone,
            "hair_colour": hair_colour,
            "hair_length": hair_length,
            "hair_style": hair_style,
            "eye_shape": eye_shape,
            "eye_colour": eye_colour,
            "nose": nose,
            "mouth": mouth,
            "eyebrows": eyebrows,
        }
        option_sets = {
            "character": (AVATAR_CHARACTER_TYPES, "characters"),
            "clothes": (AVATAR_CLOTHES, "clothes"),
            "shoes": (AVATAR_SHOES, "shoes"),
            "skin_tone": (AVATAR_SKIN_TONES, "skin tones"),
            "hair_colour": (AVATAR_HAIR_COLOURS, "hair colours"),
            "hair_length": (AVATAR_HAIR_LENGTHS, "hair lengths"),
            "hair_style": (AVATAR_HAIR_STYLES, "hair styles"),
            "eye_shape": (AVATAR_EYE_SHAPES, "eye shapes"),
            "eye_colour": (AVATAR_EYE_COLOURS, "eye colours"),
            "nose": (AVATAR_NOSE_SHAPES, "nose shapes"),
            "mouth": (AVATAR_MOUTH_SHAPES, "mouth shapes"),
            "eyebrows": (AVATAR_EYEBROW_SHAPES, "eyebrow shapes"),
        }
        chosen_profile: dict[str, str] = {}
        for key, value in raw_profile.items():
            chosen = str(value or "").strip().lower()
            allowed, label = option_sets[key]
            if chosen not in allowed:
                raise ValueError(f"Choose one of the available avatar {label}")
            chosen_profile[key] = chosen

        now = _now()
        with self.engine.begin() as conn:
            wallet = self._ensure_wallet(conn, account, learner, lock=False)
            result = conn.execute(
                update(self.character_profiles)
                .where(
                    and_(
                        self.character_profiles.c.account_id == account,
                        self.character_profiles.c.student_id == learner,
                    )
                )
                .values(**chosen_profile, updated_at=now)
            )
            if not result.rowcount:
                try:
                    with conn.begin_nested():
                        conn.execute(
                            insert(self.character_profiles).values(
                                student_id=learner,
                                account_id=account,
                                **chosen_profile,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                except IntegrityError:
                    conn.execute(
                        update(self.character_profiles)
                        .where(
                            and_(
                                self.character_profiles.c.account_id == account,
                                self.character_profiles.c.student_id == learner,
                            )
                        )
                        .values(**chosen_profile, updated_at=now)
                    )
            lifetime_xp = int(wallet._mapping["lifetime_xp"] or 0)
        return _avatar_payload(
            lifetime_xp,
            profile=chosen_profile,
            customised=True,
        )

    def dashboard(self, *, account_id: str, student_id: str) -> dict[str, Any]:
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        now = _now()
        local_day, week_start = _local_day_and_week(now)
        with self.engine.begin() as conn:
            self._ensure_wallet(conn, account, learner, lock=True)
            self._unlock_certificates(
                conn,
                account_id=account,
                student_id=learner,
                unlocked_at=now,
            )
            wallet = _public_wallet(self._ensure_wallet(conn, account, learner))
            quests = self._quest_cards(
                conn,
                student_id=learner,
                local_day=local_day,
                week_start=week_start,
            )
            unlocked_rows = conn.execute(
                select(
                    self.certificates.c.certificate_code,
                    self.certificates.c.unlocked_at,
                ).where(self.certificates.c.student_id == learner)
            ).all()
            unlocked = {
                row._mapping["certificate_code"]: row._mapping["unlocked_at"]
                for row in unlocked_rows
            }
            certificates = []
            for item in CERTIFICATES:
                unlocked_at = unlocked.get(item["code"])
                certificates.append(
                    {
                        **dict(item),
                        "unlocked": unlocked_at is not None,
                        "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
                        "print_url": (
                            f"/rewards/certificate/{item['code']}?student_id={learner}"
                            if unlocked_at
                            else None
                        ),
                    }
                )
            catalog = self._catalog_items(conn, account)
            redemption_rows = conn.execute(
                select(self.redemptions)
                .where(
                    and_(
                        self.redemptions.c.account_id == account,
                        self.redemptions.c.student_id == learner,
                    )
                )
                .order_by(self.redemptions.c.requested_at.desc())
                .limit(30)
            ).all()
            address_ids = set(
                conn.execute(
                    select(self.delivery_addresses.c.redemption_id).where(
                        and_(
                            self.delivery_addresses.c.account_id == account,
                            self.delivery_addresses.c.student_id == learner,
                        )
                    )
                ).scalars()
            )
            redemptions = [
                _public_redemption(
                    row,
                    delivery_address_supplied=(
                        row._mapping["id"] in address_ids
                    ),
                )
                for row in redemption_rows
            ]
            recent_rows = conn.execute(
                select(
                    self.events.c.label,
                    self.events.c.event_type,
                    self.events.c.subject,
                    self.events.c.lifetime_delta,
                    self.events.c.spendable_delta,
                    self.events.c.created_at,
                )
                .where(
                    and_(
                        self.events.c.student_id == learner,
                        self.events.c.lifetime_delta > 0,
                    )
                )
                .order_by(self.events.c.created_at.desc())
                .limit(12)
            ).all()
            recent_activity = []
            for row in recent_rows:
                item = _serialise(row) or {}
                item["xp_delta"] = int(item.pop("lifetime_delta", 0) or 0)
                item["gift_points_delta"] = int(
                    item.pop("spendable_delta", 0) or 0
                )
                # 对于 checked_activity 事件，用科目名称替换 "Checked learning activity"
                if item.get("event_type") == "checked_activity" and item.get("subject"):
                    item["label"] = item["subject"]
                recent_activity.append(item)
            day_count, active_days, subject_count = self._quest_progress(
                conn,
                student_id=learner,
                local_day=local_day,
                week_start=week_start,
            )

        lifetime_xp = wallet["lifetime_xp"]
        return {
            "wallet": {
                "lifetime_xp": lifetime_xp,
                "gift_points": wallet["gift_points"],
                "level": _level_status(lifetime_xp),
            },
            "quests": quests,
            "certificates": certificates,
            "catalog": catalog,
            "redemptions": redemptions,
            "recent_activity": recent_activity,
            "week_summary": {
                "active_days": active_days,
                "subjects_explored": subject_count,
                "checked_today": day_count,
                "quests_completed": sum(1 for quest in quests if quest["completed"]),
            },
            "rules": {
                "homework_activity_xp": _bounded_env_int(
                    "REWARD_HOMEWORK_ACTIVITY_XP", 20, 1, 100
                ),
                "tutor_activity_xp": max(
                    1,
                    _bounded_env_int("REWARD_HOMEWORK_ACTIVITY_XP", 20, 1, 100) // 10,
                ),
                "daily_activity_cap": _bounded_env_int(
                    "REWARD_DAILY_ACTIVITY_CAP", 3, 1, 10
                ),
                "daily_gift_point_activity_cap": _bounded_env_int(
                    "REWARD_DAILY_ACTIVITY_CAP", 3, 1, 10
                ),
                "xp_activity_cap": None,
                "gift_provider": "homework_magic",
                "delivery_country": "GB",
                "xp_never_deducted": True,
            },
        }

    def _reward_item(
        self, conn: Connection, account_id: str, reward_code: str
    ) -> dict[str, Any] | None:
        del conn, account_id
        code = _clean_id(reward_code, maximum=100)
        default = next((item for item in DEFAULT_REWARDS if item["code"] == code), None)
        if default:
            return {**default, "is_branded": True}
        return None

    def request_redemption(
        self,
        *,
        account_id: str,
        student_id: str,
        reward_code: str,
        gift_points_eligible: bool = False,
    ) -> dict[str, Any]:
        if not gift_points_eligible:
            raise PermissionError(
                "An active Homework Magic subscription is needed to claim gifts"
            )
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        now = _now()
        with self.engine.begin() as conn:
            wallet = self._ensure_wallet(conn, account, learner, lock=True)
            item = self._reward_item(conn, account, reward_code)
            if item is None:
                raise ValueError("That gift is not available")
            if int(wallet._mapping["spendable_xp"]) < int(item["points_cost"]):
                raise ValueError(
                    "Keep learning to collect enough Gift Points for this gift"
                )
            pending_count = int(
                conn.execute(
                    select(func.count())
                    .select_from(self.redemptions)
                    .where(
                        and_(
                            self.redemptions.c.student_id == learner,
                            self.redemptions.c.status == "pending",
                        )
                    )
                ).scalar_one()
                or 0
            )
            if pending_count >= 3:
                raise ValueError("A grown-up needs to check the waiting requests first")
            existing = conn.execute(
                select(self.redemptions.c.id).where(
                    and_(
                        self.redemptions.c.student_id == learner,
                        self.redemptions.c.reward_code == item["code"],
                        self.redemptions.c.status == "pending",
                    )
                )
            ).first()
            if existing:
                raise ValueError("This reward is already waiting for a grown-up")
            redemption_id = f"red_{uuid.uuid4().hex}"
            conn.execute(
                insert(self.redemptions).values(
                    id=redemption_id,
                    account_id=account,
                    student_id=learner,
                    reward_code=item["code"],
                    reward_name=item["name"],
                    reward_icon=item["icon"],
                    xp_cost=int(item["points_cost"]),
                    status="pending",
                    requested_at=now,
                    decided_at=None,
                    fulfilled_at=None,
                    updated_at=now,
                )
            )
            row = conn.execute(
                select(self.redemptions).where(
                    self.redemptions.c.id == redemption_id
                )
            ).first()
        return _public_redemption(row)

    def request_custom_redemption(
        self,
        *,
        account_id: str,
        student_id: str,
        reward_name: str,
        reward_icon: str = "🎁",
        xp_cost: int,
    ) -> dict[str, Any]:
        """孩子自定义礼物请求：输入礼物名称和点数，等待家长审批。"""
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        name = str(reward_name or "").strip()[:40]
        if not name:
            raise ValueError("Please enter a gift name")
        icon = str(reward_icon or "🎁").strip()[:12] or "🎁"
        cost = max(10, min(int(xp_cost or 0), 5000))
        now = _now()
        with self.engine.begin() as conn:
            wallet = self._ensure_wallet(conn, account, learner, lock=True)
            if int(wallet._mapping["spendable_xp"]) < cost:
                raise ValueError(
                    "Keep learning to collect enough Gift Points for this gift"
                )
            pending_count = int(
                conn.execute(
                    select(func.count())
                    .select_from(self.redemptions)
                    .where(
                        and_(
                            self.redemptions.c.student_id == learner,
                            self.redemptions.c.status == "pending",
                        )
                    )
                ).scalar_one()
                or 0
            )
            if pending_count >= 3:
                raise ValueError("A grown-up needs to check the waiting requests first")
            redemption_id = f"red_{uuid.uuid4().hex}"
            # 使用 custom: 前缀区分自定义请求
            reward_code = f"custom:{redemption_id}"
            conn.execute(
                insert(self.redemptions).values(
                    id=redemption_id,
                    account_id=account,
                    student_id=learner,
                    reward_code=reward_code,
                    reward_name=name,
                    reward_icon=icon,
                    xp_cost=cost,
                    status="pending",
                    requested_at=now,
                    decided_at=None,
                    fulfilled_at=None,
                    updated_at=now,
                )
            )
            row = conn.execute(
                select(self.redemptions).where(
                    self.redemptions.c.id == redemption_id
                )
            ).first()
        return _public_redemption(row)

    def get_pending_redemptions_for_account(
        self,
        *,
        account_id: str,
    ) -> list[dict[str, Any]]:
        """获取家庭所有待审批的礼物请求。"""
        account = _clean_id(account_id, maximum=80)
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.redemptions)
                .where(
                    and_(
                        self.redemptions.c.account_id == account,
                        self.redemptions.c.status == "pending",
                    )
                )
                .order_by(self.redemptions.c.requested_at.desc())
            ).fetchall()
        return [_public_redemption(row, include_owner_ids=True) for row in rows]

    def decide_redemption(
        self,
        *,
        account_id: str,
        redemption_id: str,
        decision: str,
        delivery_address: Mapping[str, Any] | None = None,
        gift_points_eligible: bool = False,
    ) -> dict[str, Any]:
        account = _clean_id(account_id, maximum=80)
        redemption = _clean_id(redemption_id, maximum=80)
        action = str(decision or "").strip().lower()
        if action not in {"approve", "decline", "dispatch", "cancel"}:
            raise ValueError("Choose approve, decline, dispatch or cancel")
        encrypted_address: str | None = None
        if action == "approve":
            if not gift_points_eligible:
                raise PermissionError(
                    "An active Homework Magic subscription is needed to approve a gift"
                )
            if delivery_address is None:
                raise ValueError(
                    "A parent or guardian must enter the UK delivery address"
                )
            encrypted_address = self._encrypt_delivery_address(delivery_address)
        now = _now()
        local_day, week_start = _local_day_and_week(now)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.redemptions)
                .where(
                    and_(
                        self.redemptions.c.id == redemption,
                        self.redemptions.c.account_id == account,
                    )
                )
                .with_for_update()
            ).first()
            if row is None:
                raise LookupError("Reward request not found")
            item = row._mapping
            status = str(item["status"])
            learner = str(item["student_id"])
            wallet = self._ensure_wallet(conn, account, learner, lock=True)
            values: dict[str, Any] = {"updated_at": now}

            if action == "approve":
                if status != "pending":
                    raise ValueError("Only a waiting request can be approved")
                if int(wallet._mapping["spendable_xp"]) < int(item["xp_cost"]):
                    raise ValueError(
                        "There are not enough Gift Points for this gift"
                    )
                if encrypted_address is None:
                    raise ValueError(
                        "A parent or guardian must enter the UK delivery address"
                    )
                event = self._add_event(
                    conn,
                    account_id=account,
                    student_id=learner,
                    source_key=f"redemption:{redemption}:spend",
                    event_type="gift_points_spend",
                    label=f"Gift approved: {item['reward_name']}",
                    lifetime_delta=0,
                    spendable_delta=-int(item["xp_cost"]),
                    subject=None,
                    local_day=local_day,
                    week_start=week_start,
                    created_at=now,
                )
                if event is None:
                    raise ValueError("This gift has already been approved")
                self._save_delivery_address(
                    conn,
                    account_id=account,
                    student_id=learner,
                    redemption_id=redemption,
                    encrypted_payload=encrypted_address,
                    saved_at=now,
                )
                values.update(status="approved", decided_at=now)
            elif action == "decline":
                if status != "pending":
                    raise ValueError("Only a waiting request can be declined")
                values.update(status="declined", decided_at=now)
            elif action == "dispatch":
                if status != "approved":
                    raise ValueError("Only an approved gift can be dispatched")
                address_exists = conn.execute(
                    select(self.delivery_addresses.c.redemption_id).where(
                        self.delivery_addresses.c.redemption_id == redemption
                    )
                ).first()
                if address_exists is None:
                    raise ValueError(
                        "This gift has no delivery address; ask the parent to try again"
                    )
                conn.execute(
                    update(self.delivery_addresses)
                    .where(self.delivery_addresses.c.redemption_id == redemption)
                    .values(
                        updated_at=now,
                        purge_after=now + timedelta(days=_DELIVERY_RETENTION_DAYS),
                    )
                )
                values.update(status="dispatched", fulfilled_at=now)
            else:
                if status not in {"pending", "approved"}:
                    raise ValueError("This request can no longer be cancelled")
                if status == "approved":
                    event = self._add_event(
                        conn,
                        account_id=account,
                        student_id=learner,
                        source_key=f"redemption:{redemption}:refund",
                        event_type="gift_points_refund",
                        label=f"Gift Points returned: {item['reward_name']}",
                        lifetime_delta=0,
                        spendable_delta=int(item["xp_cost"]),
                        subject=None,
                        local_day=local_day,
                        week_start=week_start,
                        created_at=now,
                    )
                    if event is None:
                        raise ValueError(
                            "The Gift Points for this gift were already returned"
                        )
                conn.execute(
                    delete(self.delivery_addresses).where(
                        self.delivery_addresses.c.redemption_id == redemption
                    )
                )
                values.update(status="cancelled", decided_at=now)

            conn.execute(
                update(self.redemptions)
                .where(self.redemptions.c.id == redemption)
                .values(**values)
            )
            updated_redemption = conn.execute(
                select(self.redemptions).where(
                    self.redemptions.c.id == redemption
                )
            ).first()
            updated_wallet = self._ensure_wallet(conn, account, learner)
            address_supplied = conn.execute(
                select(self.delivery_addresses.c.redemption_id).where(
                    self.delivery_addresses.c.redemption_id == redemption
                )
            ).first() is not None
        return {
            "redemption": _public_redemption(
                updated_redemption,
                delivery_address_supplied=address_supplied,
            ),
            "wallet": _public_wallet(updated_wallet),
        }

    def list_reward_orders(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return address-free order summaries for the administrator queue."""
        allowed = {"pending", "approved", "declined", "dispatched", "cancelled"}
        clean_status = str(status or "").strip().lower() or None
        if clean_status and clean_status not in allowed:
            raise ValueError("Invalid gift order status")
        self.purge_expired_delivery_addresses()
        query = select(self.redemptions)
        if clean_status:
            query = query.where(self.redemptions.c.status == clean_status)
        else:
            query = query.where(
                self.redemptions.c.status.in_(("approved", "dispatched"))
            )
        query = query.order_by(self.redemptions.c.updated_at.desc()).limit(
            max(1, min(200, int(limit)))
        )
        with self.engine.begin() as conn:
            rows = conn.execute(query).all()
            order_ids = [str(row._mapping["id"]) for row in rows]
            address_ids = set(
                conn.execute(
                    select(self.delivery_addresses.c.redemption_id).where(
                        self.delivery_addresses.c.redemption_id.in_(order_ids)
                    )
                ).scalars()
            ) if order_ids else set()
        return [
            _public_redemption(
                row,
                delivery_address_supplied=row._mapping["id"] in address_ids,
            )
            for row in rows
        ]

    def get_reward_order(self, *, redemption_id: str) -> dict[str, Any] | None:
        """Return one order and its decrypted adult delivery address for admins."""
        redemption = _clean_id(redemption_id, maximum=80)
        self.purge_expired_delivery_addresses()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.redemptions).where(
                    self.redemptions.c.id == redemption
                )
            ).first()
            address_row = conn.execute(
                select(self.delivery_addresses).where(
                    self.delivery_addresses.c.redemption_id == redemption
                )
            ).first()
        if row is None:
            return None
        address = (
            self._decrypt_delivery_address(
                str(address_row._mapping["encrypted_payload"])
            )
            if address_row is not None
            else None
        )
        return {
            "order": _public_redemption(
                row,
                delivery_address_supplied=address is not None,
            ),
            "delivery_address": address,
            "address_purge_after": (
                address_row._mapping["purge_after"].isoformat()
                if address_row is not None
                and address_row._mapping["purge_after"] is not None
                else None
            ),
        }

    def decide_reward_order(
        self,
        *,
        redemption_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """Dispatch or cancel an order from the protected administrator queue."""
        redemption = _clean_id(redemption_id, maximum=80)
        action = str(decision or "").strip().lower()
        if action not in {"dispatch", "cancel"}:
            raise ValueError("Choose dispatch or cancel")
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.redemptions.c.account_id).where(
                    self.redemptions.c.id == redemption
                )
            ).first()
        if row is None:
            raise LookupError("Gift order not found")
        return self.decide_redemption(
            account_id=str(row._mapping["account_id"]),
            redemption_id=redemption,
            decision=action,
        )

    def get_certificate(
        self, *, account_id: str, student_id: str, certificate_code: str
    ) -> dict[str, Any] | None:
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        code = _clean_id(certificate_code, maximum=60)
        definition = next((item for item in CERTIFICATES if item["code"] == code), None)
        if definition is None:
            return None
        with self.engine.begin() as conn:
            self._ensure_wallet(conn, account, learner)
            row = conn.execute(
                select(self.certificates.c.unlocked_at).where(
                    and_(
                        self.certificates.c.account_id == account,
                        self.certificates.c.student_id == learner,
                        self.certificates.c.certificate_code == code,
                    )
                )
            ).first()
        if row is None:
            return None
        unlocked_at = row._mapping["unlocked_at"]
        return {
            **dict(definition),
            "unlocked_at": unlocked_at.isoformat(),
        }

    def delete_learner(self, *, account_id: str, student_id: str) -> dict[str, int]:
        account = _clean_id(account_id, maximum=80)
        learner = _clean_id(student_id, maximum=80)
        counts: dict[str, int] = {}
        with self.engine.begin() as conn:
            for key, table in (
                ("delivery_addresses", self.delivery_addresses),
                ("redemptions", self.redemptions),
                ("certificates", self.certificates),
                ("xp_events", self.events),
                ("character_profiles", self.character_profiles),
                ("avatar_profiles", self.avatar_profiles),
                ("wallets", self.wallets),
            ):
                result = conn.execute(
                    delete(table).where(
                        and_(
                            table.c.account_id == account,
                            table.c.student_id == learner,
                        )
                    )
                )
                counts[key] = int(result.rowcount or 0)
        return counts

    def delete_account(self, account_id: str) -> dict[str, int]:
        account = _clean_id(account_id, maximum=80)
        counts: dict[str, int] = {}
        with self.engine.begin() as conn:
            for key, table in (
                ("delivery_addresses", self.delivery_addresses),
                ("redemptions", self.redemptions),
                ("certificates", self.certificates),
                ("xp_events", self.events),
                ("character_profiles", self.character_profiles),
                ("avatar_profiles", self.avatar_profiles),
                ("wallets", self.wallets),
                ("catalog_items", self.catalog),
            ):
                result = conn.execute(
                    delete(table).where(table.c.account_id == account)
                )
                counts[key] = int(result.rowcount or 0)
        return counts

    # 家长自定义奖励目录管理

    def list_catalog_items(
        self, *, account_id: str, include_inactive: bool = False
    ) -> list[dict[str, Any]]:
        """列出家长为该家庭创建的自定义奖励。"""
        account = _clean_id(account_id, maximum=80)
        query = select(self.catalog).where(self.catalog.c.account_id == account)
        if not include_inactive:
            query = query.where(self.catalog.c.is_active.is_(True))
        query = query.order_by(self.catalog.c.created_at.desc())
        with self.engine.begin() as conn:
            rows = conn.execute(query).all()
        return [
            {
                "id": row._mapping["id"],
                "name": row._mapping["name"],
                "icon": row._mapping["icon"],
                "xp_cost": int(row._mapping["xp_cost"]),
                "is_active": bool(row._mapping["is_active"]),
                "created_at": row._mapping["created_at"].isoformat()
                if row._mapping["created_at"] else None,
            }
            for row in rows
        ]

    def create_catalog_item(
        self,
        *,
        account_id: str,
        name: str,
        icon: str,
        xp_cost: int,
    ) -> dict[str, Any]:
        """家长创建自定义奖励（如书本、电影票、足球等）。"""
        account = _clean_id(account_id, maximum=80)
        clean_name = " ".join(str(name or "").split())[:40]
        if not clean_name:
            raise ValueError("Please enter a reward name")
        clean_icon = str(icon or "").strip()[:12] or "gift"
        cost = max(10, min(int(xp_cost or 0), 5000))
        now = _now()
        item_id = f"cat_{uuid.uuid4().hex}"
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.catalog).values(
                    id=item_id,
                    account_id=account,
                    name=clean_name,
                    icon=clean_icon,
                    xp_cost=cost,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = conn.execute(
                select(self.catalog).where(self.catalog.c.id == item_id)
            ).first()
        return {
            "id": row._mapping["id"],
            "name": row._mapping["name"],
            "icon": row._mapping["icon"],
            "xp_cost": int(row._mapping["xp_cost"]),
            "is_active": bool(row._mapping["is_active"]),
            "created_at": row._mapping["created_at"].isoformat()
            if row._mapping["created_at"] else None,
        }

    def update_catalog_item(
        self,
        *,
        account_id: str,
        item_id: str,
        name: str | None = None,
        icon: str | None = None,
        xp_cost: int | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """家长更新自定义奖励。"""
        account = _clean_id(account_id, maximum=80)
        clean_id = _clean_id(item_id, maximum=80)
        values: dict[str, Any] = {"updated_at": _now()}
        if name is not None:
            clean_name = " ".join(str(name).split())[:40]
            if clean_name:
                values["name"] = clean_name
        if icon is not None:
            values["icon"] = str(icon).strip()[:12] or "gift"
        if xp_cost is not None:
            values["xp_cost"] = max(10, min(int(xp_cost), 5000))
        if is_active is not None:
            values["is_active"] = bool(is_active)
        with self.engine.begin() as conn:
            conn.execute(
                update(self.catalog)
                .where(
                    and_(
                        self.catalog.c.id == clean_id,
                        self.catalog.c.account_id == account,
                    )
                )
                .values(**values)
            )
            row = conn.execute(
                select(self.catalog).where(self.catalog.c.id == clean_id)
            ).first()
        if row is None:
            raise LookupError("Reward not found")
        return {
            "id": row._mapping["id"],
            "name": row._mapping["name"],
            "icon": row._mapping["icon"],
            "xp_cost": int(row._mapping["xp_cost"]),
            "is_active": bool(row._mapping["is_active"]),
            "created_at": row._mapping["created_at"].isoformat()
            if row._mapping["created_at"] else None,
        }

    def delete_catalog_item(self, *, account_id: str, item_id: str) -> bool:
        """家长删除自定义奖励。"""
        account = _clean_id(account_id, maximum=80)
        clean_id = _clean_id(item_id, maximum=80)
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.catalog).where(
                    and_(
                        self.catalog.c.id == clean_id,
                        self.catalog.c.account_id == account,
                    )
                )
            )
        return bool(result.rowcount)

    def decide_redemption_with_custom_xp(
        self,
        *,
        account_id: str,
        redemption_id: str,
        decision: str,
        xp_to_deduct: int | None = None,
    ) -> dict[str, Any]:
        """家长审批/拒绝孩子的奖励请求，可自定义扣除的 XP 数量。

        奖励为线下交接（如书本、电影票），无需配送地址。
        """
        account = _clean_id(account_id, maximum=80)
        redemption = _clean_id(redemption_id, maximum=80)
        action = str(decision or "").strip().lower()
        if action not in {"approve", "decline"}:
            raise ValueError("Choose approve or decline")
        now = _now()
        local_day, week_start = _local_day_and_week(now)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.redemptions)
                .where(
                    and_(
                        self.redemptions.c.id == redemption,
                        self.redemptions.c.account_id == account,
                    )
                )
                .with_for_update()
            ).first()
            if row is None:
                raise LookupError("Reward request not found")
            item = row._mapping
            status = str(item["status"])
            learner = str(item["student_id"])
            wallet = self._ensure_wallet(conn, account, learner, lock=True)
            values: dict[str, Any] = {"updated_at": now}

            if action == "approve":
                if status != "pending":
                    raise ValueError("Only a waiting request can be approved")
                # 家长可自定义扣除的 XP 数量
                deduct = int(xp_to_deduct) if xp_to_deduct is not None else int(item["xp_cost"])
                deduct = max(0, min(deduct, int(wallet._mapping["spendable_xp"])))
                if deduct <= 0:
                    raise ValueError("Not enough Gift Points to approve this reward")
                event = self._add_event(
                    conn,
                    account_id=account,
                    student_id=learner,
                    source_key=f"redemption:{redemption}:spend",
                    event_type="gift_points_spend",
                    label=f"Gift approved: {item['reward_name']}",
                    lifetime_delta=0,
                    spendable_delta=-deduct,
                    subject=None,
                    local_day=local_day,
                    week_start=week_start,
                    created_at=now,
                )
                if event is None:
                    raise ValueError("This gift has already been approved")
                values.update(
                    status="approved",
                    decided_at=now,
                    xp_cost=deduct,
                )
            else:  # decline
                if status != "pending":
                    raise ValueError("Only a waiting request can be declined")
                values.update(status="declined", decided_at=now)

            conn.execute(
                update(self.redemptions)
                .where(self.redemptions.c.id == redemption)
                .values(**values)
            )
            updated_redemption = conn.execute(
                select(self.redemptions).where(
                    self.redemptions.c.id == redemption
                )
            ).first()
            updated_wallet = self._ensure_wallet(conn, account, learner)
        return {
            "redemption": _public_redemption(updated_redemption),
            "wallet": _public_wallet(updated_wallet),
        }

    def get_xp_digest_for_account(
        self,
        *,
        account_id: str,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """查询家庭在过去一段时间内的 XP 收益摘要，用于每日邮件通知。"""
        account = _clean_id(account_id, maximum=80)
        cutoff = since or (_now() - timedelta(hours=24))
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.events.c.student_id,
                    func.sum(self.events.c.lifetime_delta).label("total_xp"),
                    func.sum(
                        case(
                            (self.events.c.event_type == "checked_activity", 1),
                            else_=0,
                        )
                    ).label("event_count"),
                )
                .where(
                    and_(
                        self.events.c.account_id == account,
                        self.events.c.created_at >= cutoff,
                        self.events.c.lifetime_delta > 0,
                    )
                )
                .group_by(self.events.c.student_id)
            ).all()
        digest = []
        for row in rows:
            digest.append({
                "student_id": row._mapping["student_id"],
                "total_xp": int(row._mapping["total_xp"] or 0),
                "event_count": int(row._mapping["event_count"] or 0),
            })
        return {
            "account_id": account,
            "period_start": cutoff.isoformat(),
            "kids": digest,
        }


_store: RewardStore | None = None
_store_lock = threading.Lock()


def get_reward_store() -> RewardStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = RewardStore()
    return _store
