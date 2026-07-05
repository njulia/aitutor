#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
学生学习进度数据库模块

使用 SQLite 存储学生的学习记录、成绩、进度追踪等数据。
支持 UK GDPR 合规：数据本地存储，可删除学生记录。
"""

import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "progress.db")

# 单例连接（线程安全）
_local = threading.local()


def _get_db() -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db() -> None:
    """初始化数据库表结构"""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'Student',
            year_group INTEGER NOT NULL DEFAULT 3,
            age INTEGER NOT NULL DEFAULT 7,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS homework_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            year_group INTEGER NOT NULL DEFAULT 3,
            homework_content TEXT,
            student_answers TEXT,
            score REAL,
            review_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE TABLE IF NOT EXISTS topic_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            questions_attempted INTEGER NOT NULL DEFAULT 0,
            questions_correct INTEGER NOT NULL DEFAULT 0,
            accuracy REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, subject, topic)
        );

        CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            questions_count INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE INDEX IF NOT EXISTS idx_homework_student ON homework_sessions(student_id);
        CREATE INDEX IF NOT EXISTS idx_homework_subject ON homework_sessions(subject);
        CREATE INDEX IF NOT EXISTS idx_topic_student ON topic_progress(student_id);
        CREATE INDEX IF NOT EXISTS idx_practice_student ON practice_sessions(student_id);
    """)
    conn.commit()
    logger.info("[DB] 数据库初始化完成: %s", DB_PATH)


def save_homework_session(
    student_id: str,
    subject: str,
    year_group: int,
    homework_content: str,
    student_answers: str,
    score: float = None,
    review_text: str = None,
) -> int:
    """保存一次作业批改记录

    Returns:
        新记录的 ID
    """
    conn = _get_db()
    # 确保学生存在
    conn.execute(
        "INSERT OR IGNORE INTO students (student_id, year_group) VALUES (?, ?)",
        (student_id, year_group),
    )
    cursor = conn.execute(
        """INSERT INTO homework_sessions
           (student_id, subject, year_group, homework_content, student_answers, score, review_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (student_id, subject, year_group, homework_content, student_answers, score, review_text),
    )
    conn.commit()
    return cursor.lastrowid


def get_progress_summary(student_id: str) -> Dict[str, Any]:
    """获取学生的学习进度汇总"""
    conn = _get_db()

    # 总作业数
    total = conn.execute(
        "SELECT COUNT(*) FROM homework_sessions WHERE student_id = ?",
        (student_id,),
    ).fetchone()[0]

    # 平均分
    avg_score = conn.execute(
        "SELECT AVG(score) FROM homework_sessions WHERE student_id = ? AND score IS NOT NULL",
        (student_id,),
    ).fetchone()[0]

    # 各科成绩
    subject_stats = conn.execute(
        """SELECT subject, COUNT(*) as count, AVG(score) as avg_score
           FROM homework_sessions
           WHERE student_id = ? AND score IS NOT NULL
           GROUP BY subject""",
        (student_id,),
    ).fetchall()

    # 最近一次作业
    latest = conn.execute(
        """SELECT subject, score, created_at FROM homework_sessions
           WHERE student_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (student_id,),
    ).fetchone()

    return {
        "student_id": student_id,
        "total_sessions": total,
        "average_score": round(avg_score, 1) if avg_score else None,
        "subjects": [
            {"subject": row["subject"], "count": row["count"], "avg_score": round(row["avg_score"], 1)}
            for row in subject_stats
        ],
        "latest_session": dict(latest) if latest else None,
    }


def get_score_history(student_id: str, subject: str = None, limit: int = 50) -> List[Dict]:
    """获取学生的成绩历史"""
    conn = _get_db()
    if subject:
        rows = conn.execute(
            """SELECT subject, score, created_at FROM homework_sessions
               WHERE student_id = ? AND subject = ? AND score IS NOT NULL
               ORDER BY created_at DESC LIMIT ?""",
            (student_id, subject, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT subject, score, created_at FROM homework_sessions
               WHERE student_id = ? AND score IS NOT NULL
               ORDER BY created_at DESC LIMIT ?""",
            (student_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic_progress(student_id: str, subject: str = None) -> List[Dict]:
    """获取学生的各知识点掌握情况"""
    conn = _get_db()
    if subject:
        rows = conn.execute(
            """SELECT subject, topic, questions_attempted, questions_correct, accuracy, updated_at
               FROM topic_progress WHERE student_id = ? AND subject = ?
               ORDER BY accuracy ASC""",
            (student_id, subject),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT subject, topic, questions_attempted, questions_correct, accuracy, updated_at
               FROM topic_progress WHERE student_id = ?
               ORDER BY subject, accuracy ASC""",
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---- 管理员接口 ----

def list_all_students(limit: int = 100, offset: int = 0) -> List[Dict]:
    """列出所有学生（管理员用）"""
    conn = _get_db()
    rows = conn.execute(
        """SELECT s.student_id, s.name, s.year_group, s.age, s.created_at, s.is_active,
           COUNT(h.id) as total_sessions,
           AVG(h.score) as avg_score
           FROM students s
           LEFT JOIN homework_sessions h ON s.student_id = h.student_id
           GROUP BY s.student_id
           ORDER BY s.created_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_student_detail(student_id: str) -> Optional[Dict]:
    """获取学生详细信息（管理员用）"""
    conn = _get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not student:
        return None

    result = dict(student)
    result["sessions"] = [
        dict(r) for r in conn.execute(
            """SELECT id, subject, score, created_at FROM homework_sessions
               WHERE student_id = ? ORDER BY created_at DESC LIMIT 20""",
            (student_id,),
        ).fetchall()
    ]
    result["topics"] = get_topic_progress(student_id)
    return result


def update_student(student_id: str, **kwargs) -> bool:
    """更新学生信息（管理员用）"""
    conn = _get_db()
    allowed = {"name", "year_group", "age", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [student_id]
    conn.execute(f"UPDATE students SET {set_clause} WHERE student_id = ?", values)
    conn.commit()
    return conn.total_changes > 0


def delete_student(student_id: str) -> bool:
    """删除学生及所有相关数据（UK GDPR 合规：被遗忘权）"""
    conn = _get_db()
    conn.execute("DELETE FROM topic_progress WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM practice_sessions WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM homework_sessions WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    return conn.total_changes > 0


def get_all_sessions_summary() -> Dict[str, Any]:
    """获取所有作业会话的汇总统计（管理员用）"""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM homework_sessions").fetchone()[0]
    avg_score = conn.execute(
        "SELECT AVG(score) FROM homework_sessions WHERE score IS NOT NULL"
    ).fetchone()[0]
    by_subject = conn.execute(
        """SELECT subject, COUNT(*) as count, AVG(score) as avg_score
           FROM homework_sessions WHERE score IS NOT NULL
           GROUP BY subject ORDER BY count DESC"""
    ).fetchall()
    by_day = conn.execute(
        """SELECT DATE(created_at) as date, COUNT(*) as count
           FROM homework_sessions
           WHERE created_at >= datetime('now', '-30 days')
           GROUP BY DATE(created_at) ORDER BY date"""
    ).fetchall()
    return {
        "total_sessions": total,
        "average_score": round(avg_score, 1) if avg_score else None,
        "by_subject": [dict(r) for r in by_subject],
        "daily_activity": [dict(r) for r in by_day],
    }


# 初始化时创建表
init_db()
