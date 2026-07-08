#!/usr/bin/env python3
# Simple persistent embedding cache using sqlite and pickle
import os
import sqlite3
import threading
import hashlib
import pickle
from typing import List, Callable, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(PROJECT_ROOT, "data_archive")
os.makedirs(DB_DIR, exist_ok=True)
CACHE_DB = os.path.join(DB_DIR, "embedding_cache.db")

_local = threading.local()

def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(CACHE_DB, check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_cache():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS embeddings (
            key TEXT PRIMARY KEY,
            vector BLOB,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_embeddings_key ON embeddings(key);
    """)
    conn.commit()


init_cache()


def _key_for(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def get_embeddings(texts: List[str], embed_fn: Callable[[List[str]], List[Any]]) -> List[Any]:
    """Return embeddings for texts using cache. embed_fn is called only for missing keys."""
    conn = _get_conn()
    keys = [_key_for(t) for t in texts]
    results = [None] * len(texts)

    # fetch existing
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(f"SELECT key, vector FROM embeddings WHERE key IN ({placeholders})", keys).fetchall() if keys else []
    cache_map = {r['key']: pickle.loads(r['vector']) for r in rows}

    missing_texts = []
    missing_indices = []
    for i, k in enumerate(keys):
        if k in cache_map:
            results[i] = cache_map[k]
        else:
            missing_texts.append(texts[i])
            missing_indices.append(i)

    if missing_texts:
        # compute embeddings for missing
        computed = embed_fn(missing_texts)
        # store into DB
        to_insert = []
        for idx, vec in zip(missing_indices, computed):
            results[idx] = vec
            to_insert.append((keys[idx], sqlite3.Binary(pickle.dumps(vec))))
        try:
            conn.executemany("INSERT OR REPLACE INTO embeddings (key, vector) VALUES (?, ?)", to_insert)
            conn.commit()
        except Exception:
            # best-effort cache write
            pass

    return results


# ---- Cache maintenance utilities ----
from datetime import datetime, timedelta

def get_stats() -> dict:
    """Return basic stats about the embedding cache."""
    conn = _get_conn()
    cur = conn.execute("SELECT COUNT(*) as cnt, MIN(created_at) as oldest, MAX(created_at) as newest FROM embeddings")
    row = cur.fetchone()
    count = row["cnt"] if row else 0
    oldest = row["oldest"] if row else None
    newest = row["newest"] if row else None
    try:
        size = os.path.getsize(CACHE_DB)
    except Exception:
        size = None
    return {
        "count": count,
        "oldest": oldest,
        "newest": newest,
        "db_path": CACHE_DB,
        "db_size_bytes": size,
    }


def cleanup_older_than(days: int) -> int:
    """Delete embeddings older than specified number of days. Returns number of rows removed."""
    if days is None or days <= 0:
        return 0
    conn = _get_conn()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cur = conn.execute("SELECT COUNT(*) FROM embeddings WHERE created_at < ?", (cutoff,))
    to_remove = cur.fetchone()[0]
    conn.execute("DELETE FROM embeddings WHERE created_at < ?", (cutoff,))
    conn.commit()
    return to_remove


def ensure_max_rows(max_rows: int) -> int:
    """Ensure the embeddings table has at most max_rows rows. Trims oldest entries. Returns number of rows removed."""
    if not max_rows or max_rows <= 0:
        return 0
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) as cnt FROM embeddings").fetchone()[0]
    if total <= max_rows:
        return 0
    remove_count = total - max_rows
    # Delete the oldest remove_count rows
    conn.execute(
        "DELETE FROM embeddings WHERE key IN (SELECT key FROM embeddings ORDER BY created_at ASC LIMIT ?)",
        (remove_count,),
    )
    conn.commit()
    return remove_count
