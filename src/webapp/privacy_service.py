"""Child-data erasure helpers.

The service keeps erasure orchestration outside route handlers so every data
store is cleaned consistently. Stripe records are intentionally not deleted
here because payment providers may need to retain statutory accounting data;
an active subscription must be cancelled through the billing portal first.
"""
from __future__ import annotations

from typing import Any, Dict

from src.auth_tokens import revoke_all_for_user
from src.progress_db import delete_student as delete_progress_student
from src.progress_db import delete_user_account
from src.ai_monitor import delete_student_records

from .account_store import (
    delete_account,
    delete_student as delete_account_student,
    get_active_subscription,
    list_students,
)
from .memory_store import get_memory_store
from .message_routes import delete_messages_for_owners
from .runtime import owner_key
from .session_store import TutorSessionStore


def erase_learner(
    *,
    account_id: str,
    student_id: str,
    account_email: str,
    session_store: TutorSessionStore,
) -> Dict[str, int | bool]:
    """Erase one learner's structured and operational data."""
    memory_events = get_memory_store().delete_all(
        student_id, account_id, include_preferences=True
    )
    progress_deleted = delete_progress_student(student_id)
    telemetry_deleted = delete_student_records(student_id)
    support_deleted = delete_messages_for_owners([student_id])
    # A tutor session may include the selected learner in its JSON payload.
    sessions_deleted = session_store.delete_owner(owner_key(account_email))
    profile_deleted = delete_account_student(student_id, account_id)
    return {
        "profile_deleted": profile_deleted,
        "memory_events_deleted": memory_events,
        "progress_deleted": bool(progress_deleted),
        "telemetry_deleted": telemetry_deleted,
        "support_messages_deleted": support_deleted,
        "temporary_sessions_deleted": sessions_deleted,
    }


def erase_account(
    *,
    account_id: str,
    account_email: str,
    session_store: TutorSessionStore,
) -> Dict[str, Any]:
    """Erase local parent and child data after billing has ended."""
    if get_active_subscription(account_id):
        raise ValueError(
            "Please cancel the active subscription in the billing portal before deleting the account."
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

    revoked_sessions = revoke_all_for_user(account_email)
    account_deleted = delete_account(account_id)
    login_deleted = delete_user_account(account_email)
    return {
        "account_deleted": account_deleted,
        "login_deleted": login_deleted,
        "login_sessions_revoked": revoked_sessions,
        "learners_erased": len(learner_results),
        "learner_results": learner_results,
    }
