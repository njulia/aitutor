from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.webapp.reward_store import RewardStore, review_fingerprint

DELIVERY_ADDRESS = {
    "recipient_name": "Alex Parent",
    "address_line1": "10 High Street",
    "address_line2": "",
    "town_city": "London",
    "postcode": "SW1A 1AA",
    "country": "GB",
    "adult_recipient_confirmed": True,
}
DELIVERY_SECRET = "unit-test-delivery-secret-with-32-characters"


def _fingerprint(seed: str) -> str:
    return review_fingerprint(
        homework=f"Question {seed}",
        answers=f"Answer {seed}",
        subject="Maths",
    )


def test_effort_xp_quests_daily_cap_and_certificates(tmp_path) -> None:
    store = RewardStore(f"sqlite+pysqlite:///{tmp_path / 'rewards.db'}")
    account_id = "acct_family"
    student_id = "stu_learner"
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)

    first = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("one"),
        subject="Maths",
        awarded_at=now,
    )
    assert first["awarded_xp"] == 30  # 20 activity + 10 first quest
    assert first["lifetime_xp"] == 30

    duplicate = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("one"),
        subject="Maths",
        awarded_at=now,
    )
    assert duplicate["awarded_xp"] == 0
    assert duplicate["already_awarded"] is True

    second = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("two"),
        subject="English",
        awarded_at=now,
    )
    assert second["awarded_xp"] == 35  # 20 activity + 15 second quest

    third = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("three"),
        subject="Science",
        awarded_at=now,
    )
    # 20 activity + 20 third quest + 25 three-subject weekly quest.
    assert third["awarded_xp"] == 65
    assert third["lifetime_xp"] == 130
    assert {item["code"] for item in third["new_certificates"]} == {
        "brilliant_beginner"
    }

    capped = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("four"),
        subject="History",
        awarded_at=now,
    )
    assert capped["awarded_xp"] == 0
    assert capped["daily_cap_reached"] is True
    assert capped["lifetime_xp"] == 130

    dashboard = store.dashboard(account_id=account_id, student_id=student_id)
    assert dashboard["wallet"]["lifetime_xp"] == 130
    assert dashboard["wallet"]["gift_points"] == 130
    completed = {item["code"] for item in dashboard["quests"] if item["completed"]}
    assert {
        "ready_set_learn",
        "double_explorer",
        "triple_star",
        "subject_safari",
    }.issubset(completed)
    certificate = store.get_certificate(
        account_id=account_id,
        student_id=student_id,
        certificate_code="brilliant_beginner",
    )
    assert certificate and certificate["title"] == "Brilliant Beginner"


def test_parent_approval_spends_gift_points_but_never_deducts_xp(tmp_path) -> None:
    store = RewardStore(
        f"sqlite+pysqlite:///{tmp_path / 'spend.db'}",
        delivery_secret=DELIVERY_SECRET,
    )
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    for index, subject in enumerate(("Maths", "English", "Science"), start=1):
        store.award_checked_activity(
            account_id="acct_family",
            student_id="stu_learner",
            fingerprint=_fingerprint(str(index)),
            subject=subject,
            awarded_at=now,
        )

    requested = store.request_redemption(
        account_id="acct_family",
        student_id="stu_learner",
        reward_code="homework_magic_stickers",
    )
    assert requested["status"] == "pending"
    before = store.dashboard(
        account_id="acct_family", student_id="stu_learner"
    )["wallet"]
    assert before["gift_points"] == 130

    approved = store.decide_redemption(
        account_id="acct_family",
        redemption_id=requested["id"],
        decision="approve",
        delivery_address=DELIVERY_ADDRESS,
    )
    assert approved["redemption"]["status"] == "approved"
    assert approved["wallet"]["gift_points"] == 30
    assert approved["wallet"]["lifetime_xp"] == 130
    assert approved["redemption"]["delivery_address_supplied"] is True
    assert "recipient_name" not in str(approved)

    order = store.get_reward_order(redemption_id=requested["id"])
    assert order is not None
    assert order["delivery_address"]["recipient_name"] == "Alex Parent"
    assert order["delivery_address"]["postcode"] == "SW1A 1AA"

    cancelled = store.decide_redemption(
        account_id="acct_family",
        redemption_id=requested["id"],
        decision="cancel",
    )
    assert cancelled["redemption"]["status"] == "cancelled"
    assert cancelled["wallet"]["gift_points"] == 130
    assert cancelled["wallet"]["lifetime_xp"] == 130
    assert store.get_reward_order(redemption_id=requested["id"])[
        "delivery_address"
    ] is None


def test_only_branded_gifts_and_encrypted_adult_uk_delivery(tmp_path) -> None:
    store = RewardStore(
        f"sqlite+pysqlite:///{tmp_path / 'delivery.db'}",
        delivery_secret=DELIVERY_SECRET,
    )
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    for index, subject in enumerate(("Maths", "English", "Science"), start=1):
        store.award_checked_activity(
            account_id="acct_family",
            student_id="stu_learner",
            fingerprint=_fingerprint(f"delivery-{index}"),
            subject=subject,
            awarded_at=now,
        )

    dashboard = store.dashboard(account_id="acct_family", student_id="stu_learner")
    assert {item["code"] for item in dashboard["catalog"]} == {
        "homework_magic_stickers",
        "homework_magic_pen",
        "homework_magic_notebook",
    }
    requested = store.request_redemption(
        account_id="acct_family",
        student_id="stu_learner",
        reward_code="homework_magic_stickers",
    )
    with pytest.raises(ValueError, match="postcode"):
        store.decide_redemption(
            account_id="acct_family",
            redemption_id=requested["id"],
            decision="approve",
            delivery_address={**DELIVERY_ADDRESS, "postcode": "NOT A POSTCODE"},
        )

    store.decide_redemption(
        account_id="acct_family",
        redemption_id=requested["id"],
        decision="approve",
        delivery_address=DELIVERY_ADDRESS,
    )
    with store.engine.begin() as conn:
        encrypted = conn.execute(
            store.delivery_addresses.select()
        ).first()._mapping["encrypted_payload"]
    assert "Alex Parent" not in encrypted
    assert "SW1A 1AA" not in encrypted

    dispatched = store.decide_reward_order(
        redemption_id=requested["id"],
        decision="dispatch",
    )
    assert dispatched["redemption"]["status"] == "dispatched"
    assert dispatched["wallet"]["lifetime_xp"] == 130


def test_review_fingerprint_never_contains_raw_homework_or_answers() -> None:
    fingerprint = review_fingerprint(
        homework="Private worksheet wording",
        answers="Private pupil answer",
        subject="English",
    )
    assert len(fingerprint) == 64
    assert "Private" not in fingerprint
    assert fingerprint == review_fingerprint(
        homework="Private worksheet wording",
        answers="Private pupil answer",
        subject="English",
    )
