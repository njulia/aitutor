"""Explicit, idempotent Study Buddy database migrations.

Study Buddy uses the existing account database.  Migrations are versioned so
Cloud Run instances do not depend on SQLAlchemy ``create_all()`` for upgrades.
"""
from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, inspect, insert, select, text, update
from sqlalchemy.engine import Engine

from .account_store import _engine

MIGRATION_VERSION = 10


def _migration_table(metadata: MetaData) -> Table:
    return Table(
        "study_buddy_schema_migrations",
        metadata,
        Column("version", Integer, primary_key=True),
        Column("applied_at", DateTime(timezone=True), nullable=False),
    )


def _column_names(engine: Engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _add_column(engine: Engine, table_name: str, column_name: str, sql_type: str) -> None:
    if column_name in _column_names(engine, table_name):
        return
    # Column names/types here are fixed application constants, not user input.
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}"))


def run_study_buddy_migrations() -> None:
    engine = _engine()
    metadata = MetaData()
    migrations = _migration_table(metadata)
    metadata.create_all(engine, tables=[migrations])

    with engine.begin() as conn:
        applied = {int(v) for v in conn.execute(select(migrations.c.version)).scalars()}

    # v1: create the initial Study Buddy tables.  Importing the table metadata
    # here avoids circular imports while still making this migration explicit.
    from .study_buddy_store import buddy_requests, buddy_challenges
    buddy_requests.metadata.create_all(engine, tables=[buddy_requests, buddy_challenges])
    if 1 not in applied:
        with engine.begin() as conn:
            conn.execute(insert(migrations).values(version=1, applied_at=datetime.now(UTC)))

    # v2: make the learner pair canonical and persist server-side verification
    # details for completed challenges. This can touch every old request, so it
    # must only run once rather than at every application start.
    if 2 not in applied:
        _add_column(engine, "study_buddy_requests", "pair_key", "VARCHAR(161)")
        _add_column(engine, "study_buddy_challenges", "verified_activity_count", "INTEGER DEFAULT 0")
        _add_column(engine, "study_buddy_challenges", "completion_source", "VARCHAR(40)")

        with engine.begin() as conn:
            rows = conn.execute(select(buddy_requests.c.id, buddy_requests.c.requester_student_id, buddy_requests.c.target_student_id, buddy_requests.c.status, buddy_requests.c.created_at).order_by(buddy_requests.c.created_at.desc())).all()
            seen: set[str] = set()
            for row in rows:
                pair_key = "|".join(sorted((str(row.requester_student_id), str(row.target_student_id))))
                if pair_key in seen:
                    # Phase 1 did not have an unordered-pair constraint. Keep the
                    # newest row and retire older duplicates before adding the
                    # database-level unique index.
                    legacy_key = f"legacy:{row.id}"[:161]
                    conn.execute(update(buddy_requests).where(buddy_requests.c.id == row.id).values(pair_key=legacy_key, status="removed", updated_at=datetime.now(UTC)))
                else:
                    seen.add(pair_key)
                    conn.execute(update(buddy_requests).where(buddy_requests.c.id == row.id).values(pair_key=pair_key))

            # A unique index prevents the same unordered pair being inserted twice,
            # including the race where A->B and B->A arrive together.
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_study_buddy_pair_key ON study_buddy_requests (pair_key)"))
            except Exception:
                # Existing duplicate legacy rows are handled by create_request's
                # application-level lookup; do not prevent the app from starting.
                pass
            conn.execute(insert(migrations).values(version=2, applied_at=datetime.now(UTC)))

    # v3: bounded, fixed emoji reactions and compound indexes for a much
    # larger buddy population. The indexes keep the normal friend lookup and
    # incoming-reaction screen independent of the total number of learners.
    from .study_buddy_store import buddy_emoji_reactions
    buddy_emoji_reactions.metadata.create_all(engine, tables=[buddy_emoji_reactions])
    if 3 not in applied:
        with engine.begin() as conn:
            for statement in (
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_requester_status ON study_buddy_requests (requester_student_id, status)",
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_target_status ON study_buddy_requests (target_student_id, status)",
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_emoji_recipient_created ON study_buddy_emoji_reactions (recipient_student_id, created_at)",
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_emoji_expires ON study_buddy_emoji_reactions (expires_at)",
            ):
                conn.execute(text(statement))
            conn.execute(insert(migrations).values(version=3, applied_at=datetime.now(UTC)))

    # v4: one narrow index for each hot, bounded emoji operation.  Existing
    # installations that already applied v3 still receive these indexes.
    if 4 not in applied:
        with engine.begin() as conn:
            for statement in (
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_emoji_sender_created ON study_buddy_emoji_reactions (sender_student_id, created_at)",
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_emoji_recipient_expires ON study_buddy_emoji_reactions (recipient_student_id, expires_at)",
            ):
                conn.execute(text(statement))
            conn.execute(insert(migrations).values(version=4, applied_at=datetime.now(UTC)))

    # v5: a singleton settings row allows an administrator to change the
    # connection cap without changing application code.  No value is seeded:
    # the store supplies the safe default of 20 until an admin saves one.
    from .study_buddy_store import study_buddy_settings
    study_buddy_settings.metadata.create_all(engine, tables=[study_buddy_settings])
    if 5 not in applied:
        with engine.begin() as conn:
            conn.execute(insert(migrations).values(version=5, applied_at=datetime.now(UTC)))

    # v6: Study Buddy challenges now mean one completed, verified subject
    # activity.  Existing open cards used 10/15 activities, which made the
    # new child-facing wording misleading.  Do not rewrite completed history
    # or any future non-legacy challenge definitions.
    if 6 not in applied:
        from .study_buddy_challenge_catalog import legacy_open_target_count_types

        with engine.begin() as conn:
            conn.execute(
                update(buddy_challenges)
                .where(buddy_challenges.c.status == "open")
                .where(
                    buddy_challenges.c.challenge_type.in_(
                        tuple(legacy_open_target_count_types())
                    )
                )
                .where(buddy_challenges.c.target_count > 1)
                .values(target_count=1)
            )
            conn.execute(insert(migrations).values(version=6, applied_at=datetime.now(UTC)))

    # v7: make the child-safe daily emoji sending limit configurable from the
    # admin dashboard. Existing installations keep the established default.
    if 7 not in applied:
        _add_column(
            engine,
            "study_buddy_settings",
            "max_emojis_per_learner",
            "INTEGER NOT NULL DEFAULT 40",
        )
        with engine.begin() as conn:
            conn.execute(insert(migrations).values(version=7, applied_at=datetime.now(UTC)))

    # v8: children under the same parent account are siblings in one family
    # space, so a pending buddy request between them does not need a parent to
    # approve it twice. Other families remain pending until both approve.
    if 8 not in applied:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE study_buddy_requests
                SET requester_parent_approved = TRUE,
                    target_parent_approved = TRUE,
                    status = 'active',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'pending'
                  AND EXISTS (
                    SELECT 1
                    FROM students AS requester
                    JOIN students AS target
                      ON requester.id = study_buddy_requests.requester_student_id
                     AND target.id = study_buddy_requests.target_student_id
                    WHERE requester.account_id = target.account_id
                      AND requester.account_id IS NOT NULL
                  )
            """))
            conn.execute(insert(migrations).values(version=8, applied_at=datetime.now(UTC)))

    # v9: a bounded, one-time celebration queue tells the child who sent a
    # challenge that their approved buddy completed it and that both rewards
    # were added. It contains no free text or child directory data.
    from .study_buddy_store import buddy_challenge_notifications
    buddy_challenge_notifications.metadata.create_all(
        engine, tables=[buddy_challenge_notifications]
    )
    if 9 not in applied:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_study_buddy_notice_recipient_seen_created "
                "ON study_buddy_challenge_notifications (recipient_student_id, seen_at, created_at)"
            ))
            conn.execute(insert(migrations).values(version=9, applied_at=datetime.now(UTC)))

    # v10: record the final shared bonus, which may be higher for a more
    # accurate checked activity. Existing completed challenges fall back to
    # their original reward fields until they are viewed.
    if 10 not in applied:
        _add_column(engine, "study_buddy_challenges", "awarded_xp", "INTEGER")
        _add_column(engine, "study_buddy_challenges", "awarded_gift_points", "INTEGER")
        with engine.begin() as conn:
            conn.execute(insert(migrations).values(version=10, applied_at=datetime.now(UTC)))
