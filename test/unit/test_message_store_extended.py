import os
import sqlite3
import pytest
from pathlib import Path
from datetime import UTC, datetime, timedelta
from src.webapp.message_store import MessageStore, _iso

def test_migration_and_legacy_column(tmp_path: Path):
    db_path = tmp_path / "legacy_messages.db"
    
    # 1. Create a legacy database schema
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE support_messages (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            contact_email TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            access_token TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.close()
    
    # 2. Initialize MessageStore with this legacy DB
    store = MessageStore(str(tmp_path), db_path=str(db_path))
    
    # 3. Verify columns were added
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(support_messages)")
    columns = {row["name"] for row in cursor.fetchall()}
    assert "category" in columns
    assert "access_token_hash" in columns
    assert "expires_at" in columns
    assert "user_read_at" in columns
    assert "admin_read_at" in columns
    assert "access_token" in columns  # Should still be there
    conn.close()
    
    # 4. Verify we can create a message even with the NOT NULL access_token column
    created, token = store.create_message(
        owner_id="test-owner",
        contact_email="test@example.com",
        category="technical",
        subject="Migration test",
        message="This should work with legacy column."
    )
    assert created["id"].startswith("msg_")
    assert token is not None
    
    # 5. Verify the data in the DB
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM support_messages WHERE id = ?", (created["id"],)).fetchone()
    assert row["access_token"] == "" # Our fix sets it to empty string
    assert row["category"] == "technical"
    conn.close()

def test_purge_expired(tmp_path: Path):
    store = MessageStore(str(tmp_path), db_path=str(tmp_path / "purge.db"))
    
    # Create an expired message manually
    now = datetime.now(UTC)
    expired_at = _iso(now - timedelta(days=1))
    
    with store._connection() as conn:
        conn.execute(
            """INSERT INTO support_messages 
               (id, owner_id, contact_email, category, subject, message, status, access_token_hash, created_at, updated_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("msg_expired", "owner1", "c@e.com", "general", "Sub", "Msg", "open", "hash", _iso(now), _iso(now), expired_at)
        )
    
    # Create a non-expired message
    store.create_message(
        owner_id="owner1",
        contact_email="c@e.com",
        category="general",
        subject="Not expired",
        message="Msg"
    )
    
    assert store.purge_expired() == 1
    
    with store._connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM support_messages").fetchone()[0]
        assert count == 1

def test_delete_for_owners(tmp_path: Path):
    store = MessageStore(str(tmp_path), db_path=str(tmp_path / "delete.db"))
    
    store.create_message(owner_id="owner1", contact_email="c1@e.com", category="general", subject="S1", message="M1")
    store.create_message(owner_id="owner2", contact_email="c2@e.com", category="general", subject="S2", message="M2")
    store.create_message(owner_id="owner1", contact_email="c1@e.com", category="general", subject="S3", message="M3")
    
    count = store.delete_for_owners(["owner1"])
    assert count == 2
    
    with store._connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM support_messages").fetchone()[0]
        assert count == 1

def test_list_admin_filters(tmp_path: Path):
    store = MessageStore(str(tmp_path), db_path=str(tmp_path / "admin.db"))
    
    store.create_message(owner_id="o1", contact_email="a@example.com", category="billing", subject="Billing issue", message="M1")
    store.create_message(owner_id="o2", contact_email="b@example.com", category="technical", subject="Tech help", message="M2")
    
    # Filter by category
    billing = store.list_admin(category="billing")
    assert len(billing) == 1
    assert billing[0]["category"] == "billing"
    
    # Search
    search_tech = store.list_admin(search="tech")
    assert len(search_tech) == 1
    assert "Tech" in search_tech[0]["subject"]
    
    search_email = store.list_admin(search="example.com")
    assert len(search_email) == 2
