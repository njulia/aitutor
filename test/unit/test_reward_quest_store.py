from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
CUSTOM_CHARACTER = {
    "character": "boy",
    "clothes": "green_jumper",
    "shoes": "boots",
    "skin_tone": "tan",
    "hair_colour": "black",
    "hair_length": "short",
    "hair_style": "curly",
    "eye_shape": "almond",
    "eye_colour": "green",
    "nose": "small",
    "mouth": "grin",
    "eyebrows": "arched",
}


def _fingerprint(seed: str) -> str:
    return review_fingerprint(
        homework=f"Question {seed}",
        answers=f"Answer {seed}",
        subject="Maths",
    )


def _award_sticker_points(
    store: RewardStore,
    *,
    account_id: str = "acct_family",
    student_id: str = "stu_learner",
    prefix: str,
) -> dict:
    """Earn at least the catalogue's 500-point sticker threshold."""
    now = datetime.now(UTC).replace(
        hour=12,
        minute=0,
        second=0,
        microsecond=0,
    )
    for day_offset in range(5):
        awarded_at = now - timedelta(days=day_offset)
        for index, subject in enumerate(
            ("Maths", "English", "Science"),
            start=1,
        ):
            store.award_checked_activity(
                account_id=account_id,
                student_id=student_id,
                fingerprint=_fingerprint(
                    f"{prefix}-{day_offset}-{index}"
                ),
                subject=subject,
                gift_points_eligible=True,
                awarded_at=awarded_at,
            )
    return store.dashboard(
        account_id=account_id,
        student_id=student_id,
    )["wallet"]


def test_effort_xp_is_uncapped_but_gift_points_keep_daily_cap(
    tmp_path,
) -> None:
    store = RewardStore(f"sqlite+pysqlite:///{tmp_path / 'rewards.db'}")
    account_id = "acct_family"
    student_id = "stu_learner"
    now = datetime.now(UTC).replace(microsecond=0)

    first = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("one"),
        subject="Maths",
        gift_points_eligible=True,
        awarded_at=now,
    )
    assert first["awarded_xp"] == 30  # 20 activity + 10 first quest
    assert first["lifetime_xp"] == 30

    duplicate = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("one"),
        subject="Maths",
        gift_points_eligible=True,
        awarded_at=now,
    )
    assert duplicate["awarded_xp"] == 0
    assert duplicate["already_awarded"] is True

    second = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("two"),
        subject="English",
        gift_points_eligible=True,
        awarded_at=now,
    )
    assert second["awarded_xp"] == 35  # 20 activity + 15 second quest

    third = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("three"),
        subject="Science",
        gift_points_eligible=True,
        awarded_at=now,
    )
    # 20 activity + 20 third quest + 25 three-subject weekly quest.
    assert third["awarded_xp"] == 65
    assert third["lifetime_xp"] == 130
    assert {item["code"] for item in third["new_certificates"]} == {
        "brilliant_beginner"
    }

    after_gift_cap = store.award_checked_activity(
        account_id=account_id,
        student_id=student_id,
        fingerprint=_fingerprint("four"),
        subject="History",
        gift_points_eligible=True,
        awarded_at=now,
    )
    assert after_gift_cap["awarded_xp"] == 20
    assert after_gift_cap["awarded_gift_points"] == 0
    assert after_gift_cap["daily_cap_reached"] is True
    assert after_gift_cap["daily_gift_activity_cap_reached"] is True
    assert after_gift_cap["xp_activity_cap"] is None
    assert after_gift_cap["lifetime_xp"] == 150

    dashboard = store.dashboard(account_id=account_id, student_id=student_id)
    assert dashboard["wallet"]["lifetime_xp"] == 150
    assert dashboard["wallet"]["gift_points"] == 130
    assert dashboard["rules"]["xp_activity_cap"] is None
    assert dashboard["rules"]["daily_gift_point_activity_cap"] == 3
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


def test_everyone_earns_xp_but_free_learners_do_not_earn_gift_points(
    tmp_path,
) -> None:
    store = RewardStore(f"sqlite+pysqlite:///{tmp_path / 'free-rewards.db'}")
    awarded = store.award_checked_activity(
        account_id="acct_free",
        student_id="stu_free",
        fingerprint=_fingerprint("free"),
        subject="Maths",
    )

    assert awarded["awarded_xp"] == 30
    assert awarded["awarded_gift_points"] == 0
    assert awarded["gift_points_eligible"] is False
    assert awarded["lifetime_xp"] == 30
    assert awarded["gift_points"] == 0

    dashboard = store.dashboard(account_id="acct_free", student_id="stu_free")
    assert dashboard["wallet"]["lifetime_xp"] == 30
    assert dashboard["wallet"]["gift_points"] == 0
    with pytest.raises(PermissionError, match="active Homework Magic subscription"):
        store.request_redemption(
            account_id="acct_free",
            student_id="stu_free",
            reward_code="homework_magic_stickers",
        )


