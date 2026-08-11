"""Small, child-safe virtual capybara store for the Homework Magic playtime page.

The pet is deliberately separate from the reward wallet: caring for a pet never
changes XP or Gift Points. A pet only exists to make the daily learning habit
feel playful.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, and_, insert, select, update
from sqlalchemy.engine import Engine

from .db import get_engine, normalise_database_url

FRUITS: dict[str, dict[str, str]] = {
    "apple": {"label": "Apple", "emoji": "🍎"},
    "strawberry": {"label": "Strawberry", "emoji": "🍓"},
    "banana": {"label": "Banana", "emoji": "🍌"},
    "orange": {"label": "Orange", "emoji": "🍊"},
    "watermelon": {"label": "Watermelon", "emoji": "🍉"},
    "blueberry": {"label": "Blueberry", "emoji": "🫐"},
    "cherry": {"label": "Cherries", "emoji": "🍒"},
}

ACTIVITIES = {
    "play": {"label": "Play", "emoji": "🎾", "care": 3},
    "food": {"label": "Food", "emoji": "🥕", "care": 2},
    "poo": {"label": "Clean up", "emoji": "🧹", "care": 2},
    "sleep": {"label": "Sleep", "emoji": "💤", "care": 1},
}

GROWTH_STAGES = (
    (0, "Baby Capy", "Tiny paws, huge cuddles!"),
    (8, "Little Capy", "Bouncy, bright and very cute!"),
    (22, "Happy Capy", "Growing stronger with gentle care!"),
    (45, "Big Kid Capy", "A cheerful friend with a fluffy smile!"),
    (80, "Super Capy", "Super cute and full of happy energy!"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("REWARD_TIMEZONE", "Europe/London"))
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _local_day(now: datetime | None = None) -> str:
    return (now or _now()).astimezone(_timezone()).date().isoformat()


def _clean(value: Any, maximum: int = 80) -> str:
    return str(value or "").strip()[:maximum]


def growth_for(care_points: int) -> dict[str, Any]:
    points = max(0, int(care_points or 0))
    stage = 1
    name, copy = GROWTH_STAGES[0][1:]
    for number, stage_name, stage_copy in GROWTH_STAGES:
        if points >= number:
            stage = GROWTH_STAGES.index((number, stage_name, stage_copy)) + 1
            name, copy = stage_name, stage_copy
    next_threshold = next((item[0] for item in GROWTH_STAGES if item[0] > points), None)
    return {
        "stage": stage,
        "name": name,
        "copy": copy,
        "care_points": points,
        "next_care_points": next_threshold,
        "cute": True,
    }


class CapybaraStore:
    """Persistent pet state keyed strictly by account + learner."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = normalise_database_url(
            database_url
            or os.getenv("REWARD_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or f"sqlite+pysqlite:///{os.path.join(os.path.dirname(__file__), '../../data/rewards.db')}"
        )
        self.engine: Engine = get_engine(self.database_url)
        self.metadata = MetaData()
        self.pets = Table(
            "reward_capybara_pets",
            self.metadata,
            Column("student_id", String(80), primary_key=True),
            Column("account_id", String(80), nullable=False, index=True),
            Column("generation", Integer, nullable=False, default=1),
            Column("care_points", Integer, nullable=False, default=0),
            Column("fruit", String(30), nullable=False, default="apple"),
            Column("alive", Integer, nullable=False, default=1),
            Column("last_goal_completed_day", String(10), nullable=True),
            Column("last_play_day", String(10), nullable=True),
            Column("last_activity", String(20), nullable=True),
            Column("deceased_at", DateTime(timezone=True), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        self.metadata.create_all(self.engine)
        self._lock = threading.RLock()

    def initialise(self) -> None:
        self.metadata.create_all(self.engine)

    def _ensure(self, conn, account_id: str, student_id: str) -> Mapping[str, Any]:
        row = conn.execute(
            select(self.pets).where(
                and_(self.pets.c.account_id == account_id, self.pets.c.student_id == student_id)
            )
        ).first()
        if row:
            return row._mapping
        now = _now()
        conn.execute(
            insert(self.pets).values(
                student_id=student_id,
                account_id=account_id,
                generation=1,
                care_points=0,
                fruit="apple",
                alive=1,
                created_at=now,
                updated_at=now,
            )
        )
        return conn.execute(
            select(self.pets).where(
                and_(self.pets.c.account_id == account_id, self.pets.c.student_id == student_id)
            )
        ).first()._mapping

    def _mark_missed_play(self, conn, row: Mapping[str, Any], today: str) -> Mapping[str, Any]:
        last_goal = row.get("last_goal_completed_day")
        last_play = row.get("last_play_day")
        if row.get("alive") and last_goal and last_goal < today and last_play != last_goal:
            now = _now()
            conn.execute(
                update(self.pets)
                .where(self.pets.c.student_id == row["student_id"])
                .values(alive=0, deceased_at=now, updated_at=now)
            )
            return conn.execute(select(self.pets).where(self.pets.c.student_id == row["student_id"])).first()._mapping
        return row

    def status(
        self,
        *,
        account_id: str,
        student_id: str,
        daily_goal_completed: bool,
        today: str | None = None,
    ) -> dict[str, Any]:
        account = _clean(account_id)
        learner = _clean(student_id)
        day = today or _local_day()
        with self._lock, self.engine.begin() as conn:
            row = self._ensure(conn, account, learner)
            row = self._mark_missed_play(conn, row, day)
            if row["alive"] and daily_goal_completed and row.get("last_goal_completed_day") != day:
                conn.execute(
                    update(self.pets)
                    .where(and_(self.pets.c.account_id == account, self.pets.c.student_id == learner))
                    .values(last_goal_completed_day=day, updated_at=_now())
                )
                row = conn.execute(
                    select(self.pets).where(and_(self.pets.c.account_id == account, self.pets.c.student_id == learner))
                ).first()._mapping
            return self._payload(row, day, daily_goal_completed)

    def adopt_new_baby(self, *, account_id: str, student_id: str, daily_goal_completed: bool, today: str | None = None) -> dict[str, Any]:
        account = _clean(account_id)
        learner = _clean(student_id)
        day = today or _local_day()
        with self._lock, self.engine.begin() as conn:
            row = self._ensure(conn, account, learner)
            generation = int(row.get("generation") or 1) + (1 if not row.get("alive") else 0)
            if row.get("alive"):
                return self._payload(row, day, daily_goal_completed)
            conn.execute(
                update(self.pets)
                .where(and_(self.pets.c.account_id == account, self.pets.c.student_id == learner))
                .values(
                    generation=generation,
                    care_points=0,
                    fruit="apple",
                    alive=1,
                    last_goal_completed_day=day if daily_goal_completed else None,
                    last_play_day=None,
                    last_activity=None,
                    deceased_at=None,
                    updated_at=_now(),
                )
            )
            row = conn.execute(select(self.pets).where(self.pets.c.student_id == learner)).first()._mapping
            return self._payload(row, day, daily_goal_completed)

    def set_fruit(self, *, account_id: str, student_id: str, fruit: str, daily_goal_completed: bool, today: str | None = None) -> dict[str, Any]:
        fruit_key = _clean(fruit, 30).lower()
        if fruit_key not in FRUITS:
            raise ValueError("Choose one of the available fruits.")
        account = _clean(account_id)
        learner = _clean(student_id)
        day = today or _local_day()
        with self._lock, self.engine.begin() as conn:
            row = self._ensure(conn, account, learner)
            row = self._mark_missed_play(conn, row, day)
            if not row["alive"]:
                return self._payload(row, day, daily_goal_completed)
            conn.execute(
                update(self.pets)
                .where(and_(self.pets.c.account_id == account, self.pets.c.student_id == learner))
                .values(fruit=fruit_key, last_goal_completed_day=day, updated_at=_now())
            )
            row = conn.execute(select(self.pets).where(self.pets.c.student_id == learner)).first()._mapping
            return self._payload(row, day, daily_goal_completed)

    def act(self, *, account_id: str, student_id: str, activity: str, daily_goal_completed: bool, today: str | None = None) -> dict[str, Any]:
        activity_key = _clean(activity, 20).lower()
        if activity_key not in ACTIVITIES:
            raise ValueError("Choose play, food, clean up or sleep.")
        account = _clean(account_id)
        learner = _clean(student_id)
        day = today or _local_day()
        with self._lock, self.engine.begin() as conn:
            row = self._ensure(conn, account, learner)
            row = self._mark_missed_play(conn, row, day)
            if not row["alive"]:
                return self._payload(row, day, daily_goal_completed)
            if not daily_goal_completed:
                raise PermissionError("Finish today's Daily Goal before playtime.")
            values = {
                "care_points": int(row.get("care_points") or 0) + int(ACTIVITIES[activity_key]["care"]),
                "last_goal_completed_day": day,
                "last_activity": activity_key,
                "updated_at": _now(),
            }
            if activity_key == "play":
                values["last_play_day"] = day
            conn.execute(
                update(self.pets)
                .where(and_(self.pets.c.account_id == account, self.pets.c.student_id == learner))
                .values(**values)
            )
            row = conn.execute(select(self.pets).where(self.pets.c.student_id == learner)).first()._mapping
            return self._payload(row, day, daily_goal_completed)

    def _payload(self, row: Mapping[str, Any], today: str, goal_completed: bool) -> dict[str, Any]:
        alive = bool(row.get("alive"))
        last_goal = row.get("last_goal_completed_day")
        played_today = row.get("last_play_day") == today
        return {
            "generation": int(row.get("generation") or 1),
            "alive": alive,
            "fruit": row.get("fruit") or "apple",
            "fruit_info": FRUITS.get(row.get("fruit") or "apple", FRUITS["apple"]),
            "growth": growth_for(int(row.get("care_points") or 0)),
            "last_activity": row.get("last_activity"),
            "played_today": played_today,
            "care_due_today": bool(goal_completed) and not played_today,
            "daily_goal_completed": bool(goal_completed),
            "last_goal_completed_day": last_goal,
            "deceased_at": row.get("deceased_at").isoformat() if row.get("deceased_at") else None,
            "activities": {
                key: {"label": value["label"], "emoji": value["emoji"]}
                for key, value in ACTIVITIES.items()
            },
            "fruits": FRUITS,
            "no_xp_change": True,
            "no_gift_points_change": True,
        }

    def delete_learner(self, *, account_id: str, student_id: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                self.pets.delete().where(and_(self.pets.c.account_id == _clean(account_id), self.pets.c.student_id == _clean(student_id)))
            )
            return int(result.rowcount or 0)

    def delete_account(self, *, account_id: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(self.pets.delete().where(self.pets.c.account_id == _clean(account_id)))
            return int(result.rowcount or 0)


_STORE: CapybaraStore | None = None
_STORE_LOCK = threading.Lock()


def get_capybara_store() -> CapybaraStore:
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = CapybaraStore()
    return _STORE
