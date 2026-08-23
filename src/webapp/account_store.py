"""PostgreSQL-ready account, learner and subscription persistence.

Production uses ``DATABASE_URL=postgresql+psycopg://...``. SQLite is retained
only as a zero-setup local/test fallback. Billing belongs to the parent account;
learner profiles are never sent to Stripe.
"""
from __future__ import annotations

import os
import re
import secrets
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    func,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .db import get_engine, normalise_database_url

DB_PATH = os.getenv(
    "ACCOUNT_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "accounts.db"),
)
_INITIALISED_PATH: Optional[str] = None  # retained for backward-compatible tests
_INIT_LOCK = threading.Lock()
_ENGINE: Optional[Engine] = None
_ENGINE_URL: Optional[str] = None
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_metadata = MetaData()
BETA_PLAN = "beta_year3"

# 定价计划常量
HOMEWORK_PREMIUM_PLAN = "homework_monthly"
ELEVENPLUS_PREMIUM_PLAN = "elevenplus_monthly"
# FAMILY_MONTHLY_PLAN = "family_monthly"
# FAMILY_11PLUS_MONTHLY_PLAN = "family_11plus_monthly"

PREMIUM_PLAN_NAMES = {
    HOMEWORK_PREMIUM_PLAN: "Homework Premium",
    ELEVENPLUS_PREMIUM_PLAN: "11+ Premium",
    # FAMILY_MONTHLY_PLAN: "Family Premium",
    # FAMILY_11PLUS_MONTHLY_PLAN: "Family 11+ Premium",
}

# 各计划允许的最大孩子数量
MAX_STUDENTS_BY_PLAN = {
    ELEVENPLUS_PREMIUM_PLAN: 4,
    HOMEWORK_PREMIUM_PLAN: 2,
}
DEFAULT_MAX_STUDENTS = 2  # 无订阅或未知计划时的默认限制

