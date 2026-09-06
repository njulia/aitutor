"""将 progress_students 中尚未在 account_store 的学生迁移到新表。

发布前运行，确保所有学生和家长数据不丢失。

用法:  python -m src.tools.migrate_students
"""
import os
import logging
import uuid
from datetime import datetime, UTC
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)


def _now():
    return datetime.now(UTC)


def migrate() -> dict:
    """可由管理端点调用的迁移函数，返回结果字典。"""
    from src.progress_db import list_all_students
    from src.webapp.account_store import (
        ensure_account,
        get_student as account_get_student,
        _engine as _account_engine_func,
        accounts,
    )
    from src.webapp.reward_store import get_reward_store

    legacy_students = list_all_students(limit=100000, offset=0)
    logger.info("progress_students 中有 %d 条记录", len(legacy_students))

    created = 0
    skipped = 0
    skip_no_id = 0
    skip_exists = 0
    skip_account_fail = 0
    skip_student_fail = 0
    reward_store = get_reward_store()

    for legacy in legacy_students:
        sid = legacy.get("student_id")
        if not sid:
            skipped += 1
            skip_no_id += 1
            continue

        # 如果 account_store 中已存在，跳过
        if account_get_student(sid):
            skipped += 1
            skip_exists += 1
            logger.debug("  跳过 %s：已存在于 account_store", sid)
            continue

        name = (legacy.get("name") or "Learner").strip()
        year_group = int(legacy.get("year_group") or 3)
        age = int(legacy.get("age") or max(5, min(12, year_group + 4)))
        parent_email = (legacy.get("parent_username") or "").strip()
        xp = int(legacy.get("xp") or 0)
        gift_points = int(legacy.get("gift_points") or 0)
        is_active = bool(legacy.get("is_active", True))

        # 确定或创建家长账号
        try:
            if parent_email and "@" in parent_email:
                account = ensure_account(parent_email)
            else:
                internal_email = f"legacy-migrated-{sid}@internal.local"
                # 内部账号需要直接插入，不走 ensure_account 的 email 校验
                with _account_engine_func().begin() as conn:
                    row = conn.execute(
                        accounts.select().where(accounts.c.email == internal_email)
                    ).first()
                if not row:
                    now = _now()
                    # 手动创建内部账号（复用 ensure_account 的逻辑但跳过校验）
                    acct_id = f"acct_{uuid.uuid4().hex}"
                    with _account_engine_func().begin() as conn:
                        from src.webapp.account_store import _generate_code
                        conn.execute(
                            accounts.insert().values(
                                id=acct_id, email=internal_email,
                                display_name="Migrated Parent", role="user",
                                family_code=_generate_code(),
                                created_at=now, updated_at=now,
                            )
                        )
                    with _account_engine_func().begin() as conn:
                        row = conn.execute(
                            accounts.select().where(accounts.c.id == acct_id)
                        ).first()
                    account_id = row._mapping["id"]
                else:
                    account_id = row._mapping["id"]
                account = {"id": account_id, "email": internal_email}
        except Exception as e:
            logger.warning("跳过 %s：创建账号失败 - %s", sid, e)
            skipped += 1
            skip_account_fail += 1
            continue

        # 创建学生档案
        try:
            # 使用原始 student_id 保持跨表一致性
            now = _now()
            with _account_engine_func().begin() as conn:
                from src.webapp.account_store import students, _generate_buddy_code, _generate_code, _validate_student
                nickname, yg, ag = _validate_student(name, year_group, age)
                conn.execute(
                    students.insert().values(
                        id=sid, account_id=account["id"], name=nickname,
                        year_group=yg, age=ag, is_active=is_active,
                        is_default=False, default_for_account=None,
                        kid_code=_generate_code(),
                        buddy_code=_generate_buddy_code(nickname),
                        created_at=now, updated_at=now,
                    )
                )
            logger.info("  创建学生: %s (%s) -> account %s", sid, nickname, account["id"])
        except Exception as e:
            logger.warning("  跳过 %s：创建学生失败 - %s", sid, e)
            skipped += 1
            skip_student_fail += 1
            continue

        # 迁移 XP 和 Gift Points 到 reward_wallets
        if xp or gift_points:
            try:
                with reward_store.engine.begin() as conn:
                    reward_store._ensure_wallet(conn, account["id"], sid)
                    conn.execute(
                        reward_store.wallets.update()
                        .where(reward_store.wallets.c.student_id == sid)
                        .values(
                            lifetime_xp=xp,
                            spendable_xp=gift_points,
                            updated_at=_now(),
                        )
                    )
            except Exception as e:
                logger.warning("  警告 %s：reward_wallet 写入失败 - %s", sid, e)

        created += 1

    logger.info("完成: 创建 %d, 跳过 %d (无ID=%d, 已存在=%d, 账号失败=%d, 学生失败=%d)",
                created, skipped, skip_no_id, skip_exists, skip_account_fail, skip_student_fail)
    return {
        "created": created,
        "skipped": skipped,
        "skip_no_id": skip_no_id,
        "skip_exists": skip_exists,
        "skip_account_fail": skip_account_fail,
        "skip_student_fail": skip_student_fail,
    }


def main() -> None:
    result = migrate()
    print(f"Migrated: created={result['created']}, skipped={result['skipped']}")


if __name__ == "__main__":
    main()
