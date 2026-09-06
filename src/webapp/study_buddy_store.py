"""Privacy-first Study Buddy persistence and challenge/reward logic."""
from __future__ import annotations
import secrets
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint, and_, delete, func, insert, select, union_all, update
from sqlalchemy.exc import IntegrityError
from .account_store import _engine, get_student, students
from .study_buddy_challenge_catalog import (
    CHALLENGE_CATALOG,
    challenge_catalog_entry,
    challenge_subject_matches,
)

_metadata = MetaData()
buddy_requests = Table(
    "study_buddy_requests", _metadata,
    Column("id", String(80), primary_key=True),
    Column("requester_student_id", String(80), nullable=False, index=True),
    Column("target_student_id", String(80), nullable=False, index=True),
    Column("requester_parent_approved", Boolean, nullable=False, default=False),
    Column("target_parent_approved", Boolean, nullable=False, default=False),
    Column("status", String(20), nullable=False, default="pending"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("pair_key", String(161), nullable=True, index=True),
    UniqueConstraint("requester_student_id", "target_student_id", name="uq_study_buddy_pair"),
)
buddy_challenges = Table(
    "study_buddy_challenges", _metadata,
    Column("id", String(80), primary_key=True),
    Column("requester_student_id", String(80), nullable=False, index=True),
    Column("target_student_id", String(80), nullable=False, index=True),
    Column("challenge_type", String(40), nullable=False),
    Column("title", String(100), nullable=False),
    Column("target_count", Integer, nullable=False),
    Column("xp_reward", Integer, nullable=False),
    Column("gift_points_reward", Integer, nullable=False),
    Column("status", String(20), nullable=False, default="open"),
    Column("completed_by_student_id", String(80), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("verified_activity_count", Integer, nullable=False, default=0),
    Column("completion_source", String(40), nullable=True),
)
buddy_emoji_reactions = Table(
    "study_buddy_emoji_reactions", _metadata,
    Column("id", String(80), primary_key=True),
    Column("sender_student_id", String(80), nullable=False, index=True),
    Column("recipient_student_id", String(80), nullable=False, index=True),
    Column("emoji", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Reactions automatically disappear after a short period. This keeps the
    # feature a light, kind signal rather than an ongoing child message log.
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
)

study_buddy_settings = Table(
    "study_buddy_settings", _metadata,
    Column("id", String(40), primary_key=True),
    Column("max_buddies_per_learner", Integer, nullable=False),
    # This is a daily sending limit.  It is kept alongside the buddy limit so
    # an administrator can tune both child-safety limits from one place.
    Column("max_emojis_per_learner", Integer, nullable=False, default=40),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

DEFAULT_MAX_BUDDIES_PER_LEARNER = 40
# Retained as the public default for integrations that import this constant.
MAX_BUDDIES_PER_LEARNER = DEFAULT_MAX_BUDDIES_PER_LEARNER
MAX_CONFIGURABLE_BUDDIES_PER_LEARNER = 100
DAILY_EMOJI_SEND_LIMIT = 40
DEFAULT_MAX_EMOJIS_PER_LEARNER = DAILY_EMOJI_SEND_LIMIT
MAX_CONFIGURABLE_EMOJIS_PER_LEARNER = 100
EMOJI_REACTION_RETENTION_DAYS = 7
EMOJI_OPTIONS = {
    "heart": {"emoji": "❤️", "label": "Heart"},
    "like": {"emoji": "👍", "label": "Like"},
    "shake_hand": {"emoji": "🤝", "label": "Shake Hand"},
    "smile": {"emoji": "😊", "label": "Smile"},
    "laugh": {"emoji": "😂", "label": "Laugh"},
    "wink": {"emoji": "😉", "label": "Wink"},
    "flower": {"emoji": "🌹", "label": "Flower"},
    "high_five": {"emoji": "🙌", "label": "High five"},
    "star": {"emoji": "⭐", "label": "Star"},
}

def init_study_buddy_db() -> None:
    # Account migrations own learner codes. Run them first so an upgraded
    # Study Buddy table never queries a pre-Buddy-Code students table.
    from .account_store import init_account_db
    from .study_buddy_migrations import run_study_buddy_migrations
    init_account_db()
    run_study_buddy_migrations()

def _now() -> datetime: return datetime.now(UTC)
def _row(r): return dict(r._mapping) if r else None

def _pair(a: str, b: str) -> tuple[str,str]: return tuple(sorted((str(a), str(b))))


def get_study_buddy_settings() -> dict[str, int]:
    """Return the child-safe, admin-configured Study Buddy limits."""
    with _engine().begin() as conn:
        row = conn.execute(
            select(
                study_buddy_settings.c.max_buddies_per_learner,
                study_buddy_settings.c.max_emojis_per_learner,
            ).where(
                study_buddy_settings.c.id == "global"
            )
        ).first()
    buddy_limit = int(row.max_buddies_per_learner) if row else DEFAULT_MAX_BUDDIES_PER_LEARNER
    emoji_limit = (
        int(row.max_emojis_per_learner)
        if row and row.max_emojis_per_learner is not None
        else DEFAULT_MAX_EMOJIS_PER_LEARNER
    )
    if not 1 <= buddy_limit <= MAX_CONFIGURABLE_BUDDIES_PER_LEARNER:
        buddy_limit = DEFAULT_MAX_BUDDIES_PER_LEARNER
    if not 1 <= emoji_limit <= MAX_CONFIGURABLE_EMOJIS_PER_LEARNER:
        emoji_limit = DEFAULT_MAX_EMOJIS_PER_LEARNER
    return {
        "max_buddies_per_learner": buddy_limit,
        "max_emojis_per_learner": emoji_limit,
    }


def set_max_buddies_per_learner(value: int) -> dict[str, int]:
    """Save a global limit; existing connections are intentionally unchanged."""
    limit = int(value)
    if not 1 <= limit <= MAX_CONFIGURABLE_BUDDIES_PER_LEARNER:
        raise ValueError(
            f"The maximum number of Study Buddies must be between 1 and {MAX_CONFIGURABLE_BUDDIES_PER_LEARNER}."
        )
    current = get_study_buddy_settings()
    with _engine().begin() as conn:
        existing = conn.execute(
            select(study_buddy_settings.c.id).where(study_buddy_settings.c.id == "global")
        ).first()
        values = {
            "max_buddies_per_learner": limit,
            "max_emojis_per_learner": current["max_emojis_per_learner"],
            "updated_at": _now(),
        }
        if existing:
            conn.execute(
                update(study_buddy_settings)
                .where(study_buddy_settings.c.id == "global")
                .values(**values)
            )
        else:
            conn.execute(insert(study_buddy_settings).values(id="global", **values))
    return {"max_buddies_per_learner": limit, **{
        "max_emojis_per_learner": current["max_emojis_per_learner"],
    }}


def set_max_emojis_per_learner(value: int) -> dict[str, int]:
    """Save the maximum number of kind emojis a child can send each day."""
    limit = int(value)
    if not 1 <= limit <= MAX_CONFIGURABLE_EMOJIS_PER_LEARNER:
        raise ValueError(
            "The maximum number of kind emojis must be between 1 and "
            f"{MAX_CONFIGURABLE_EMOJIS_PER_LEARNER}."
        )
    current = get_study_buddy_settings()
    with _engine().begin() as conn:
        existing = conn.execute(
            select(study_buddy_settings.c.id).where(study_buddy_settings.c.id == "global")
        ).first()
        values = {
            "max_buddies_per_learner": current["max_buddies_per_learner"],
            "max_emojis_per_learner": limit,
            "updated_at": _now(),
        }
        if existing:
            conn.execute(
                update(study_buddy_settings)
                .where(study_buddy_settings.c.id == "global")
                .values(**values)
            )
        else:
            conn.execute(insert(study_buddy_settings).values(id="global", **values))
    return {"max_buddies_per_learner": current["max_buddies_per_learner"], "max_emojis_per_learner": limit}


def max_buddies_per_learner() -> int:
    return get_study_buddy_settings()["max_buddies_per_learner"]


def max_emojis_per_learner() -> int:
    return get_study_buddy_settings()["max_emojis_per_learner"]


def _active_buddy_count(conn, student_id: str) -> int:
    sent = conn.execute(select(func.count()).select_from(buddy_requests).where(and_(
        buddy_requests.c.status == "active",
        buddy_requests.c.requester_student_id == student_id,
    ))).scalar() or 0
    received = conn.execute(select(func.count()).select_from(buddy_requests).where(and_(
        buddy_requests.c.status == "active",
        buddy_requests.c.target_student_id == student_id,
    ))).scalar() or 0
    return int(sent) + int(received)

def find_students(query: str, requester_student_id: str, limit: int = 10) -> list[dict[str, Any]]:
    # A shared Buddy Code is an exact, indexed lookup. We deliberately do not
    # offer a searchable child directory by name, email or school.
    code = str(query or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,10}\d{4}", code):
        return []
    requester = str(requester_student_id)
    with _engine().begin() as conn:
        stmt = select(students.c.id, students.c.name, students.c.year_group).where(
            and_(
                students.c.is_active.is_(True),
                students.c.id != requester,
                students.c.buddy_code == code,
            )
        )
        rows = conn.execute(stmt.limit(1)).all()
    return [{"student_id": r.id, "nickname": r.name, "year_group": r.year_group} for r in rows]


def buddy_code_for(student_id: str) -> str | None:
    """Return only the signed-in learner's dedicated, shareable Buddy Code."""
    student = get_student(str(student_id))
    value = student.get("buddy_code") if student else None
    return str(value) if value else None

def create_request(requester: str, target: str) -> dict[str, Any]:
    if requester == target: raise ValueError("You cannot add yourself as a buddy.")
    a,b = _pair(requester,target); pair_key = "|".join((a, b)); now=_now()
    with _engine().begin() as conn:
        learner_rows = conn.execute(
            select(students.c.id, students.c.account_id).where(
                and_(
                    students.c.id.in_((requester, target)),
                    students.c.is_active.is_(True),
                )
            )
        ).all()
        learner_accounts = {str(row.id): row.account_id for row in learner_rows}
        if target not in learner_accounts:
            raise ValueError("That Buddy Code is not available.")
        if requester not in learner_accounts:
            raise ValueError("Your child profile is not available.")
        same_parent_account = bool(learner_accounts[requester]) and (
            learner_accounts[requester] == learner_accounts[target]
        )
        existing = conn.execute(select(buddy_requests).where(
            buddy_requests.c.pair_key == pair_key
        )).first()
        if existing:
            d=_row(existing)
            if d["status"] == "active": raise ValueError("You are already Study Buddies.")
            if same_parent_account:
                limit = max_buddies_per_learner()
                if _active_buddy_count(conn, requester) >= limit:
                    raise ValueError("This child has reached the maximum number of Study Buddies.")
                if _active_buddy_count(conn, target) >= limit:
                    raise ValueError("The other child has reached the maximum number of Study Buddies.")
                values = {
                    "requester_parent_approved": True,
                    "target_parent_approved": True,
                    "status": "active",
                    "updated_at": now,
                }
                conn.execute(
                    update(buddy_requests).where(buddy_requests.c.id == d["id"]).values(**values)
                )
                return {**d, **values}
            return d
        limit = max_buddies_per_learner()
        requester_count = _active_buddy_count(conn, requester)
        target_count = _active_buddy_count(conn, target)
        if requester_count >= limit:
            raise ValueError(f"You can have up to {limit} Study Buddies.")
        if target_count >= limit:
            raise ValueError("Your friend has the maximum number of Study Buddies right now.")
        rid=f"sbr_{secrets.token_urlsafe(18)}"
        # Siblings on the same parent account are already inside one family
        # space, so they become buddies straight away.  All other families
        # still need a clear approval from both parents.
        initial_status = "active" if same_parent_account else "pending"
        try:
            conn.execute(insert(buddy_requests).values(id=rid, requester_student_id=requester, target_student_id=target, pair_key=pair_key, requester_parent_approved=same_parent_account, target_parent_approved=same_parent_account, status=initial_status, created_at=now, updated_at=now))
        except IntegrityError:
            existing = conn.execute(select(buddy_requests).where(buddy_requests.c.pair_key == pair_key)).first()
            if existing:
                return _row(existing)
            raise
        return {"id":rid,"status":initial_status}

def parent_requests(account_id: str) -> list[dict[str,Any]]:
    with _engine().begin() as conn:
        rows=conn.execute(select(buddy_requests, students.c.name.label('child_name'), students.c.account_id.label('child_account')).join(students, students.c.id==buddy_requests.c.target_student_id).where(
            (buddy_requests.c.requester_student_id.in_(select(students.c.id).where(students.c.account_id==account_id))) |
            (buddy_requests.c.target_student_id.in_(select(students.c.id).where(students.c.account_id==account_id)))
        ).order_by(buddy_requests.c.created_at.desc())).all()
        out=[]
        for r in rows:
            d=_row(r); d["is_requester_parent"] = d["requester_student_id"] in [x[0] for x in conn.execute(select(students.c.id).where(students.c.account_id==account_id)).all()]
            other_id=d["target_student_id"] if d["is_requester_parent"] else d["requester_student_id"]
            other=conn.execute(select(students.c.name, students.c.year_group).where(students.c.id==other_id)).first()
            d.update({"other_nickname": other.name if other else "Learner", "other_year_group": other.year_group if other else None})
            out.append(d)
        return out

def approve_request(request_id: str, account_id: str, approve: bool) -> dict[str,Any]:
    with _engine().begin() as conn:
        row=conn.execute(select(buddy_requests).where(buddy_requests.c.id==request_id)).first()
        if not row: raise ValueError("Buddy request not found.")
        d=_row(row)
        owned=set(x[0] for x in conn.execute(select(students.c.id).where(students.c.account_id==account_id)).all())
        if d["requester_student_id"] in owned:
            field=buddy_requests.c.requester_parent_approved
        elif d["target_student_id"] in owned:
            field=buddy_requests.c.target_parent_approved
        else: raise PermissionError("This request does not belong to your family.")
        now=_now()
        values={field.key: bool(approve), "updated_at":now}
        if not approve:
            values["status"]="declined"
        else:
            requester_approved = bool(d["requester_parent_approved"] or field.key == "requester_parent_approved")
            target_approved = bool(d["target_parent_approved"] or field.key == "target_parent_approved")
            if requester_approved and target_approved:
                # A declined request can be approved again. Re-check the buddy
                # limit only while it is becoming active, not for an existing
                # active relationship whose parent refreshes the page.
                if d["status"] == "active":
                    values["status"] = "active"
                else:
                    limit = max_buddies_per_learner()
                    if _active_buddy_count(conn, d["requester_student_id"]) >= limit:
                        raise ValueError("This child has reached the maximum number of Study Buddies.")
                    if _active_buddy_count(conn, d["target_student_id"]) >= limit:
                        raise ValueError("The other child has reached the maximum number of Study Buddies.")
                    values["status"]="active"
            else:
                values["status"] = "pending"
        conn.execute(update(buddy_requests).where(buddy_requests.c.id==request_id).values(**values))
        return {**d, **values}

def buddies(student_id: str) -> list[dict[str,Any]]:
    with _engine().begin() as conn:
        # Each half of the UNION uses a compact compound index.  That keeps a
        # learner's buddy screen bounded even when the service has 100k users.
        outgoing = select(
            buddy_requests.c.target_student_id.label("other_student_id"),
            buddy_requests.c.updated_at.label("updated_at"),
        ).where(and_(
            buddy_requests.c.status == "active",
            buddy_requests.c.requester_student_id == student_id,
        ))
        incoming = select(
            buddy_requests.c.requester_student_id.label("other_student_id"),
            buddy_requests.c.updated_at.label("updated_at"),
        ).where(and_(
            buddy_requests.c.status == "active",
            buddy_requests.c.target_student_id == student_id,
        ))
        connections = union_all(outgoing, incoming).subquery()
        rows = conn.execute(
            select(students.c.id, students.c.name, students.c.year_group)
            .join(connections, students.c.id == connections.c.other_student_id)
            .order_by(connections.c.updated_at.desc())
            .limit(max_buddies_per_learner())
        ).all()
    return [
        {"student_id": row.id, "nickname": row.name, "year_group": row.year_group}
        for row in rows
    ]

def is_buddy(a:str,b:str)->bool:
    x,y=_pair(a,b)
    with _engine().begin() as conn:
        return conn.execute(select(buddy_requests.c.id).where(and_(
            buddy_requests.c.status == "active",
            buddy_requests.c.pair_key == "|".join((x, y)),
        ))).first() is not None


def send_emoji_reaction(sender_student_id: str, recipient_student_id: str, emoji_key: str) -> dict[str, Any]:
    """Send one fixed, kind reaction to an approved Study Buddy."""
    sender = str(sender_student_id)
    recipient = str(recipient_student_id)
    emoji = str(emoji_key or "").strip().lower()
    if emoji not in EMOJI_OPTIONS:
        raise ValueError("Choose one of the kind emoji buttons.")
    if not is_buddy(sender, recipient):
        raise PermissionError("You can only send an emoji to an approved Study Buddy.")

    now = _now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with _engine().begin() as conn:
        sent_today = conn.execute(select(func.count()).select_from(buddy_emoji_reactions).where(and_(buddy_emoji_reactions.c.sender_student_id == sender, buddy_emoji_reactions.c.created_at >= day_start))).scalar() or 0
        if sent_today >= max_emojis_per_learner():
            raise ValueError("You have sent lots of kind emojis today. Try again tomorrow.")
        reaction_id = f"sber_{secrets.token_urlsafe(18)}"
        expires_at = now + timedelta(days=EMOJI_REACTION_RETENTION_DAYS)
        conn.execute(insert(buddy_emoji_reactions).values(
            id=reaction_id,
            sender_student_id=sender,
            recipient_student_id=recipient,
            emoji=emoji,
            created_at=now,
            expires_at=expires_at,
        ))
    return {"id": reaction_id, "emoji": emoji, "symbol": EMOJI_OPTIONS[emoji]["emoji"]}


def emoji_reactions_for(student_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent fixed reactions from the learner's current buddies only."""
    student = str(student_id)
    buddy_map = {item["student_id"]: item["nickname"] for item in buddies(student)}
    if not buddy_map:
        return []
    now = _now()
    with _engine().begin() as conn:
        # Cleanup is narrowed to this learner, so an emoji tap never needs a
        # write lock across every family's expired reactions.
        conn.execute(delete(buddy_emoji_reactions).where(and_(
            buddy_emoji_reactions.c.recipient_student_id == student,
            buddy_emoji_reactions.c.expires_at <= now,
        )))
        rows = conn.execute(
            select(buddy_emoji_reactions).where(and_(
                buddy_emoji_reactions.c.recipient_student_id == student,
                buddy_emoji_reactions.c.sender_student_id.in_(list(buddy_map)),
                buddy_emoji_reactions.c.expires_at > now,
            )).order_by(buddy_emoji_reactions.c.created_at.desc()).limit(
                max(1, min(int(limit), 20))
            )
        ).all()
    return [
        {
            "id": str(row.id),
            "sender_student_id": str(row.sender_student_id),
            "sender_nickname": buddy_map.get(str(row.sender_student_id), "Buddy"),
            "emoji": EMOJI_OPTIONS.get(str(row.emoji), {}).get("emoji", "⭐"),
            "label": EMOJI_OPTIONS.get(str(row.emoji), {}).get("label", "Kind emoji"),
        }
        for row in rows
    ]

DAILY_CHALLENGE_SEND_LIMIT = 3
DAILY_CHALLENGE_RECEIVE_LIMIT = 5

def create_challenge(requester:str,target:str,challenge_type:str)->dict[str,Any]:
    if not is_buddy(requester,target): raise PermissionError("You can only challenge an approved Study Buddy.")
    catalog = challenge_catalog_entry(challenge_type)
    if not catalog:
        raise ValueError("Choose one of the ready-made learning challenges.")
    key = str(catalog["key"])
    now=_now(); local_day=now.date()
    with _engine().begin() as conn:
        sent = conn.execute(select(func.count()).select_from(buddy_challenges).where(and_(buddy_challenges.c.requester_student_id==requester, func.date(buddy_challenges.c.created_at)==local_day))).scalar() or 0
        received = conn.execute(select(func.count()).select_from(buddy_challenges).where(and_(buddy_challenges.c.target_student_id==target, func.date(buddy_challenges.c.created_at)==local_day))).scalar() or 0
        if int(sent) >= DAILY_CHALLENGE_SEND_LIMIT:
            raise ValueError("You have sent today's maximum number of buddy challenges. Try again tomorrow.")
        if int(received) >= DAILY_CHALLENGE_RECEIVE_LIMIT:
            raise ValueError("Your buddy has reached today's challenge limit. Try again tomorrow.")
        cid=f"sbc_{secrets.token_urlsafe(18)}"
        conn.execute(insert(buddy_challenges).values(id=cid,requester_student_id=requester,target_student_id=target,challenge_type=key,title=catalog["title"],target_count=catalog["target_count"],xp_reward=catalog["xp"],gift_points_reward=catalog["gift_points"],status="open",created_at=now,verified_activity_count=0))
    return {
        "id": cid,
        "title": catalog["title"],
        "target_count": catalog["target_count"],
        "xp_reward": catalog["xp"],
        "gift_points_reward": catalog["gift_points"],
        "challenge_type": key,
        "practice_subject": catalog["subject"],
        "practice_tab": catalog["practice_tab"],
    }

def challenges_for(student_id:str)->list[dict[str,Any]]:
    with _engine().begin() as conn:
        rows=conn.execute(select(buddy_challenges).where((buddy_challenges.c.target_student_id==student_id)|(buddy_challenges.c.requester_student_id==student_id)).order_by(buddy_challenges.c.created_at.desc()).limit(30)).all()
        challenges=[_row(r) for r in rows]
        learner_ids = {
            str(challenge[student_key])
            for challenge in challenges
            for student_key in ("requester_student_id", "target_student_id")
        }
        names = {
            str(row.id): str(row.name or "Buddy")
            for row in conn.execute(
                select(students.c.id, students.c.name).where(students.c.id.in_(learner_ids))
            ).all()
        } if learner_ids else {}
    for challenge in challenges:
        # These are names for the two learners in this already-approved buddy
        # interaction only; no child directory is exposed.
        catalog = challenge_catalog_entry(challenge["challenge_type"])
        if catalog:
            # These are presentation/navigation details, never the catalogue's
            # internal subject-matching rules.
            challenge["practice_subject"] = catalog["subject"]
            challenge["practice_tab"] = catalog["practice_tab"]
        challenge["requester_nickname"] = (
            "You" if challenge["requester_student_id"] == student_id
            else names.get(str(challenge["requester_student_id"]), "Buddy")
        )
        challenge["target_nickname"] = (
            "You" if challenge["target_student_id"] == student_id
            else names.get(str(challenge["target_student_id"]), "Buddy")
        )
        if challenge["status"] == "open":
            count = _verified_activity_count(challenge["target_student_id"], challenge)
            challenge["verified_activity_count"] = count
            challenge["remaining_activity_count"] = max(0, int(challenge["target_count"]) - count)
            challenge["ready_to_complete"] = count >= int(challenge["target_count"])
    return challenges

def _subject_matches(challenge_type: str, subject: str | None) -> bool:
    """Match only learning subjects that Homework Magic actually supports."""
    return challenge_subject_matches(challenge_type, subject)

def _verified_activity_count(student_id: str, challenge: dict[str, Any]) -> int:
    from .reward_store import get_reward_store

    store = get_reward_store()
    target_count = max(1, int(challenge.get("target_count") or 1))
    count = 0
    with store.engine.begin() as conn:
        rows = conn.execute(
            select(store.events.c.subject)
            .where(
                and_(
                    store.events.c.student_id == student_id,
                    store.events.c.event_type == "checked_activity",
                    store.events.c.created_at >= challenge["created_at"],
                )
            )
            .order_by(store.events.c.created_at.desc())
        ).scalars()
        for subject in rows:
            if not _subject_matches(str(challenge["challenge_type"]), subject):
                continue
            count += 1
            # The UI only needs progress up to the target.  Stopping there
            # avoids reading a child's entire learning history for a one-step
            # challenge.
            if count >= target_count:
                break
    return count


def complete_challenge(
    challenge_id: str,
    student_id: str,
    *,
    completion_source: str = "manual_claim",
) -> dict[str, Any]:
    from .reward_store import get_reward_store

    with _engine().begin() as conn:
        row=conn.execute(select(buddy_challenges).where(buddy_challenges.c.id==challenge_id).with_for_update()).first()
        if not row: raise ValueError("Challenge not found.")
        d=_row(row)
        if d["target_student_id"] != student_id or d["status"] != "open": raise PermissionError("This challenge is not available to you.")
        verified_count = _verified_activity_count(student_id, d)
        if verified_count < int(d["target_count"]):
            remaining = int(d["target_count"]) - verified_count
            raise ValueError(f"Keep learning to finish this challenge. {remaining} more verified activities to go.")
        now=_now()
        result=conn.execute(update(buddy_challenges).where(and_(buddy_challenges.c.id==challenge_id,buddy_challenges.c.status=="open")).values(status="completed",completed_by_student_id=student_id,completed_at=now,verified_activity_count=verified_count,completion_source=completion_source))
        if result.rowcount != 1:
            raise ValueError("This challenge has already been completed.")
    target_reward = get_reward_store().award_custom_event(
        student_id=student_id, xp=d["xp_reward"], gift_points=d["gift_points_reward"],
        source_key=f"study-buddy:{challenge_id}:target", label=d["title"],
    )
    requester_reward = get_reward_store().award_custom_event(
        student_id=d["requester_student_id"], xp=d["xp_reward"], gift_points=d["gift_points_reward"],
        source_key=f"study-buddy:{challenge_id}:requester", label=f"Buddy completed: {d['title']}",
    )
    d.update({"status":"completed","completed_by_student_id":student_id,"verified_activity_count":verified_count,"completion_source":completion_source,"completed_at":now})
    # Only return badges earned by the signed-in learner.  A buddy's badge
    # progress is private even though a small earned-badge summary is shown
    # in the buddy ranking.
    d["new_badges"] = target_reward.get("new_badges", [])
    d["new_certificates"] = target_reward.get("new_certificates", [])
    d["buddy_new_badges_count"] = len(requester_reward.get("new_badges", []))
    d["reward"] = {
        "awarded_xp": int(target_reward.get("xp") or 0),
        "awarded_gift_points": int(target_reward.get("gift_points") or 0),
        "lifetime_xp": int(target_reward.get("lifetime_xp") or 0),
        "gift_points": int(target_reward.get("gift_points") or 0),
        "level": target_reward.get("level"),
        "new_certificates": target_reward.get("new_certificates", []),
        "new_badges": target_reward.get("new_badges", []),
    }
    return d


def complete_challenge_for_verified_activity(
    *,
    challenge_id: str | None,
    student_id: str,
    subject: str,
) -> dict[str, Any] | None:
    """Complete one explicitly selected challenge after a verified activity.

    The challenge ID originates from a child opening the particular Study
    Buddy card.  Requiring that ID means a single reviewed answer cannot
    accidentally complete (or be used to farm rewards from) several older
    challenges that happen to use the same subject.
    """
    requested_id = str(challenge_id or "").strip()
    learner_id = str(student_id or "").strip()
    if not requested_id or not learner_id:
        return None

    with _engine().begin() as conn:
        row = conn.execute(
            select(buddy_challenges).where(
                and_(
                    buddy_challenges.c.id == requested_id,
                    buddy_challenges.c.target_student_id == learner_id,
                    buddy_challenges.c.status == "open",
                )
            )
        ).first()
    challenge = _row(row)
    if not challenge or not _subject_matches(challenge["challenge_type"], subject):
        return None

    try:
        return complete_challenge(
            requested_id,
            learner_id,
            completion_source="verified_activity",
        )
    except (PermissionError, ValueError):
        # The activity is already safely recorded.  A concurrent request or a
        # stale card should not make homework feedback fail for a child.
        return None

def remove_buddy(student_id: str, buddy_id: str) -> dict[str, Any]:
    a, b = _pair(student_id, buddy_id)
    with _engine().begin() as conn:
        row = conn.execute(select(buddy_requests).where(and_(buddy_requests.c.pair_key == f"{a}|{b}", buddy_requests.c.status == "active")).with_for_update()).first()
        if not row:
            raise ValueError("Study Buddy relationship not found.")
        conn.execute(update(buddy_requests).where(buddy_requests.c.id == row.id).values(status="removed", updated_at=_now()))
        return {"removed": True}

def remove_buddy_for_parent(account_id: str, request_id: str) -> dict[str, Any]:
    with _engine().begin() as conn:
        row = conn.execute(select(buddy_requests).where(buddy_requests.c.id == request_id).with_for_update()).first()
        if not row:
            raise ValueError("Study Buddy relationship not found.")
        owned = set(conn.execute(select(students.c.id).where(students.c.account_id == account_id)).scalars())
        d = _row(row)
        if d["requester_student_id"] not in owned and d["target_student_id"] not in owned:
            raise PermissionError("This Study Buddy relationship does not belong to your family.")
        if d["status"] != "active":
            raise ValueError("This Study Buddy relationship is not active.")
        conn.execute(update(buddy_requests).where(buddy_requests.c.id == request_id).values(status="removed", updated_at=_now()))
        return {"removed": True}

def ranking(student_id:str)->dict[str,Any]:
    # Only rank the child's approved buddies plus the child; no global child directory.
    buddy_list = buddies(student_id)
    ids = list(dict.fromkeys([student_id] + [b["student_id"] for b in buddy_list]))
    learner = get_student(student_id) or {}
    names = {
        student_id: str(learner.get("name") or "Learner"),
        **{b["student_id"]: b["nickname"] for b in buddy_list},
    }
    from .reward_store import (
        BADGES,
        LEGACY_BADGE_CODE_ALIASES,
        _local_day_and_week,
        get_reward_store,
    )
    store = get_reward_store()
    now = _now()
    _, week_start = _local_day_and_week(now)
    weekly_totals: dict[str, int] = {sid: 0 for sid in ids}
    lifetime_totals: dict[str, int] = {sid: 0 for sid in ids}
    earned_codes: dict[str, set[str]] = {sid: set() for sid in ids}
    with store.engine.begin() as conn:
        rows = conn.execute(
            select(store.events.c.student_id, func.sum(store.events.c.lifetime_delta).label("xp"))
            .where(and_(store.events.c.student_id.in_(ids), store.events.c.week_start == week_start, store.events.c.lifetime_delta > 0))
            .group_by(store.events.c.student_id)
        ).all()
        for row in rows:
            weekly_totals[str(row.student_id)] = int(row.xp or 0)

        wallet_rows = conn.execute(
            select(store.wallets.c.student_id, store.wallets.c.lifetime_xp)
            .where(store.wallets.c.student_id.in_(ids))
        ).all()
        for row in wallet_rows:
            lifetime_totals[str(row.student_id)] = int(row.lifetime_xp or 0)

        # A ranking only needs badges already earned, not every learner's
        # private progress.  Fetch them in one bounded query rather than
        # calculating badge progress separately for every buddy.
        badge_rows = conn.execute(
            select(store.badges.c.student_id, store.badges.c.badge_code)
            .where(store.badges.c.student_id.in_(ids))
        ).all()
        for row in badge_rows:
            sid = str(row.student_id)
            canonical_code = LEGACY_BADGE_CODE_ALIASES.get(
                str(row.badge_code), str(row.badge_code)
            )
            if sid in earned_codes:
                earned_codes[sid].add(canonical_code)

    def earned_badges_for(sid: str) -> list[dict[str, Any]]:
        codes = earned_codes.get(sid, set())
        return [dict(badge) for badge in BADGES if badge["code"] in codes]

    all_time = []
    for sid in ids:
        earned = earned_badges_for(sid)
        all_time.append({
            "student_id": sid, "nickname": names.get(sid, "Learner"),
            "xp": lifetime_totals.get(sid, 0),
            "badge_count": len(earned),
            "badges": earned,
            "is_current_learner": sid == student_id,
        })
    all_time.sort(key=lambda x: (-x["xp"], x["nickname"].lower()))
    for i, item in enumerate(all_time, 1): item["rank"] = i
    weekly = []
    for sid in ids:
        earned = earned_badges_for(sid)
        weekly.append({
            "student_id": sid, "nickname": names.get(sid, "Learner"),
            "xp": weekly_totals.get(sid, 0),
            "badge_count": len(earned),
            "badges": earned,
            "is_current_learner": sid == student_id,
        })
    weekly.sort(key=lambda x: (-x["xp"], x["nickname"].lower()))
    for i, item in enumerate(weekly, 1): item["rank"] = i
    return {"all_time": all_time, "weekly": weekly, "week_start": week_start}
