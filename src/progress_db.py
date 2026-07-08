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
import uuid
from datetime import datetime, timedelta
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

        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            customer_email TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            product_name TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            is_dev INTEGER NOT NULL DEFAULT 0
        );

        -- Users table for persistent login
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            operation TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            latency_ms REAL,
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            prompt_text TEXT,
            response_text TEXT,
            rag_context TEXT,
            student_id TEXT,
            subject TEXT,
            homework_doc_id TEXT,
            langfuse_trace_id TEXT,
            metadata_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_homework_student ON homework_sessions(student_id);
        CREATE INDEX IF NOT EXISTS idx_homework_subject ON homework_sessions(subject);
        CREATE INDEX IF NOT EXISTS idx_topic_student ON topic_progress(student_id);
        CREATE INDEX IF NOT EXISTS idx_practice_student ON practice_sessions(student_id);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(customer_email);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
        CREATE INDEX IF NOT EXISTS idx_ai_requests_timestamp ON ai_requests(timestamp);
        CREATE INDEX IF NOT EXISTS idx_ai_requests_provider ON ai_requests(provider);
        CREATE INDEX IF NOT EXISTS idx_ai_requests_status ON ai_requests(status);
        CREATE INDEX IF NOT EXISTS idx_ai_requests_student ON ai_requests(student_id);

        -- Additional performance indexes
        CREATE INDEX IF NOT EXISTS idx_students_created_at ON students(created_at);
        CREATE INDEX IF NOT EXISTS idx_homework_created_at ON homework_sessions(created_at);
        CREATE INDEX IF NOT EXISTS idx_students_year_group ON students(year_group);
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


def get_daily_goal_stats(student_id: str, daily_goal: int = 1) -> Dict[str, Any]:
    """获取学生每日目标完成情况统计

    Args:
        student_id: 学生ID
        daily_goal: 每天目标完成作业数，默认1

    Returns:
        包含每日目标完成率、活跃天数等统计
    """
    conn = _get_db()

    # 按天统计作业完成数
    daily_counts = conn.execute(
        """SELECT DATE(created_at) as date, COUNT(*) as count
           FROM homework_sessions
           WHERE student_id = ?
           GROUP BY DATE(created_at)
           ORDER BY date""",
        (student_id,),
    ).fetchall()

    if not daily_counts:
        return {
            "total_active_days": 0,
            "total_days_with_data": 0,
            "goal_met_days": 0,
            "daily_goal_rate": 0,
            "daily_breakdown": [],
        }

    total_active_days = len(daily_counts)
    goal_met_days = sum(1 for d in daily_counts if d["count"] >= daily_goal)

    # 计算从首次活动到今天的天数（含不活跃日）
    first_date_str = daily_counts[0]["date"]
    last_date_str = daily_counts[-1]["date"]
    first_date = datetime.strptime(first_date_str, "%Y-%m-%d")
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
    total_span_days = (last_date - first_date).days + 1

    # 每日明细
    daily_breakdown = [
        {"date": d["date"], "count": d["count"], "goal_met": d["count"] >= daily_goal}
        for d in daily_counts
    ]

    return {
        "total_active_days": total_active_days,
        "total_span_days": total_span_days,
        "goal_met_days": goal_met_days,
        "daily_goal_rate": round(goal_met_days / total_active_days * 100, 1) if total_active_days else 0,
        "daily_goal": daily_goal,
        "daily_breakdown": daily_breakdown,
    }


def get_streak_info(student_id: str) -> Dict[str, Any]:
    """计算学生的连续学习天数（当前连续 & 历史最长）"""
    conn = _get_db()

    daily_counts = conn.execute(
        """SELECT DATE(created_at) as date
           FROM homework_sessions
           WHERE student_id = ?
           GROUP BY DATE(created_at)
           ORDER BY date""",
        (student_id,),
    ).fetchall()

    if not daily_counts:
        return {"current_streak": 0, "best_streak": 0}

    dates = sorted(
        datetime.strptime(d["date"], "%Y-%m-%d").date()
        for d in daily_counts
    )

    # 计算连续天数
    best_streak = 1
    current_streak = 1
    running_streak = 1

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            running_streak += 1
        else:
            running_streak = 1
        best_streak = max(best_streak, running_streak)

    # 当前连续：从今天或昨天往回数
    from datetime import date as date_type
    today = date_type.today()
    if dates[-1] == today or (today - dates[-1]).days == 1:
        current_streak = 1
        for i in range(len(dates) - 1, 0, -1):
            if (dates[i] - dates[i - 1]).days == 1:
                current_streak += 1
            else:
                break
    else:
        current_streak = 0

    return {"current_streak": current_streak, "best_streak": best_streak}