accounts = Table(
    "accounts",
    _metadata,
    Column("id", String(80), primary_key=True),
    Column("email", String(254), nullable=False, unique=True, index=True),
    Column("display_name", String(80), nullable=True),
    Column("role", String(20), nullable=False, default="user"),
    Column("stripe_customer_id", String(100), nullable=True, unique=True),
    # 永久家庭登录码，供孩子用 family_code + kid_code 登录，不依赖家长邮箱
    Column("family_code", String(16), nullable=True, unique=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

students = Table(
    "students",
    _metadata,
    Column("id", String(80), primary_key=True),
    Column("account_id", String(80), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(80), nullable=False),  # nickname/display label only
    Column("year_group", Integer, nullable=False),
    Column("age", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("is_default", Boolean, nullable=False, default=False),
    # NULL for ordinary learners; account_id for the single default learner.
    Column("default_for_account", String(80), nullable=True, unique=True),
    # 永久孩子登录码，与家庭码配对使用，不包含任何个人数据
    Column("kid_code", String(20), nullable=True, unique=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

learning_targets = Table(
    "learning_targets",
    _metadata,
    Column("student_id", String(80), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("daily_goal", Integer, nullable=False, default=1),
    Column("weekly_xp_goal", Integer, nullable=False, default=100),
    Column("focus_subjects", String(200), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

subscriptions = Table(
    "account_subscriptions",
    _metadata,
    Column("id", String(100), primary_key=True),
    Column("account_id", String(80), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("plan", String(80), nullable=False),
    Column("price_id", String(100), nullable=True),
    Column("status", String(30), nullable=False, index=True),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("current_period_end", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("cancel_at_period_end", Boolean, nullable=False, default=False),
    Column("stripe_customer_id", String(100), nullable=True, index=True),
    Column("stripe_subscription_id", String(100), nullable=True, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

beta_access_grants = Table(
    "beta_access_grants",
    _metadata,
    Column("id", String(100), primary_key=True),
    Column(
        "account_id",
        String(80),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    Column("granted_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

beta_access_capacity = Table(
    "beta_access_capacity",
    _metadata,
    Column("cohort", String(40), primary_key=True),
    Column("redeemed_count", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _database_url() -> str:
    configured = os.getenv("ACCOUNT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return normalise_database_url(configured)
    return f"sqlite+pysqlite:///{DB_PATH}"


def _engine() -> Engine:
    global _ENGINE, _ENGINE_URL, _INITIALISED_PATH
    url = _database_url()
    if _ENGINE is not None and _ENGINE_URL == url:
        return _ENGINE
    with _INIT_LOCK:
        if _ENGINE is not None and _ENGINE_URL == url:
            return _ENGINE
        if url.startswith("sqlite"):
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _ENGINE = get_engine(url)
        _ENGINE_URL = url
        _metadata.create_all(_ENGINE)
        _INITIALISED_PATH = DB_PATH
        return _ENGINE


def init_account_db() -> None:
    _engine()
    _ensure_legacy_columns()


# 孩子登录码使用的字符表，去除了容易混淆的 I O 0 1
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
KID_CODE_LENGTH = 6
_CODE_CREATE_ATTEMPTS = 10


def _generate_code(length: int = 6) -> str:
    """生成人类可读、可输入的永久登录码，避免混淆字符。"""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def _ensure_legacy_columns() -> None:
    """为既有数据库补齐新增列，避免老库在升级时报错。

    这是一次性迁移而非运行时兜底：新列在创建后即由 create_all 维护。
    """
    engine = _engine()
    additions = [
        ("accounts", "family_code", "VARCHAR(16)"),
        ("students", "kid_code", "VARCHAR(20)"),
        ("students", "last_login_at", "TIMESTAMP NULL"),
    ]
    for table_name, column_name, column_type in additions:
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
        except Exception:
            # 列已存在时 ALTER 会失败，这是预期行为，直接忽略
            pass
    # 迁移旧格式: 移除 FAM- 和 KID- 前缀
    _migrate_code_prefixes()


def _migrate_code_prefixes() -> None:
    """移除旧版登录码的前缀 (FAM-/KID-)，改为纯字符格式。"""
    engine = _engine()
    try:
        with engine.begin() as conn:
            # 移除 family_code 的 FAM- 前缀
            conn.exec_driver_sql(
                "UPDATE accounts SET family_code = SUBSTR(family_code, 5) "
                "WHERE family_code LIKE 'FAM-%'"
            )
            # 移除 kid_code 的 KID- 前缀
            conn.exec_driver_sql(
                "UPDATE students SET kid_code = SUBSTR(kid_code, 5) "
                "WHERE kid_code LIKE 'KID-%'"
            )
    except Exception:
        pass


def _normalise_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(value) or len(value) > 254:
        raise ValueError("A valid email address is required")
    return value


def _validate_student(name: str, year_group: int, age: int) -> tuple[str, int, int]:
    nickname = " ".join((name or "").split())
    if not nickname or len(nickname) > 40:
        raise ValueError("Learner nickname must be between 1 and 40 characters")
    if "@" in nickname or re.search(r"\b(?:school|road|street|avenue|postcode)\b", nickname, re.I):
        raise ValueError("Please use a nickname, not contact or school information")
    if not 1 <= int(year_group) <= 6:
        raise ValueError("Year group must be between 1 and 6")
    if not 5 <= int(age) <= 11:
        raise ValueError("Age must be between 5 and 11")
    return nickname, int(year_group), int(age)


def _dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row._mapping)
    # Keep old frontend contracts using 0/1 for booleans where needed.
    for key in ("is_active", "is_default", "cancel_at_period_end"):
        if key in data:
            data[key] = int(bool(data[key]))
    return data


def ensure_account(email: str, display_name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
    clean_email = _normalise_email(email)
    clean_display = " ".join((display_name or clean_email.split("@", 1)[0]).split())[:80]
    safe_role = role if role in {"user", "admin"} else "user"
    engine = _engine()
    with engine.begin() as conn:
        row = conn.execute(select(accounts).where(accounts.c.email == clean_email)).first()
    if row is None:
        now = _now()
        for _ in range(_CODE_CREATE_ATTEMPTS):
            try:
                with engine.begin() as conn:
                    conn.execute(insert(accounts).values(
                        id=f"acct_{uuid.uuid4().hex}", email=clean_email,
                        display_name=clean_display, role=safe_role,
                        stripe_customer_id=None, family_code=_generate_code(),
                        created_at=now, updated_at=now,
                    ))
            except IntegrityError:
                # Either another worker created this email, or a family-code
                # collision occurred. Read by email first, then retry with a
                # fresh code when needed.
                pass
            with engine.begin() as conn:
                row = conn.execute(
                    select(accounts).where(accounts.c.email == clean_email)
                ).first()
            if row is not None:
                break
    if row is None:
        raise RuntimeError("Unable to create or read account")
    data = _dict(row) or {}
    # 老账号补发永久家庭码，保证每个家庭都有可用的孩子登录入口
    if not data.get("family_code"):
        data = _backfill_family_code(data["id"]) or data
    return data


def _backfill_family_code(account_id: str) -> Optional[Dict[str, Any]]:
    """为缺少家庭码的既有账号补发一个唯一码。"""
    for _ in range(5):
        code = _generate_code()
        try:
            with _engine().begin() as conn:
                conn.execute(
                    update(accounts).where(accounts.c.id == account_id).values(
                        family_code=code, updated_at=_now()
                    )
                )
                return _dict(conn.execute(select(accounts).where(accounts.c.id == account_id)).first())
        except IntegrityError:
            continue
    return None


def get_account_by_family_code(family_code: str) -> Optional[Dict[str, Any]]:
    """按家庭登录码查找账号，用于孩子登录。

    兼容新旧格式: 数据库可能存储 FAM-XXXXXX 或 XXXXXX。
    """
    code = _normalise_code(family_code)
    if not code:
        return None
    with _engine().begin() as conn:
        # 先尝试精确匹配
        row = conn.execute(
            select(accounts).where(accounts.c.family_code == code)
        ).first()
        if row:
            return _dict(row)
        # 兼容旧格式: 尝试带 FAM- 前缀
        legacy_code = f"FAM-{code}"
        row = conn.execute(
            select(accounts).where(accounts.c.family_code == legacy_code)
        ).first()
        if row:
            return _dict(row)
    return None


def _normalise_code(code: str) -> str:
    return " ".join(str(code or "").upper().split())[:20]


def parse_combined_login_code(combined_code: str) -> Optional[tuple]:
    """解析组合登录码，返回 (family_code, kid_code) 或 None。

    支持格式:
    - XXXXXX-XXXXXX (current format)
    - XXXXXX-XXX (legacy format)
    - FAM-XXXXXX-XXX (旧格式，自动去除 FAM- 前缀)
    """
    code = _normalise_code(combined_code)
    # 处理旧格式: 如果以 FAM- 开头，先去掉
    if code.startswith("FAM-"):
        code = code[4:]
    if "-" not in code:
        return None
    parts = code.split("-", 1)
    if len(parts) != 2:
        return None
    family_code, kid_code = parts[0].strip(), parts[1].strip()
    # Keep existing three-character learner codes working while issuing much
    # larger six-character codes to new learners.
    if len(family_code) != 6 or len(kid_code) not in {3, KID_CODE_LENGTH}:
        return None
    # 验证字符表
    valid_chars = set(_CODE_ALPHABET)
    if not all(c in valid_chars for c in family_code + kid_code):
        return None
    return family_code, kid_code


def verify_combined_login_code(combined_code: str) -> Optional[Dict[str, Any]]:
    """使用组合登录码验证，返回孩子档案或 None。"""
    parsed = parse_combined_login_code(combined_code)
    if not parsed:
        return None
    family_code, kid_code = parsed
    return verify_family_kid_codes(family_code, kid_code)


def verify_family_kid_codes(family_code: str, kid_code: str) -> Optional[Dict[str, Any]]:
    """校验家庭码 + 孩子码配对，返回孩子档案或 None。

    兼容新旧格式: 数据库可能存储 KID-XXX 或 XXX。
    """
    account = get_account_by_family_code(family_code)
    if not account:
        return None
    normalised_kid = _normalise_code(kid_code)
    if not normalised_kid:
        return None
    with _engine().begin() as conn:
        # 先尝试精确匹配
        row = conn.execute(
            select(students).where(
                and_(
                    students.c.account_id == account["id"],
                    students.c.kid_code == normalised_kid,
                    students.c.is_active.is_(True),
                )
            )
        ).first()
        if row is None:
            # 兼容旧格式: 尝试带 KID- 前缀
            legacy_kid = f"KID-{normalised_kid}"
            row = conn.execute(
                select(students).where(
                    and_(
                        students.c.account_id == account["id"],
                        students.c.kid_code == legacy_kid,
                        students.c.is_active.is_(True),
                    )
                )
            ).first()
    if row is None:
        # 避免因码不存在而提前返回，做一次等长比较以保持常量时间行为
        secrets.compare_digest(normalised_kid, normalised_kid)
        return None
    student = _dict(row) or {}
    student["account_id"] = account["id"]
    return student


def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    try:
        clean_email = _normalise_email(email)
    except ValueError:
        return None
    with _engine().begin() as conn:
        return _dict(conn.execute(select(accounts).where(accounts.c.email == clean_email)).first())


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        return _dict(conn.execute(select(accounts).where(accounts.c.id == account_id)).first())


def set_stripe_customer(account_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        raise ValueError("Stripe customer ID is required")
    with _engine().begin() as conn:
        conn.execute(
            update(accounts).where(accounts.c.id == account_id).values(
                stripe_customer_id=customer_id, updated_at=_now()
            )
        )
        return _dict(conn.execute(select(accounts).where(accounts.c.id == account_id)).first())


def ensure_default_student(account_id: str, name: str = "Learner", year_group: int = 3, age: int = 7) -> Dict[str, Any]:
    nickname, year_group, age = _validate_student(name, year_group, age)
    engine = _engine()
    with engine.begin() as conn:
        row = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.default_for_account == account_id,
        ))).first()
        if row:
            return _dict(row) or {}
        account_exists = conn.execute(select(accounts.c.id).where(accounts.c.id == account_id)).first()
        existing = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.is_active.is_(True),
        )).order_by(students.c.created_at).limit(1)).first()
    if not account_exists:
        raise ValueError("Account not found")
    now = _now()
    if existing:
        try:
            with engine.begin() as conn:
                conn.execute(update(students).where(students.c.id == existing._mapping["id"]).values(
                    is_default=True, default_for_account=account_id, updated_at=now
                ))
        except IntegrityError:
            # Another worker selected the default learner first.
            pass
    else:
        for _ in range(_CODE_CREATE_ATTEMPTS):
            try:
                with engine.begin() as conn:
                    conn.execute(insert(students).values(
                        id=f"stu_{uuid.uuid4().hex}", account_id=account_id, name=nickname,
                        year_group=year_group, age=age, is_active=True, is_default=True,
                        default_for_account=account_id, kid_code=_generate_code(KID_CODE_LENGTH),
                        created_at=now, updated_at=now,
                    ))
            except IntegrityError:
                pass
            with engine.begin() as conn:
                created_default = conn.execute(select(students.c.id).where(and_(
                    students.c.account_id == account_id,
                    students.c.default_for_account == account_id,
                ))).first()
            if created_default:
                break
    with engine.begin() as conn:
        row = conn.execute(select(students).where(and_(
            students.c.account_id == account_id,
            students.c.default_for_account == account_id,
        )).with_for_update()).first()
    if row is None:
        raise RuntimeError("Unable to create default learner")
    result = _dict(row) or {}
    # 既有孩子档案补发永久孩子登录码
    if not result.get("kid_code"):
        result = _ensure_student_kid_code(result["id"]) or result
    return result


def _ensure_student_kid_code(student_id: str) -> Optional[Dict[str, Any]]:
    """为缺少孩子登录码的既有档案补发唯一码。"""
    for _ in range(_CODE_CREATE_ATTEMPTS):
        code = _generate_code(KID_CODE_LENGTH)
        try:
            with _engine().begin() as conn:
                conn.execute(
                    update(students).where(students.c.id == student_id).values(
                        kid_code=code, updated_at=_now()
                    )
                )
                return _dict(conn.execute(select(students).where(students.c.id == student_id)).first())
        except IntegrityError:
            continue
    return None


def _get_max_students_for_account(account_id: str) -> int:
    """根据账户的订阅计划获取允许的最大孩子数量。"""
    sub = get_active_subscription(account_id)
    if sub:
        plan = sub.get("plan", "")
        if plan in MAX_STUDENTS_BY_PLAN:
            return MAX_STUDENTS_BY_PLAN[plan]
    return DEFAULT_MAX_STUDENTS


def get_student_limit(account_id: str) -> int:
    """Return the active learner-profile allowance for a family account."""
    return _get_max_students_for_account(account_id)


def create_student(account_id: str, name: str, year_group: int, age: int) -> Dict[str, Any]:
    nickname, year_group, age = _validate_student(name, year_group, age)
    now = _now()
    engine = _engine()
    max_students = _get_max_students_for_account(account_id)
    for _ in range(_CODE_CREATE_ATTEMPTS):
        learner_id = f"stu_{uuid.uuid4().hex}"
        try:
            with engine.begin() as conn:
                # Lock the parent row so two simultaneous requests cannot both
                # pass the learner-count check on PostgreSQL.
                account_row = conn.execute(
                    select(accounts.c.id)
                    .where(accounts.c.id == account_id)
                    .with_for_update()
                ).first()
                if not account_row:
                    raise ValueError("Account not found")
                active_count = conn.execute(
                    select(func.count()).select_from(students).where(
                        and_(
                            students.c.account_id == account_id,
                            students.c.is_active.is_(True),
                        )
                    )
                ).scalar() or 0
                if active_count >= max_students:
                    raise ValueError(f"Your plan allows up to {max_students} children")
                conn.execute(
                    insert(students).values(
                        id=learner_id, account_id=account_id, name=nickname,
                        year_group=year_group, age=age, is_active=True, is_default=False,
                        default_for_account=None, kid_code=_generate_code(KID_CODE_LENGTH),
                        created_at=now, updated_at=now,
                    )
                )
                row = conn.execute(
                    select(students).where(students.c.id == learner_id)
                ).first()
            return _dict(row) or {}
        except IntegrityError:
            # Extremely unlikely global learner-code collision; retry safely.
            continue
    raise RuntimeError("Unable to create learner profile")


def adjust_student_for_academic_year(student: Dict[str, Any]) -> Dict[str, Any]:
    """根据当前日期和注册日期，自动调整学生的年级和年龄。

    英国学年从9月1日开始。每过一个9月1日，年级和年龄各增加1。
    如果学生在当前9月1日之后注册，则不晋升。
    """
    from datetime import UTC, datetime as dt

    now = dt.now(tz=UTC)
    created = student.get("created_at")
    if not created:
        return student

    if getattr(created, "tzinfo", None) is None:
        created = created.replace(tzinfo=UTC)

    # 计算当前学术年度（9月1日开始）
    if now.month >= 9:
        current_academic_year = now.year
    else:
        current_academic_year = now.year - 1

    # 计算注册时的学术年度
    if created.month >= 9:
        registration_academic_year = created.year
    else:
        registration_academic_year = created.year - 1

    years_promoted = current_academic_year - registration_academic_year
    if years_promoted <= 0:
        return student

    adjusted = dict(student)
    adjusted["year_group"] = min(6, student["year_group"] + years_promoted)
    adjusted["age"] = min(11, student["age"] + years_promoted)
    return adjusted


def list_students(account_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
    condition = students.c.account_id == account_id
    if active_only:
        condition = and_(condition, students.c.is_active.is_(True))
    with _engine().begin() as conn:
        rows = conn.execute(
            select(students).where(condition).order_by(students.c.is_default.desc(), students.c.created_at)
        ).all()
    return [_dict(row) or {} for row in rows]


def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        row = conn.execute(select(students).where(students.c.id == student_id)).first()
    result = _dict(row)
    if result and not result.get("kid_code"):
        # 既有档案补发孩子登录码，保证家长仪表盘能展示可分享的码
        result = _ensure_student_kid_code(student_id) or result
    return result


def get_student_by_kid_code(kid_code: str) -> Optional[Dict[str, Any]]:
    """按孩子登录码查找档案，用于孩子登录后的身份解析。"""
    code = _normalise_code(kid_code)
    if not code:
        return None
    with _engine().begin() as conn:
        return _dict(conn.execute(
            select(students).where(students.c.kid_code == code)
        ).first())


def record_student_login(student_id: str) -> bool:
    """记录孩子最近一次登录时间，供管理后台展示。"""
    clean = str(student_id or "").strip()
    if not clean:
        return False
    with _engine().begin() as conn:
        result = conn.execute(
            update(students)
            .where(students.c.id == clean)
            .values(last_login_at=_now())
        )
    return bool(result.rowcount)


def list_all_account_students(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """管理员查询所有账号下的学生（跨账号），供管理后台使用"""
    with _engine().begin() as conn:
        rows = conn.execute(
            select(
                students.c.id.label("student_id"),
                accounts.c.email.label("parent_username"),
                students.c.name,
                students.c.year_group,
                students.c.age,
                students.c.is_active,
                students.c.created_at,
                students.c.updated_at,
                students.c.last_login_at,
                students.c.account_id,
            )
            .select_from(students.join(accounts, students.c.account_id == accounts.c.id))
            .order_by(students.c.created_at.desc())
            .limit(max(1, min(limit, 10000)))
            .offset(max(0, offset))
        ).all()
    return [_dict(row) or {} for row in rows]


def count_all_parent_accounts() -> int:
    """管理员：统计普通家长账号总数（不计管理员账号）。"""
    with _engine().begin() as conn:
        return int(conn.execute(
            select(func.count()).select_from(accounts).where(accounts.c.role == "user")
        ).scalar_one() or 0)


def count_all_students() -> int:
    """管理员：统计已激活学生总数"""
    with _engine().begin() as conn:
        return int(conn.execute(
            select(func.count()).select_from(students).where(students.c.is_active.is_(True))
        ).scalar_one() or 0)


def student_growth_by_day(days: int = 30) -> List[Dict[str, Any]]:
    """管理员：按日统计累计已激活学生数，供概览页面增长曲线使用"""
    from datetime import UTC as _utc
    from sqlalchemy import func as sa_func
    since = datetime.now(_utc) - timedelta(days=days)
    with _engine().begin() as conn:
        rows = conn.execute(
            select(
                sa_func.date(students.c.created_at).label("date"),
                sa_func.count().label("cnt"),
            )
            .where(students.c.created_at >= since)
            .group_by(sa_func.date(students.c.created_at))
            .order_by(sa_func.date(students.c.created_at))
        ).all()
        daily = {r._mapping["date"].isoformat(): int(r._mapping["cnt"]) for r in rows}
        before_cnt = conn.execute(
            select(func.count()).select_from(students).where(
                students.c.created_at < since,
                students.c.is_active.is_(True),
            )
        ).scalar_one() or 0
    # 计算累计值
    result = []
    cumulative = before_cnt
    current = datetime.now(_utc).date()
    for i in range(days):
        d = current - timedelta(days=days - 1 - i)
        key = d.isoformat()
        cumulative += daily.get(key, 0)
        result.append({"date": key, "count": cumulative})
    return result


def account_growth_by_day(days: int = 30) -> List[Dict[str, Any]]:
    """管理员：按日统计累计家长账号数，供概览页面使用"""
    from datetime import UTC as _utc
    from sqlalchemy import func as sa_func
    since = datetime.now(_utc) - timedelta(days=days)
    with _engine().begin() as conn:
        rows = conn.execute(
            select(
                sa_func.date(accounts.c.created_at).label("date"),
                sa_func.count().label("cnt"),
            )
            .where(accounts.c.created_at >= since)
            .group_by(sa_func.date(accounts.c.created_at))
            .order_by(sa_func.date(accounts.c.created_at))
        ).all()
        daily = {r._mapping["date"].isoformat(): int(r._mapping["cnt"]) for r in rows}
        before_cnt = conn.execute(
            select(func.count()).select_from(accounts).where(accounts.c.created_at < since)
        ).scalar_one() or 0
    result = []
    cumulative = before_cnt
    current = datetime.now(_utc).date()
    for i in range(days):
        d = current - timedelta(days=days - 1 - i)
        key = d.isoformat()
        cumulative += daily.get(key, 0)
        result.append({"date": key, "count": cumulative})
    return result


def subscription_growth_by_plan(days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
    """管理员：按套餐按日统计累计订阅数，供概览页面多曲线图使用"""
    from datetime import UTC as _utc
    from sqlalchemy import func as sa_func
    since = datetime.now(_utc) - timedelta(days=days)
    known_plans = ["homework_monthly", "elevenplus_monthly", "family_monthly", "trial_5day", "beta_year3"]
    with _engine().begin() as conn:
        rows = conn.execute(
            select(
                sa_func.date(subscriptions.c.starts_at).label("date"),
                subscriptions.c.plan,
                sa_func.count().label("cnt"),
            )
            .where(subscriptions.c.starts_at >= since)
            .group_by(sa_func.date(subscriptions.c.starts_at), subscriptions.c.plan)
            .order_by(sa_func.date(subscriptions.c.starts_at))
        ).all()
        # 按 plan 分组每日新增
        daily: Dict[str, Dict[str, int]] = {p: {} for p in known_plans}
        for r in rows:
            plan = str(r._mapping["plan"])
            date_key = r._mapping["date"].isoformat()
            cnt = int(r._mapping["cnt"] or 0)
            if plan in daily:
                daily[plan][date_key] = cnt
        # 各 plan 的起始累计（之前的总数）
        before: Dict[str, int] = {}
        for plan in known_plans:
            before[plan] = conn.execute(
                select(func.count()).select_from(subscriptions).where(
                    subscriptions.c.starts_at < since,
                    subscriptions.c.plan == plan,
                )
            ).scalar_one() or 0

    result: Dict[str, List[Dict[str, Any]]] = {}
    current = datetime.now(_utc).date()
    for plan in known_plans:
        cumulative = before[plan]
        series = []
        for i in range(days):
            d = current - timedelta(days=days - 1 - i)
            key = d.isoformat()
            cumulative += daily[plan].get(key, 0)
            series.append({"date": key, "count": cumulative})
        result[plan] = series
    return result


def subscription_active_for_student(
    student_id: str,
    required_plans: Optional[List[str]] = None,
    *,
    strict_plans: bool = False,
) -> bool:
    """孩子登录会话的订阅校验：通过孩子档案解析家庭账号再查订阅。

    家庭档订阅属于账号，不属于单个孩子。
    """
    student = get_student(student_id)
    if not student:
        return False
    sub = get_active_subscription(student["account_id"])
    if not sub:
        return False
    if not required_plans:
        return True
    plan = str(sub.get("plan") or "")
    if strict_plans:
        return plan in set(required_plans)
    # 家庭档含 11+ 套餐与五日体验覆盖全部学习区
    if plan in {"elevenplus_monthly", "trial_5day"}:
        return True
    # 家庭档不含 11+ 套餐与免费 beta 仅覆盖 Years 1-6 家庭作业
    if plan in {"homework_monthly", BETA_PLAN}:
        return "homework_monthly" in set(required_plans)
    return plan in set(required_plans)


def student_belongs_to_account(student_id: str, account_id: str) -> bool:
    with _engine().begin() as conn:
        row = conn.execute(
            select(students.c.id).where(
                and_(students.c.id == student_id, students.c.account_id == account_id, students.c.is_active.is_(True))
            )
        ).first()
    return bool(row)


def update_student(student_id: str, account_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
    current = get_student(student_id)
    if not current or current["account_id"] != account_id:
        return None
    nickname, year_group, age = _validate_student(
        updates.get("name", current["name"]),
        updates.get("year_group", current["year_group"]),
        updates.get("age", current["age"]),
    )
    values = {
        "name": nickname, "year_group": year_group, "age": age,
        "is_active": bool(updates.get("is_active", current["is_active"])), "updated_at": _now(),
    }
    with _engine().begin() as conn:
        conn.execute(
            update(students).where(
                and_(students.c.id == student_id, students.c.account_id == account_id)
            ).values(**values)
        )
        row = conn.execute(select(students).where(students.c.id == student_id)).first()
    return _dict(row)


def delete_student(student_id: str, account_id: str) -> bool:
    """软删除：将学生标记为 inactive，保留所有数据"""
    return bool(update_student(student_id, account_id, is_active=False))


def hard_delete_student(student_id: str, account_id: str) -> bool:
    """硬删除：彻底移除学生档案（session 数据由 progress_db 管理）"""
    with _engine().begin() as conn:
        conn.execute(delete(learning_targets).where(learning_targets.c.student_id == student_id))
        result = conn.execute(
            delete(students).where(and_(students.c.id == student_id, students.c.account_id == account_id))
        )
    return bool(result.rowcount)


def create_subscription(
    account_id: str,
    plan: str,
    status: str,
    duration_days: int,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin/dev compatibility helper. Production access is webhook-driven."""
    now = _now()
    return upsert_stripe_subscription(
        account_id=account_id,
        plan=plan,
        status=status,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id or f"manual_{uuid.uuid4().hex}",
        price_id=None,
        current_period_end=now + timedelta(days=max(1, min(int(duration_days), 3660))),
        cancel_at_period_end=False,
    )


def upsert_stripe_subscription(
    *,
    account_id: str,
    plan: str,
    status: str,
    stripe_customer_id: Optional[str],
    stripe_subscription_id: str,
    price_id: Optional[str],
    current_period_end: Optional[datetime],
    cancel_at_period_end: bool,
) -> Dict[str, Any]:
    allowed = {"active", "trialing", "past_due", "unpaid", "canceled", "cancelled", "incomplete", "incomplete_expired", "paused", "expired"}
    clean_status = status.lower().strip()
    if clean_status not in allowed:
        clean_status = "incomplete"
    if clean_status == "canceled":
        clean_status = "cancelled"
    now = _now()
    with _engine().begin() as conn:
        row = conn.execute(
            select(subscriptions).where(subscriptions.c.stripe_subscription_id == stripe_subscription_id)
        ).first()
        values = dict(
            account_id=account_id, plan=(plan or "premium")[:80], price_id=price_id,
            status=clean_status, current_period_end=current_period_end,
            expires_at=current_period_end, cancel_at_period_end=bool(cancel_at_period_end),
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id, updated_at=now,
        )
        if row:
            conn.execute(update(subscriptions).where(subscriptions.c.id == row._mapping["id"]).values(**values))
            sub_id = row._mapping["id"]
        else:
            sub_id = f"subrec_{uuid.uuid4().hex}"
            conn.execute(insert(subscriptions).values(id=sub_id, starts_at=now, created_at=now, **values))
        if stripe_customer_id:
            conn.execute(update(accounts).where(accounts.c.id == account_id).values(
                stripe_customer_id=stripe_customer_id, updated_at=now
            ))
        result = conn.execute(select(subscriptions).where(subscriptions.c.id == sub_id)).first()
    return _dict(result) or {}


def get_subscription_by_stripe_id(stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
    with _engine().begin() as conn:
        return _dict(conn.execute(
            select(subscriptions).where(subscriptions.c.stripe_subscription_id == stripe_subscription_id)
        ).first())


def get_active_subscription(account_id: str) -> Optional[Dict[str, Any]]:
    now = _now()
    with _engine().begin() as conn:
        row = conn.execute(
            select(subscriptions).where(
                and_(
                    subscriptions.c.account_id == account_id,
                    subscriptions.c.status.in_(["active", "trialing"]),
                    subscriptions.c.current_period_end > now,
                )
            ).order_by(subscriptions.c.created_at.desc()).limit(1)
        ).first()
    return _dict(row)


def account_has_active_reward_subscription(account_id: str) -> bool:
    """Return whether the account can earn Gift Points.

    父母注册账户后即可获得 Gift Points，不需要付费订阅。
    """
    account = get_account(account_id)
    return account is not None


def beta_access_enabled() -> bool:
    return os.getenv("BETA_ACCESS_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _bounded_beta_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def redeem_beta_access(account_id: str, invite_code: str) -> Dict[str, Any]:
    """Grant invite-only, non-renewing Year 1–6 beta access.

    A shared invite secret is suitable for the deliberately small parent
    research cohort because this transaction enforces a hard maximum of 25
    family accounts. The code is compared in constant time and is never stored
    in the database or logs.
    """
    if not beta_access_enabled():
        raise ValueError("The parent beta is not accepting invitations right now.")
    configured_code = os.getenv("BETA_ACCESS_CODE", "")
    if len(configured_code) < 16:
        raise RuntimeError("BETA_ACCESS_CODE is not configured safely")
    supplied_code = str(invite_code or "").strip()
    if not secrets.compare_digest(supplied_code, configured_code):
        raise PermissionError("That beta invitation code is not recognised.")

    maximum_families = _bounded_beta_setting(
        "BETA_ACCESS_MAX_FAMILIES", 15, 1, 30
    )
    duration_days = _bounded_beta_setting(
        "BETA_ACCESS_DURATION_DAYS", 14, 1, 31
    )
    engine = _engine()
    now = _now()

    try:
        with engine.begin() as conn:
            capacity = conn.execute(
                select(beta_access_capacity.c.cohort).where(
                    beta_access_capacity.c.cohort == "parent_beta"
                )
            ).first()
            if not capacity:
                existing_count = int(
                    conn.execute(
                        select(func.count()).select_from(beta_access_grants)
                    ).scalar_one()
                    or 0
                )
                conn.execute(
                    insert(beta_access_capacity).values(
                        cohort="parent_beta",
                        redeemed_count=existing_count,
                        updated_at=now,
                    )
                )
    except IntegrityError:
        # Another worker created the singleton capacity row.
        pass

    with engine.begin() as conn:
        if not conn.execute(
            select(accounts.c.id).where(accounts.c.id == account_id)
        ).first():
            raise ValueError("Parent account not found")

        active_paid = conn.execute(
            select(subscriptions.c.plan)
            .where(
                and_(
                    subscriptions.c.account_id == account_id,
                    subscriptions.c.status.in_(["active", "trialing"]),
                    subscriptions.c.current_period_end > now,
                    subscriptions.c.plan != BETA_PLAN,
                )
            )
            .limit(1)
        ).first()
        if active_paid:
            raise ValueError(
                "This family already has active Homework Magic access."
            )

        existing_grant = conn.execute(
            select(beta_access_grants).where(
                beta_access_grants.c.account_id == account_id
            )
        ).first()
        if existing_grant:
            grant = dict(existing_grant._mapping)
            beta_subscription_id = f"beta_{grant['id']}"
            existing_subscription = conn.execute(
                select(subscriptions).where(
                    subscriptions.c.stripe_subscription_id
                    == beta_subscription_id
                )
            ).first()
            if not existing_subscription:
                raise RuntimeError("The existing beta grant could not be read")
            return {
                "subscription": _dict(existing_subscription) or {},
                "already_redeemed": True,
                "maximum_families": maximum_families,
            }

        capacity_update = conn.execute(
            update(beta_access_capacity)
            .where(
                and_(
                    beta_access_capacity.c.cohort == "parent_beta",
                    beta_access_capacity.c.redeemed_count
                    < maximum_families,
                )
            )
            .values(
                redeemed_count=beta_access_capacity.c.redeemed_count + 1,
                updated_at=now,
            )
        )
        if not capacity_update.rowcount:
            raise ValueError("The parent beta cohort is now full.")

        grant_id = f"grant_{uuid.uuid4().hex}"
        subscription_id = f"subrec_{uuid.uuid4().hex}"
        beta_subscription_id = f"beta_{grant_id}"
        expires_at = now + timedelta(days=duration_days)
        conn.execute(
            insert(beta_access_grants).values(
                id=grant_id,
                account_id=account_id,
                granted_at=now,
                expires_at=expires_at,
            )
        )
        conn.execute(
            insert(subscriptions).values(
                id=subscription_id,
                account_id=account_id,
                plan=BETA_PLAN,
                price_id=None,
                status="active",
                starts_at=now,
                current_period_end=expires_at,
                expires_at=expires_at,
                cancel_at_period_end=True,
                stripe_customer_id=None,
                stripe_subscription_id=beta_subscription_id,
                created_at=now,
                updated_at=now,
            )
        )
        saved = conn.execute(
            select(subscriptions).where(
                subscriptions.c.id == subscription_id
            )
        ).first()
    return {
        "subscription": _dict(saved) or {},
        "already_redeemed": False,
        "maximum_families": maximum_families,
    }


def account_has_used_plan(account_id: str, plan: str) -> bool:
    """Return whether an account has ever received the named entitlement."""
    if not account_id or not plan:
        return False
    with _engine().begin() as conn:
        row = conn.execute(
            select(subscriptions.c.id).where(
                and_(
                    subscriptions.c.account_id == account_id,
                    subscriptions.c.plan == str(plan),
                )
            ).limit(1)
        ).first()
    return row is not None


def account_has_active_subscription(
    email: str,
    required_plans: Optional[List[str]] = None,
    *,
    strict_plans: bool = False,
) -> bool:
    account = get_account_by_email(email)
    if not account:
        return False
    sub = get_active_subscription(account["id"])
    if not sub:
        return False
    if required_plans:
        if strict_plans:
            return str(sub.get("plan") or "") in set(required_plans)
        # 11+ Premium and the five-day pass cover both learning areas.
        effective_required = set(required_plans)
        if sub.get("plan") in {"elevenplus_monthly", "trial_5day"}:
            return True
        # Homework Premium and the research beta cover Years 1-6 only.
        if sub.get("plan") in {"homework_monthly", BETA_PLAN}:
            return "homework_monthly" in effective_required
        return sub.get("plan") in effective_required
    return True


def get_learning_target(student_id: str) -> Dict[str, Any]:
    """读取孩子学习目标，缺失时返回默认目标。"""
    with _engine().begin() as conn:
        row = conn.execute(
            select(learning_targets).where(learning_targets.c.student_id == student_id)
        ).first()
    if row is None:
        return {"daily_goal": 1, "weekly_xp_goal": 100, "focus_subjects": None}
    data = _dict(row) or {}
    return {
        "daily_goal": int(data.get("daily_goal") or 1),
        "weekly_xp_goal": int(data.get("weekly_xp_goal") or 100),
        "focus_subjects": data.get("focus_subjects"),
    }


def set_learning_target(
    account_id: str,
    student_id: str,
    *,
    daily_goal: Optional[int] = None,
    weekly_xp_goal: Optional[int] = None,
    focus_subjects: Optional[str] = None,
) -> Dict[str, Any]:
    """家长为孩子设置学习目标。需校验孩子归属。"""
    if not student_belongs_to_account(student_id, account_id):
        raise ValueError("Learner profile not found")
    daily = 1 if daily_goal is None else max(1, min(int(daily_goal), 10))
    weekly = 100 if weekly_xp_goal is None else max(10, min(int(weekly_xp_goal), 2000))
    focus = None
    if focus_subjects is not None:
        focus = ", ".join(
            part.strip()[:40] for part in str(focus_subjects).split(",") if part.strip()
        )[:200] or None
    now = _now()
    with _engine().begin() as conn:
        conn.execute(
            delete(learning_targets).where(learning_targets.c.student_id == student_id)
        )
        conn.execute(
            insert(learning_targets).values(
                student_id=student_id, daily_goal=daily,
                weekly_xp_goal=weekly, focus_subjects=focus, updated_at=now,
            )
        )
    return get_learning_target(student_id)


def get_account_overview(email: str) -> Dict[str, Any]:
    account = ensure_account(email)
    default = ensure_default_student(account["id"])
    return {
        "account": account,
        "students": list_students(account["id"]),
        "default_student_id": default["id"],
        "subscription": get_active_subscription(account["id"]),
    }


def get_account_by_stripe_customer_id(customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        return None
    with _engine().begin() as conn:
        return _dict(conn.execute(
            select(accounts).where(accounts.c.stripe_customer_id == customer_id)
        ).first())


def list_subscriptions(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List locally materialised entitlements with their parent account."""
    with _engine().begin() as conn:
        rows = conn.execute(
            select(
                subscriptions,
                accounts.c.email.label("customer_email"),
                accounts.c.display_name.label("customer_name"),
            )
            .select_from(
                subscriptions.outerjoin(
                    accounts,
                    subscriptions.c.account_id == accounts.c.id,
                )
            )
            .order_by(subscriptions.c.created_at.desc())
            .limit(max(1, min(int(limit), 1000)))
            .offset(max(0, int(offset)))
        ).all()
    items = [_dict(row) or {} for row in rows]
    for item in items:
        item["customer"] = item.get("customer_email") or item.get("customer_name")
    return items


def get_subscription_stats() -> Dict[str, Any]:
    """Return entitlement counts from PostgreSQL, not a live Stripe list call."""
    now = _now()
    monthly_prices = {
        "homework_monthly": 4.99,
        "elevenplus_monthly": 9.99,
    }
    with _engine().begin() as conn:
        active_filter = and_(
            subscriptions.c.status.in_(["active", "trialing"]),
            subscriptions.c.current_period_end > now,
        )
        active = conn.execute(
            select(func.count()).select_from(subscriptions).where(active_filter)
        ).scalar_one()
        plan_rows = conn.execute(
            select(subscriptions.c.plan, func.count())
            .where(active_filter)
            .group_by(subscriptions.c.plan)
        ).all()
        total = conn.execute(select(func.count()).select_from(subscriptions)).scalar_one()
    active_by_plan = {
        str(row[0]): int(row[1] or 0)
        for row in plan_rows
    }
    estimated_revenue = round(
        sum(
            monthly_prices.get(plan, 0) * count
            for plan, count in active_by_plan.items()
        ),
        2,
    )
    return {
        "active_subscriptions": int(active or 0),
        "active_by_plan": active_by_plan,
        "estimated_revenue_gbp": estimated_revenue,
        "total_subscription_records": int(total or 0),
        "subscriptions": list_subscriptions(limit=100),
        "source": "local_webhook_materialisation",
    }


def delete_account(account_id: str) -> bool:
    """Delete the parent account and its learners/entitlements.

    Explicit child deletes also make the local SQLite development fallback
    behave like PostgreSQL's ON DELETE CASCADE.
    """
    with _engine().begin() as conn:
        conn.execute(
            delete(beta_access_grants).where(
                beta_access_grants.c.account_id == account_id
            )
        )
        conn.execute(delete(subscriptions).where(subscriptions.c.account_id == account_id))
        conn.execute(delete(learning_targets).where(
            learning_targets.c.student_id.in_(
                select(students.c.id).where(students.c.account_id == account_id)
            )
        ))
        conn.execute(delete(students).where(students.c.account_id == account_id))
        result = conn.execute(delete(accounts).where(accounts.c.id == account_id))
    return bool(result.rowcount)