def test_character_avatar_customisation_persists_and_grows_with_xp(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'avatar.db'}"
    store = RewardStore(database_url)
    account_id = "acct_avatar"
    student_id = "stu_avatar"

    initial = store.avatar_summary(
        account_id=account_id,
        student_id=student_id,
    )
    assert initial["profile"] == {
        "character": "girl",
        "clothes": "pink_dress",
        "shoes": "trainers",
        "skin_tone": "warm",
        "hair_colour": "brown",
        "hair_length": "long",
        "hair_style": "ponytail",
        "eye_shape": "round",
        "eye_colour": "green",
        "nose": "button",
        "mouth": "smile",
        "eyebrows": "arched",
        "customised": False,
    }
    assert initial["growth"]["stage"] == 1
    assert initial["growth"]["name"] == "Little Learner"

    customised = store.update_avatar(
        account_id=account_id,
        student_id=student_id,
        **CUSTOM_CHARACTER,
    )
    assert customised["profile"] == {
        **CUSTOM_CHARACTER,
        "customised": True,
    }
    assert customised["growth"]["stage"] == 1

    # XP is normally changed only by checked learning activities. Set a known
    # wallet total directly here so this isolated persistence test remains
    # deterministic without needing to create unrelated quest events.
    with store.engine.begin() as conn:
        conn.execute(
            store.wallets.update()
            .where(store.wallets.c.student_id == student_id)
            .where(store.wallets.c.account_id == account_id)
            .values(lifetime_xp=640)
        )
    grown = store.avatar_summary(
        account_id=account_id,
        student_id=student_id,
    )
    assert grown["growth"]["lifetime_xp"] == 640
    assert grown["growth"]["stage"] == 4
    assert grown["growth"]["name"] == "Clever Champion"

    reloaded = RewardStore(database_url).avatar_summary(
        account_id=account_id,
        student_id=student_id,
    )
    assert reloaded == grown

    with pytest.raises(ValueError, match="available avatar hair colours"):
        store.update_avatar(
            account_id=account_id,
            student_id=student_id,
            **{**CUSTOM_CHARACTER, "hair_colour": "unsafe-choice"},
        )

    erased = store.delete_learner(
        account_id=account_id,
        student_id=student_id,
    )
    assert erased["character_profiles"] == 1
    with store.engine.begin() as conn:
        assert conn.execute(store.character_profiles.select()).first() is None

    store.update_avatar(
        account_id=account_id,
        student_id="stu_avatar_sibling",
        **{**CUSTOM_CHARACTER, "character": "girl"},
    )
    account_erased = store.delete_account(account_id)
    assert account_erased["character_profiles"] == 1
    with store.engine.begin() as conn:
        assert conn.execute(store.character_profiles.select()).first() is None


def test_parent_approval_spends_gift_points_but_never_deducts_xp(tmp_path) -> None:
    store = RewardStore(
        f"sqlite+pysqlite:///{tmp_path / 'spend.db'}",
        delivery_secret=DELIVERY_SECRET,
    )
    before = _award_sticker_points(store, prefix="spend")

    requested = store.request_redemption(
        account_id="acct_family",
        student_id="stu_learner",
        reward_code="homework_magic_stickers",
        gift_points_eligible=True,
    )
    assert requested["status"] == "pending"
    assert before["gift_points"] >= 500

    with pytest.raises(PermissionError, match="active Homework Magic subscription"):
        store.decide_redemption(
            account_id="acct_family",
            redemption_id=requested["id"],
            decision="approve",
            delivery_address=DELIVERY_ADDRESS,
        )

    approved = store.decide_redemption(
        account_id="acct_family",
        redemption_id=requested["id"],
        decision="approve",
        delivery_address=DELIVERY_ADDRESS,
        gift_points_eligible=True,
    )
    assert approved["redemption"]["status"] == "approved"
    assert approved["wallet"]["gift_points"] == before["gift_points"] - 500
    assert approved["wallet"]["lifetime_xp"] == before["lifetime_xp"]
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
    assert cancelled["wallet"]["gift_points"] == before["gift_points"]
    assert cancelled["wallet"]["lifetime_xp"] == before["lifetime_xp"]
    assert store.get_reward_order(redemption_id=requested["id"])[
        "delivery_address"
    ] is None


def test_only_branded_gifts_and_encrypted_adult_uk_delivery(tmp_path) -> None:
    store = RewardStore(
        f"sqlite+pysqlite:///{tmp_path / 'delivery.db'}",
        delivery_secret=DELIVERY_SECRET,
    )
    before = _award_sticker_points(store, prefix="delivery")

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
        gift_points_eligible=True,
    )
    with pytest.raises(ValueError, match="postcode"):
        store.decide_redemption(
            account_id="acct_family",
            redemption_id=requested["id"],
            decision="approve",
            delivery_address={**DELIVERY_ADDRESS, "postcode": "NOT A POSTCODE"},
            gift_points_eligible=True,
        )

    store.decide_redemption(
        account_id="acct_family",
        redemption_id=requested["id"],
        decision="approve",
        delivery_address=DELIVERY_ADDRESS,
        gift_points_eligible=True,
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
    assert dispatched["wallet"]["lifetime_xp"] == before["lifetime_xp"]


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