def get_accuracy_rate(student_id: str) -> Dict[str, Any]:
    """获取学生的综合正确率统计

    Returns:
        包含总正确率、各科正确率、正确率趋势
    """
    conn = _get_db()

    # 从 topic_progress 表获取综合正确率
    topic_stats = conn.execute(
        """SELECT SUM(questions_attempted) as total_q,
                  SUM(questions_correct) as total_correct
           FROM topic_progress
           WHERE student_id = ?""",
        (student_id,),
    ).fetchone()

    total_q = topic_stats["total_q"] or 0
    total_correct = topic_stats["total_correct"] or 0
    overall_accuracy = round(total_correct / total_q * 100, 1) if total_q > 0 else None

    # 各科正确率
    subject_accuracy = conn.execute(
        """SELECT subject,
                  SUM(questions_attempted) as total_q,
                  SUM(questions_correct) as total_correct
           FROM topic_progress
           WHERE student_id = ?
           GROUP BY subject""",
        (student_id,),
    ).fetchall()

    by_subject = []
    for row in subject_accuracy:
        q = row["total_q"] or 0
        c = row["total_correct"] or 0
        by_subject.append({
            "subject": row["subject"],
            "accuracy": round(c / q * 100, 1) if q > 0 else 0,
            "questions_attempted": q,
            "questions_correct": c,
        })

    # 按作业会话计算正确率趋势（最近10次）
    score_trend = conn.execute(
        """SELECT subject, score, created_at
           FROM homework_sessions
           WHERE student_id = ? AND score IS NOT NULL
           ORDER BY created_at DESC
           LIMIT 10""",
        (student_id,),
    ).fetchall()

    trend = []
    for s in reversed(list(score_trend)):
        pct = round(s["score"] * 10, 1) if s["score"] is not None else 0
        trend.append({
            "subject": s["subject"],
            "accuracy": pct,
            "created_at": s["created_at"],
        })

    return {
        "overall_accuracy": overall_accuracy,
        "total_questions": total_q,
        "total_correct": total_correct,
        "by_subject": by_subject,
        "accuracy_trend": trend,
    }


def generate_progress_feedback(
    total_sessions: int,
    avg_accuracy: float,
    current_streak: int,
    daily_goal_rate: float,
) -> Dict[str, str]:
    """根据学生数据生成积极鼓励性的反馈文案

    Returns:
        包含标题、正文、小贴士的字典
    """
    # 总体评价
    if total_sessions == 0:
        return {
            "headline": "Ready to Begin Your Journey!",
            "message": "Every great achievement starts with a single step. Complete your first homework to start tracking your amazing progress!",
            "tip": "Tip: Try to complete at least one homework session each day to build a strong learning habit.",
        }

    # 根据正确率生成评价
    if avg_accuracy >= 90:
        accuracy_msg = "Outstanding work! Your accuracy is exceptional -- you're truly mastering these topics!"
    elif avg_accuracy >= 75:
        accuracy_msg = "Great job! You're showing a strong understanding of the material. Keep pushing for even higher scores!"
    elif avg_accuracy >= 60:
        accuracy_msg = "Good effort! You're building a solid foundation. With a bit more practice, you'll see your scores climb even higher!"
    else:
        accuracy_msg = "Every mistake is a chance to learn something new. You're making progress, and that's what matters most!"

    # 根据连续天数生成评价
    if current_streak >= 7:
        streak_msg = f"Incredible! You've been learning for {current_streak} days in a row -- your dedication is paying off!"
    elif current_streak >= 3:
        streak_msg = f"Well done! A {current_streak}-day streak shows real commitment. Keep the momentum going!"
    elif current_streak >= 1:
        streak_msg = f"You're on a {current_streak}-day streak! Consistency is the key to success -- keep it up!"
    else:
        streak_msg = "Start a new streak today! Even one session counts -- you've got this!"

    # 根据每日目标完成率
    if daily_goal_rate >= 90:
        goal_msg = "You're hitting your daily goals almost every day -- what fantastic discipline!"
    elif daily_goal_rate >= 60:
        goal_msg = "You're meeting your daily goals more often than not. That's a great habit forming!"
    elif daily_goal_rate > 0:
        goal_msg = "You've started building your daily learning habit. Each day you practise brings you closer to your goals!"
    else:
        goal_msg = "Set a daily goal and work towards it -- even one small session each day makes a big difference over time!"

    # 综合标题
    if total_sessions >= 20 and avg_accuracy >= 80:
        headline = "You're a Learning Superstar!"
    elif total_sessions >= 10:
        headline = "Fantastic Progress -- Keep Going!"
    elif total_sessions >= 5:
        headline = "You're Building Great Momentum!"
    else:
        headline = "Great Start -- Your Journey Is Taking Off!"

    return {
        "headline": headline,
        "message": f"{accuracy_msg} {streak_msg}",
        "tip": goal_msg,
    }


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


