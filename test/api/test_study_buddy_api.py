"""Study Buddy API contracts for child-safe, bounded interactions."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.webapp.account_store import create_student, ensure_account
from src.webapp.kid_session_store import create_kid_session, init_kid_session_db
from src.webapp.reward_store import get_reward_store
from src.webapp.study_buddy_store import (
    approve_request,
    create_request,
    init_study_buddy_db,
)


pytestmark = pytest.mark.api


def test_approved_buddies_use_separate_share_codes_and_fixed_emojis(client) -> None:
    init_study_buddy_db()
    init_kid_session_db()
    suffix = uuid4().hex[:12]
    first_account = ensure_account(f"buddy-api-one-{suffix}@example.com")
    second_account = ensure_account(f"buddy-api-two-{suffix}@example.com")
    first = create_student(first_account["id"], "Robin", 4, 8)
    second = create_student(second_account["id"], "Casey", 4, 8)
    request = create_request(first["id"], second["id"])
    approve_request(request["id"], first_account["id"], True)
    approve_request(request["id"], second_account["id"], True)

    first_headers = {"X-Kid-Session": create_kid_session(first["id"])["token"]}
    found = client.post(
        "/api/study-buddies/search",
        json={"query": second["buddy_code"]},
        headers=first_headers,
    )
    sent = client.post(
        "/api/study-buddies/emoji",
        json={"target_student_id": second["id"], "emoji": "heart"},
        headers=first_headers,
    )

    # Ranking shares only earned badge summaries with approved buddies.  This
    # lets the UI show a kind achievement chip after each child's name.
    reward_store = get_reward_store()
    with reward_store.engine.begin() as conn:
        conn.execute(reward_store.badges.insert().values(
            id=f"badge_{uuid4().hex}", account_id=first_account["id"],
            student_id=first["id"], badge_code="buddy_booster", earned_at=datetime.now(UTC),
        ))
        conn.execute(reward_store.badges.insert().values(
            id=f"badge_{uuid4().hex}", account_id=second_account["id"],
            student_id=second["id"], badge_code="challenge_legend", earned_at=datetime.now(UTC),
        ))

    second_headers = {"X-Kid-Session": create_kid_session(second["id"])["token"]}
    mine = client.get("/api/study-buddies", headers=second_headers)
    page = client.get("/study-buddies")

    assert found.status_code == 200, found.text
    assert found.json()["students"] == [{
        "student_id": second["id"], "nickname": "Casey", "year_group": 4,
    }]
    assert sent.status_code == 200, sent.text
    assert mine.status_code == 200, mine.text
    assert mine.json()["buddy_code"] == second["buddy_code"]
    assert mine.json()["emoji_reactions"][0]["emoji"] == "❤️"
    assert {
        (item["key"], item["emoji"], item["label"])
        for item in mine.json()["emoji_options"]
    } >= {
        ("heart", "❤️", "Heart"),
        ("smile", "😊", "Smile"),
        ("high_five", "🙌", "High five"),
        ("star", "⭐", "Star"),
    }
    ranked = mine.json()["ranking"]["all_time"]
    own_row = next(item for item in ranked if item["student_id"] == second["id"])
    buddy_row = next(item for item in ranked if item["student_id"] == first["id"])
    assert own_row["nickname"] == "Casey"
    assert own_row["is_current_learner"] is True
    assert any(item["code"] == "challenge_legend" for item in own_row["badges"])
    assert any(item["code"] == "buddy_booster" for item in buddy_row["badges"])
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
