"""The allow-listed, child-friendly Study Buddy challenge options.

The catalogue deliberately derives its primary-subject coverage from the same
``UK_PRIMARY_SUBJECTS`` list used by the learning app.  A challenge is never a
free-text subject: callers must use one of these stable keys.  That keeps
challenge progress tied to verified learning activities and avoids creating
new, unreviewed subject labels from request data.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.models import (
    ELEVEN_PLUS_SUBJECTS,
    UK_PRIMARY_SUBJECTS,
    canonical_primary_subject,
)


NORMAL_CHALLENGE_REWARD = {"target_count": 1, "xp": 5, "gift_points": 2}
ADVANCED_CHALLENGE_REWARD = {"target_count": 1, "xp": 8, "gift_points": 3}


# Keep presentation details here rather than in the browser so that the API
# only ever publishes options the backend accepts.  The map must cover every
# supported primary subject; the check below makes additions to the app's
# subject list visible during development.
_PRIMARY_PRESENTATION: dict[str, tuple[str, str, str, str]] = {
    "Maths": ("maths", "➗", "Maths", "Maths Mini Sprint"),
    "English": ("english", "📖", "English", "English Word Sprint"),
    "Science": ("science", "🔬", "Science", "Science Discovery Dash"),
    "History": ("history", "🏛️", "History", "History Time Trek"),
    "Geography": ("geography", "🗺️", "Geography", "Geography Explorer"),
    "Design and Technology": (
        "design_technology", "🛠️", "Design & Technology", "Design & Make Dash"
    ),
    "Art and Design": ("art_design", "🎨", "Art & Design", "Art Adventure"),
    "Computing": ("computing", "💻", "Computing", "Coding Quest"),
    "Music": ("music", "🎵", "Music", "Music Maker Mission"),
    "Physical Education": ("physical_education", "🏃", "PE", "PE Power-Up"),
    "Religious Education": (
        "religious_education", "🌍", "Religious Education", "RE Reflection Quest"
    ),
    "PSHE": ("pshe", "🌟", "PSHE", "PSHE Super Skills"),
    "French": ("french", "🇫🇷", "French", "French Word Quest"),
    "German": ("german", "🇩🇪", "German", "German Word Quest"),
    "Spanish": ("spanish", "🇪🇸", "Spanish", "Spanish Word Quest"),
    "Italian": ("italian", "🇮🇹", "Italian", "Italian Word Quest"),
    "Polish": ("polish", "🇵🇱", "Polish", "Polish Word Quest"),
    "Arabic": ("arabic", "🌙", "Arabic", "Arabic Word Quest"),
    "Latin": ("latin", "🏺", "Latin", "Latin Word Quest"),
    "Chinese": ("chinese", "🧧", "Chinese", "Chinese Word Quest"),
}


def _entry(
    *,
    key: str,
    icon: str,
    label: str,
    title: str,
    subject: str,
    practice_subject: str | None = None,
    practice_tab: str,
    group: str,
    reward: Mapping[str, int],
    match_subjects: tuple[str, ...] = (),
    match_any_supported_subject: bool = False,
    match_any_eleven_plus_subject: bool = False,
    requires_eleven_plus_context: bool = False,
) -> dict[str, Any]:
    """Build a serialisable immutable-looking catalogue record."""
    return {
        "key": key,
        "icon": icon,
        "label": f"{icon} {label}",
        "title": title,
        "subject": subject,
        "practice_subject": practice_subject or subject,
        "practice_tab": practice_tab,
        "group": group,
        "target_count": int(reward["target_count"]),
        "xp": int(reward["xp"]),
        "gift_points": int(reward["gift_points"]),
        "match_subjects": tuple(match_subjects),
        "match_any_supported_subject": bool(match_any_supported_subject),
        "match_any_eleven_plus_subject": bool(match_any_eleven_plus_subject),
        "requires_eleven_plus_context": bool(requires_eleven_plus_context),
    }


def _build_catalog() -> dict[str, dict[str, Any]]:
    missing = set(UK_PRIMARY_SUBJECTS) - set(_PRIMARY_PRESENTATION)
    extra = set(_PRIMARY_PRESENTATION) - set(UK_PRIMARY_SUBJECTS)
    if missing or extra:
        raise RuntimeError(
            "Study Buddy primary challenge options must match UK_PRIMARY_SUBJECTS "
            f"(missing={sorted(missing)}, extra={sorted(extra)})."
        )

    catalog: dict[str, dict[str, Any]] = {}
    for subject in UK_PRIMARY_SUBJECTS:
        key, icon, label, title = _PRIMARY_PRESENTATION[subject]
        catalog[key] = _entry(
            key=key,
            icon=icon,
            label=label,
            title=title,
            subject=subject,
            practice_tab="homework",
            group="primary",
            reward=NORMAL_CHALLENGE_REWARD,
            match_subjects=(subject,),
        )

    # Existing challenge keys remain valid so live rows and older browser
    # versions continue to work. All 11+ choices begin with “11+” so a child
    # can tell at a glance that they open the 11+ learning area, not ordinary
    # homework.
    catalog["reasoning"] = _entry(
        key="reasoning",
        icon="🧠",
        label="11+ Reasoning",
        title="11+ Reasoning Brain Boost",
        subject="11+ Reasoning",
        practice_subject="Verbal Reasoning",
        practice_tab="eleven",
        group="eleven_plus",
        reward=ADVANCED_CHALLENGE_REWARD,
        match_subjects=("Verbal Reasoning", "Non-Verbal Reasoning"),
        requires_eleven_plus_context=True,
    )
    catalog["11plus"] = _entry(
        key="11plus",
        icon="⭐",
        label="11+",
        title="11+ Brain Boost",
        subject="11+",
        practice_subject="Maths",
        practice_tab="eleven",
        group="eleven_plus",
        reward=ADVANCED_CHALLENGE_REWARD,
        match_any_eleven_plus_subject=True,
    )
    catalog["verbal_reasoning"] = _entry(
        key="verbal_reasoning",
        icon="🗣️",
        label="11+ Verbal Reasoning",
        title="11+ Verbal Reasoning Brain Boost",
        subject="11+ Verbal Reasoning",
        practice_subject="Verbal Reasoning",
        practice_tab="eleven",
        group="eleven_plus",
        reward=ADVANCED_CHALLENGE_REWARD,
        match_subjects=("Verbal Reasoning",),
        requires_eleven_plus_context=True,
    )
    catalog["non_verbal_reasoning"] = _entry(
        key="non_verbal_reasoning",
        icon="🧩",
        label="11+ Non-Verbal Reasoning",
        title="11+ Pattern Power-Up",
        subject="11+ Non-Verbal Reasoning",
        practice_subject="Non-Verbal Reasoning",
        practice_tab="eleven",
        group="eleven_plus",
        reward=ADVANCED_CHALLENGE_REWARD,
        match_subjects=("Non-Verbal Reasoning",),
        requires_eleven_plus_context=True,
    )
    catalog["eleven_plus_maths"] = _entry(
        key="eleven_plus_maths", icon="➕", label="11+ Maths",
        title="11+ Maths Brain Boost", subject="11+ Maths", practice_subject="Maths",
        practice_tab="eleven", group="eleven_plus", reward=ADVANCED_CHALLENGE_REWARD,
        match_subjects=("Maths",), requires_eleven_plus_context=True,
    )
    catalog["eleven_plus_english"] = _entry(
        key="eleven_plus_english", icon="📚", label="11+ English",
        title="11+ English Brain Boost", subject="11+ English", practice_subject="English",
        practice_tab="eleven", group="eleven_plus", reward=ADVANCED_CHALLENGE_REWARD,
        match_subjects=("English",), requires_eleven_plus_context=True,
    )
    catalog["mixed"] = _entry(
        key="mixed",
        icon="🌈",
        label="Any subject",
        title="Study Sprint",
        subject="Any supported subject",
        practice_tab="homework",
        group="primary",
        reward=NORMAL_CHALLENGE_REWARD,
        match_any_supported_subject=True,
    )
    return catalog


CHALLENGE_CATALOG = _build_catalog()
"""Stable challenge key to backend-validated option metadata."""


def _normalise_key(value: object) -> str:
    return re.sub(r"[-\s]+", "_", str(value or "").strip().casefold())


def challenge_catalog_entry(challenge_type: object) -> dict[str, Any] | None:
    """Return a copy of an allow-listed challenge option, if it exists."""
    entry = CHALLENGE_CATALOG.get(_normalise_key(challenge_type))
    return dict(entry) if entry else None


def challenge_catalog_options() -> list[dict[str, Any]]:
    """Return child-facing options safe to send to an authenticated learner."""
    public_fields = (
        "key",
        "icon",
        "label",
        "title",
        "subject",
        "practice_subject",
        "practice_tab",
        "group",
        "target_count",
        "xp",
        "gift_points",
    )
    return [
        {field: option[field] for field in public_fields}
        for option in CHALLENGE_CATALOG.values()
    ]


def supported_challenge_types() -> frozenset[str]:
    return frozenset(CHALLENGE_CATALOG)


def _fold_subject(value: object) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


_ELEVEN_PLUS_ALIASES = {
    "maths": "Maths",
    "mathematics": "Maths",
    "11maths": "Maths",
    "11plusmaths": "Maths",
    "elevenplusmaths": "Maths",
    "english": "English",
    "11english": "English",
    "11plusenglish": "English",
    "elevenplusenglish": "English",
    "verbalreasoning": "Verbal Reasoning",
    "11verbalreasoning": "Verbal Reasoning",
    "11plusverbalreasoning": "Verbal Reasoning",
    "elevenplusverbalreasoning": "Verbal Reasoning",
    "nonverbalreasoning": "Non-Verbal Reasoning",
    "11nonverbalreasoning": "Non-Verbal Reasoning",
    "11plusnonverbalreasoning": "Non-Verbal Reasoning",
    "elevenplusnonverbalreasoning": "Non-Verbal Reasoning",
}


def canonical_challenge_subject(subject: object) -> str:
    """Canonicalise a verified activity subject to a supported learning subject.

    Empty text and unknown labels intentionally return an empty string.  In
    particular, a mixed challenge cannot be completed by an arbitrary value
    that happened to be written to a historical reward event.
    """
    value = str(subject or "").strip()
    primary = canonical_primary_subject(value)
    if primary:
        return primary
    return _ELEVEN_PLUS_ALIASES.get(_fold_subject(value), "")


def is_eleven_plus_activity_subject(subject: object) -> bool:
    """Return whether an activity label is specifically an 11+ activity.

    Maths and English are offered in both the primary and 11+ parts of the
    app.  Their shared display names alone must not let ordinary primary work
    finish an 11+ challenge, so those two need an 11+ prefix in the recorded
    subject.  Verbal and non-verbal reasoning are 11+-only in this product.
    """
    canonical_subject = canonical_challenge_subject(subject)
    if canonical_subject in {"Verbal Reasoning", "Non-Verbal Reasoning"}:
        return True
    folded = _fold_subject(subject)
    return folded.startswith("11") or folded.startswith("elevenplus")


def challenge_subject_matches(challenge_type: object, subject: object) -> bool:
    """Whether a verified activity can make progress for this challenge."""
    option = challenge_catalog_entry(challenge_type)
    canonical_subject = canonical_challenge_subject(subject)
    if not option or not canonical_subject:
        return False
    if option["match_any_supported_subject"]:
        return canonical_subject in UK_PRIMARY_SUBJECTS or canonical_subject in ELEVEN_PLUS_SUBJECTS
    if option["match_any_eleven_plus_subject"]:
        return canonical_subject in ELEVEN_PLUS_SUBJECTS and is_eleven_plus_activity_subject(subject)
    if option["requires_eleven_plus_context"] and not is_eleven_plus_activity_subject(subject):
        return False
    return canonical_subject in option["match_subjects"]


def legacy_open_target_count_types() -> frozenset[str]:
    """Legacy keys whose old open challenges used multi-activity targets.

    A database upgrade should change *only* open rows for these keys where the
    stored target is greater than the current one.  This allows old children
    to finish a challenge after one verified subject activity without rewriting
    completion history or future custom values.
    """
    return frozenset({"maths", "english", "reasoning", "11plus", "mixed"})