def create_student(name: str, year_group: int = 3, age: int = 7) -> Dict[str, Any]:
    """创建新学生记录（管理员用）

    自动生成 UUID 作为 student_id。

    Returns:
        包含新学生信息的字典
    """
    conn = _get_db()
    student_id = uuid.uuid4().hex[:12]
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO students (student_id, name, year_group, age, created_at, updated_at, is_active)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (student_id, name, year_group, age, now, now),
    )
    conn.commit()
    logger.info("[DB] 新学生已创建: %s (%s)", student_id, name)
    return {
        "student_id": student_id,
        "name": name,
        "year_group": year_group,
        "age": age,
        "is_active": 1,
        "created_at": now,
    }


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


# ---- 本地订阅管理（开发模式绕过 Stripe） ----


# ---- 用户认证（持久化用户，密码哈希） ----
import hashlib
import binascii
import os


def _hash_password(password: str, salt_hex: str) -> str:
    """Return hex-encoded PBKDF2-HMAC-SHA256 hash."""
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return binascii.hexlify(dk).decode('ascii')


def create_user(username: str, password: str) -> Dict[str, Any]:
    """Create a new user with salted password hash. Raises if user exists."""
    conn = _get_db()
    # Check exists
    existing = conn.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        raise ValueError("User already exists")

    salt = os.urandom(16).hex()
    password_hash = _hash_password(password, salt)
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, salt, now),
    )
    conn.commit()
    return {"username": username, "created_at": now}


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    row = conn.execute("SELECT username, password_hash, salt, created_at FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def verify_user_credentials(username: str, password: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    salt = user.get('salt')
    expected_hash = user.get('password_hash')
    if not salt or not expected_hash:
        return False
    calc = _hash_password(password, salt)
    # Use constant-time compare
    import hmac
    return hmac.compare_digest(calc, expected_hash)


def ensure_user_columns():
    """Ensure optional columns exist on users table (migration-safe)."""
    conn = _get_db()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'is_test' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
            conn.commit()
            logger.info("[DB] Added users.is_test column")
        # Ensure index exists for fast lookups
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_is_test ON users(is_test)")
            conn.commit()
        except Exception as e:
            logger.warning("Could not create idx_users_is_test: %s", e)
    except Exception as e:
        logger.warning("Could not ensure user columns: %s", e)


def set_user_test_flag(username: str, is_test: bool) -> bool:
    """Mark a persistent user as a test account (bypass payment checks).

    Returns True if update affected a row.
    """
    ensure_user_columns()
    conn = _get_db()
    val = 1 if is_test else 0
    conn.execute("UPDATE users SET is_test = ? WHERE username = ?", (val, username))
    conn.commit()
    return conn.total_changes > 0


def is_user_test(username: str) -> bool:
    """Return True if the user is marked as a test account."""
    ensure_user_columns()
    conn = _get_db()
    row = conn.execute("SELECT is_test FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return False
    return bool(row["is_test"])


def create_local_subscription(
    customer_email: str,
    customer_name: str,
    product_name: str,
    duration_days: int,
) -> Dict[str, Any]:
    """创建本地订阅记录（开发模式使用，绕过 Stripe）"""
    conn = _get_db()
    sub_id = "dev_" + uuid.uuid4().hex[:12]
    now = datetime.utcnow()
    expires = now + timedelta(days=duration_days)
    now_str = now.isoformat()
    expires_str = expires.isoformat()

    conn.execute(
        """INSERT INTO subscriptions
           (id, customer_email, customer_name, status, product_name, duration_days, created_at, expires_at, is_dev)
           VALUES (?, ?, ?, 'active', ?, ?, ?, ?, 1)""",
        (sub_id, customer_email, customer_name, product_name, duration_days, now_str, expires_str),
    )
    conn.commit()
    logger.info("[DB] 本地订阅已创建: %s (%s - %s)", sub_id, customer_email, product_name)
    return {
        "subscription_id": sub_id,
        "customer_email": customer_email,
        "customer_name": customer_name,
        "status": "active",
        "product_name": product_name,
        "duration_days": duration_days,
        "created_at": now_str,
        "expires_at": expires_str,
        "is_dev": True,
    }


def list_local_subscriptions(limit: int = 100) -> List[Dict]:
    """列出所有本地订阅"""
    conn = _get_db()
    rows = conn.execute(
        """SELECT id, customer_email, customer_name, status, product_name,
                  duration_days, created_at, expires_at, is_dev
           FROM subscriptions
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_local_subscription_stats() -> Dict[str, Any]:
    """获取本地订阅统计"""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'").fetchone()[0]
    return {
        "active_subscriptions": total,
        "estimated_revenue_gbp": 0,
        "subscriptions": list_local_subscriptions(),
    }


# ---- 管理员：列出所有持久化用户（auth users） ----
def list_all_users(limit: int = 100, offset: int = 0):
    """列出所有注册用户（包含 is_test 标记）"""
    conn = _get_db()
    rows = conn.execute(
        "SELECT username, created_at, COALESCE(is_test, 0) as is_test FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


# 初始化时创建表
init_db()
ensure_user_columns()
