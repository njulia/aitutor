"""Persistent administrator exclusions for the public school finder."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Float, MetaData, String, Table, delete, insert, select, update
from sqlalchemy.engine import Engine

from .db import get_engine, normalise_database_url

_metadata = MetaData()
_school_exclusions = Table(
    "school_finder_exclusions",
    _metadata,
    Column("source_id", String(200), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("latitude", Float, nullable=True),
    Column("longitude", Float, nullable=True),
    Column("reason", String(500), nullable=False),
    Column("excluded_by", String(254), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

_school_reports = Table(
    "school_finder_reports",
    _metadata,
    Column("report_id", String(64), primary_key=True),
    Column("source_id", String(200), nullable=False),
    Column("name", String(200), nullable=False),
    Column("latitude", Float, nullable=True),
    Column("longitude", Float, nullable=True),
    Column("reason", String(500), nullable=False),
    Column("status", String(20), nullable=False, default="pending"),
    Column("submitted_by", String(254), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("reviewed_by", String(254), nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column("review_note", String(500), nullable=True),
)
_ENGINE: Engine | None = None
_ENGINE_URL: str | None = None
_LOCK = threading.RLock()

def _database_url() -> str:
    configured = os.getenv("ACCOUNT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return normalise_database_url(configured)
    path = os.getenv("ACCOUNT_DB_PATH", str(Path(__file__).resolve().parents[2] / "data" / "accounts.db"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path}"

def _engine() -> Engine:
    global _ENGINE, _ENGINE_URL
    url = _database_url()
    if _ENGINE is not None and _ENGINE_URL == url:
        return _ENGINE
    with _LOCK:
        if _ENGINE is None or _ENGINE_URL != url:
            _ENGINE = get_engine(url)
            _ENGINE_URL = url
            _metadata.create_all(_ENGINE)
    return _ENGINE

def exclude_school(*, source_id: str, name: str, latitude: float | None,
                   longitude: float | None, reason: str, excluded_by: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    row = {
        "source_id": source_id[:200],
        "name": name[:200],
        "latitude": latitude,
        "longitude": longitude,
        "reason": (reason or "Marked not a secondary school")[:500],
        "excluded_by": excluded_by[:254],
        "created_at": now,
    }
    with _engine().begin() as conn:
        if conn.execute(select(_school_exclusions.c.source_id).where(
            _school_exclusions.c.source_id == row["source_id"]
        )).first():
            conn.execute(delete(_school_exclusions).where(
                _school_exclusions.c.source_id == row["source_id"]
            ))
        conn.execute(insert(_school_exclusions).values(**row))
    return {**row, "created_at": now.isoformat()}

def is_school_excluded(*, source_id: str, name: str, latitude: float | None,
                       longitude: float | None) -> bool:
    with _engine().begin() as conn:
        if conn.execute(select(_school_exclusions.c.source_id).where(
            _school_exclusions.c.source_id == source_id
        )).first():
            return True
        if latitude is None or longitude is None:
            return False
        candidates = conn.execute(select(_school_exclusions).where(
            _school_exclusions.c.name == name
        )).all()
    for candidate in candidates:
        r = candidate._mapping
        if r["latitude"] is None or r["longitude"] is None:
            continue
        if abs(float(r["latitude"]) - float(latitude)) < 0.005 and abs(float(r["longitude"]) - float(longitude)) < 0.008:
            return True
    return False

def list_excluded_schools() -> list[dict[str, Any]]:
    with _engine().begin() as conn:
        rows = conn.execute(select(_school_exclusions).order_by(
            _school_exclusions.c.created_at.desc()
        )).all()
    result = []
    for row in rows:
        item = dict(row._mapping)
        item["created_at"] = item["created_at"].isoformat()
        result.append(item)
    return result

def restore_school(source_id: str) -> None:
    with _engine().begin() as conn:
        conn.execute(delete(_school_exclusions).where(
            _school_exclusions.c.source_id == source_id
        ))


def create_school_report(*, source_id: str, name: str, latitude: float | None,
                         longitude: float | None, reason: str, submitted_by: str | None = None) -> dict[str, Any]:
    report_id = uuid.uuid4().hex
    now = datetime.now(UTC)
    row = {
        "report_id": report_id,
        "source_id": source_id[:200],
        "name": name[:200],
        "latitude": latitude,
        "longitude": longitude,
        "reason": (reason or "This school is not a secondary school")[:500],
        "status": "pending",
        "submitted_by": (submitted_by or "")[:254] or None,
        "created_at": now,
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": None,
    }
    with _engine().begin() as conn:
        duplicate = conn.execute(select(_school_reports.c.report_id).where(
            (_school_reports.c.source_id == row["source_id"]) & (_school_reports.c.status == "pending")
        )).first()
        if duplicate:
            existing = conn.execute(select(_school_reports).where(
                _school_reports.c.report_id == duplicate[0]
            )).first()._mapping
            return {**dict(existing), "created_at": existing["created_at"].isoformat()}
        conn.execute(insert(_school_reports).values(**row))
    return {**row, "created_at": now.isoformat()}

def list_school_reports(status: str | None = None) -> list[dict[str, Any]]:
    with _engine().begin() as conn:
        stmt = select(_school_reports).order_by(_school_reports.c.created_at.desc())
        if status in {"pending", "acknowledged", "rejected"}:
            stmt = stmt.where(_school_reports.c.status == status)
        rows = conn.execute(stmt).all()
    result = []
    for row in rows:
        item = dict(row._mapping)
        for key in ("created_at", "reviewed_at"):
            if item.get(key) is not None:
                item[key] = item[key].isoformat()
        result.append(item)
    return result

def review_school_report(*, report_id: str, action: str, reviewed_by: str, review_note: str = "") -> dict[str, Any]:
    if action not in {"acknowledge", "reject"}:
        raise ValueError("Invalid report action")
    now = datetime.now(UTC)
    with _engine().begin() as conn:
        row = conn.execute(select(_school_reports).where(_school_reports.c.report_id == report_id)).first()
        if not row:
            raise KeyError("School report not found")
        current = dict(row._mapping)
        if current["status"] != "pending":
            return {**current, "created_at": current["created_at"].isoformat(), "reviewed_at": current["reviewed_at"].isoformat() if current.get("reviewed_at") else None}
        status = "acknowledged" if action == "acknowledge" else "rejected"
        conn.execute(update(_school_reports).where(_school_reports.c.report_id == report_id).values(
            status=status, reviewed_by=reviewed_by[:254], reviewed_at=now, review_note=(review_note or "")[:500] or None
        ))
        if action == "acknowledge":
            conn.execute(delete(_school_exclusions).where(_school_exclusions.c.source_id == current["source_id"]))
            conn.execute(insert(_school_exclusions).values(
                source_id=current["source_id"], name=current["name"], latitude=current["latitude"],
                longitude=current["longitude"], reason=current["reason"], excluded_by=reviewed_by[:254], created_at=now
            ))
        current.update(status=status, reviewed_by=reviewed_by[:254], reviewed_at=now, review_note=(review_note or "")[:500] or None)
    current["created_at"] = current["created_at"].isoformat()
    current["reviewed_at"] = now.isoformat()
    return current
