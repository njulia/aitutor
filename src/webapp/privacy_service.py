"""Child-data erasure helpers.

The service keeps erasure orchestration outside route handlers so every data
store is cleaned consistently. Stripe records are intentionally not deleted
here because payment providers may need to retain statutory accounting data;
an active subscription must be cancelled through the billing portal first.
"""
from __future__ import annotations

from typing import Any

from src.ai_monitor import delete_student_records
from src.auth_tokens import revoke_all_for_user
from src.progress_db import delete_student as delete_progress_student
from src.progress_db import delete_user_account

from .account_store import (
    delete_account,
    get_active_subscription,
    list_students,
)
from .account_store import (
    delete_student as delete_account_student,
)
from .homework_assignment_store import get_assignment_store
from .kid_session_store import (
    revoke_all_kid_sessions_for_account,
    revoke_all_kid_sessions_for_student,
)
from .memory_store import get_memory_store
from .message_routes import delete_messages_for_owners
from .reward_store import get_reward_store
from .runtime import owner_key
from .session_store import TutorSessionStore


def erase_learner(
    *,
    account_id: str,
    student_id: str,
    account_email: str,
    session_store: TutorSessionStore,
) -> dict[str, Any]:
    """Erase one learner's structured and operational data."""
    memory_events = get_memory_store().delete_all(
        student_id, account_id, include_preferences=True
    )
    progress_deleted = delete_progress_student(student_id)
    telemetry_deleted = delete_student_records(student_id)
    support_deleted = delete_messages_for_owners([student_id])
    assignments_deleted = get_assignment_store().delete_learner(student_id)
    rewards_deleted = get_reward_store().delete_learner(
        account_id=account_id,
        student_id=student_id,
    )
    # 撤销该孩子的所有登录会话
    kid_sessions_revoked = revoke_all_kid_sessions_for_student(student_id)
    # Older releases wrote learner IDs directly into RAG metadata. Remove
    # those compatibility records; current shared-library documents are not
    # learner-owned and are therefore left intact.
    try:
        from src.homework_rag import delete_student_homework as delete_primary_rag
        primary_rag_deleted = delete_primary_rag(student_id)
    except Exception:
        primary_rag_deleted = 0
    try:
        from src.elevenplus_rag import delete_student_homework as delete_eleven_rag
        eleven_rag_deleted = delete_eleven_rag(student_id)
    except Exception:
        eleven_rag_deleted = 0
    # A tutor session may include the selected learner in its JSON payload.
    sessions_deleted = session_store.delete_owner(owner_key(account_email))
    profile_deleted = delete_account_student(student_id, account_id)
    return {
        "profile_deleted": profile_deleted,
        "memory_events_deleted": memory_events,
        "progress_deleted": bool(progress_deleted),
        "telemetry_deleted": telemetry_deleted,
        "support_messages_deleted": support_deleted,
        "homework_assignments_deleted": assignments_deleted,
        "rewards_deleted": rewards_deleted,
        "kid_sessions_revoked": kid_sessions_revoked,
        "legacy_primary_rag_deleted": primary_rag_deleted,
        "legacy_elevenplus_rag_deleted": eleven_rag_deleted,
        "temporary_sessions_deleted": sessions_deleted,
    }


def erase_account(
    *,
    account_id: str,
    account_email: str,
    session_store: TutorSessionStore,
) -> dict[str, Any]:
    """Erase local parent and child data after billing has ended."""
    if get_active_subscription(account_id):
        raise ValueError(
            "Please cancel the active subscription in the billing portal "
            "before deleting the account."
        )

    learners = list_students(account_id)
    learner_results = []
    for learner in learners:
        learner_results.append(
            erase_learner(
                account_id=account_id,
                student_id=learner["id"],
                account_email=account_email,
                session_store=session_store,
            )
        )

    account_support_deleted = delete_messages_for_owners([account_email, account_id])
    residual_rewards_deleted = get_reward_store().delete_account(account_id)
    revoked_sessions = revoke_all_for_user(account_email)
    # 撤销该家庭所有孩子的登录会话
    kid_sessions_revoked = revoke_all_kid_sessions_for_account(account_id)
    account_deleted = delete_account(account_id)
    login_deleted = delete_user_account(account_email)
    return {
        "account_deleted": account_deleted,
        "login_deleted": login_deleted,
        "login_sessions_revoked": revoked_sessions,
        "kid_sessions_revoked": kid_sessions_revoked,
        "account_support_messages_deleted": account_support_deleted,
        "residual_rewards_deleted": residual_rewards_deleted,
        "learners_erased": len(learner_results),
        "learner_results": learner_results,
    }
