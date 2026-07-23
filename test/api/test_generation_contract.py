from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.api


def test_year1_maths_generation_preserves_rag_metadata(client, app_module, monkeypatch) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert profile["year_group"] == 1
        assert subjects == ["Maths"]
        assert is_eleven_plus is False
        return [{
            "subject": "Maths",
            "content": "1. What is 2 + 3?",
            "doc_id": "math_y1_test_001",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)

    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 1,
            "subjects": ["Maths"],
            "mode": "homework",
            "profile": {},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    item = body["homework"][0]
    assert item["from_rag"] is True
    assert item["doc_id"] == "math_y1_test_001"
    assert item["is_eleven_plus"] is False


def test_guided_primary_generation_uses_structured_choices_and_time_limit(
    client, app_module, monkeypatch
) -> None:
    captured = {}

    def fake_generate(profile, subjects, is_eleven_plus=False):
        captured["profile"] = profile
        captured["subjects"] = subjects
        assert is_eleven_plus is False
        return [{
            "subject": "Science",
            "content": "full worksheet",
            "questions": [
                {
                    "number": index,
                    "question": f"Question {index}?",
                    "response_type": "text",
                    "options": [],
                }
                for index in range(1, 11)
            ],
            "doc_id": "science_y2_guided",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "setup_source": "guided_homework",
                "year_group": 2,
                "subject": "Science",
                "session_minutes": 10,
                "difficulty": "gentle",
                "learning_notes": "Email pupil@example.com. Reading is tricky.",
                "description": "Do not keep this.",
                "target_school": "Do not keep this.",
            },
            "subjects": ["Unknown subject"],
            "mode": "homework",
            "question_count": 20,
        },
    )

    assert response.status_code == 200, response.text
    profile = captured["profile"]
    assert captured["subjects"] == ["Science"]
    assert profile["preferred_session_minutes"] == 10
    assert profile["question_count"] == 5
    assert "pupil@example.com" not in profile["learning_needs"]
    assert "description" not in profile
    assert "target_school" not in profile

    body = response.json()
    assert len(body["homework"][0]["questions"]) == 5
    assert "Question 5?" in body["homework"][0]["content"]
    assert "Question 6?" not in body["homework"][0]["content"]
    assert "student_id" not in body["profile"]
    assert "learning_needs" not in body["profile"]
    assert body["profile"]["difficulty"] == "gentle"


def test_tutor_mode_keeps_question_index_and_doc_id(client, app_module, monkeypatch) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        return [{
            "subject": "Maths",
            "content": "1. What is 1 + 1?\n2. What is 2 + 2?",
            "doc_id": "math_y1_two_questions",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)

    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 1,
            "subjects": ["Maths"],
            "mode": "tutor",
            "profile": {},
        },
    )
    assert response.status_code == 200, response.text
    homework = response.json()["homework"]
    assert [item["question_index"] for item in homework] == [0, 1]
    assert {item["doc_id"] for item in homework} == {"math_y1_two_questions"}
    assert all(item["from_rag"] is True for item in homework)


def test_review_route_passes_question_index_to_review_service(client, app_module, monkeypatch) -> None:
    captured = {}

    def fake_review(homework, answers, subject, profile, **kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "review": "Correct!",
            "score": 1,
            "max_score": 1,
            "attempted": 1,
            "correct_count": 1,
        }

    monkeypatch.setattr(app_module, "review_homework", fake_review)

    response = client.post(
        "/api/review",
        json={
            "homework": "What is 2 + 2?",
            "answers": "4",
            "subject": "Maths",
            "from_rag": True,
            "homework_doc_id": "math_y1_two_questions",
            "question_index": 1,
            "is_tutor_mode": True,
        },
    )
    assert response.status_code == 200, response.text
    assert captured["homework_doc_id"] == "math_y1_two_questions"
    assert captured["question_index"] == 1
    assert captured["is_tutor_mode"] is True


def test_year_round_generation_preserves_selected_week_and_public_questions(client, app_module, monkeypatch) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert profile["plan_week"] == 14
        assert profile["learning_goals"] == ["Decimals and percentages"]
        assert subjects == ["Maths-1year"]
        assert is_eleven_plus is True
        return [{
            "subject": "Maths-1year",
            "content": "QUESTIONS\n1. Which decimal equals one half?\nA) 0.2\nB) 0.5",
            "questions": [{
                "number": 1,
                "question": "Which decimal equals one half?",
                "options": [
                    {"label": "A", "text": "0.2"},
                    {"label": "B", "text": "0.5"},
                ],
            }],
            "doc_id": "week_14_maths",
            "from_rag": True,
            "plan_week": 14,
            "content_type": "year_round",
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *a, **kw: True)
    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "year_group": 5,
                "age": 10,
                "plan_week": 14,
                "plan_phase": "build",
                "learning_goals": ["Decimals and percentages"],
            },
            "subjects": ["Maths-1year"],
            "is_eleven_plus": True,
            "mode": "homework",
        },
    )

    assert response.status_code == 200, response.text
    item = response.json()["homework"][0]
    assert item["plan_week"] == 14
    assert item["subject"] == "Maths-1year"
    assert item["questions"][0]["options"][1]["text"] == "0.5"
    assert "ANSWERS" not in item["content"]



def test_subject_endpoint_exposes_separate_year_round_keys(client) -> None:
    response = client.get("/api/subjects")
    assert response.status_code == 200
    data = response.json()
    assert data["eleven_plus"] == [
        "Maths",
        "English",
        "Verbal Reasoning",
        "Non-Verbal Reasoning",
    ]
    assert data["eleven_plus_year_round"] == [
        "Maths-1year",
        "English-1year",
        "VerbalReasoning-1year",
        "NonVerbalReasoning-1year",
    ]
    for subject in (
        "German",
        "Italian",
        "Polish",
        "Arabic",
        "Music",
        "Physical Education",
        "Religious Education",
        "PSHE",
    ):
        assert subject in data["primary"]


def test_year_round_api_canonicalises_old_friendly_subject_name(client, app_module, monkeypatch) -> None:
    captured = {}

    def fake_generate(profile, subjects, is_eleven_plus=False):
        captured["subjects"] = subjects
        return [{
            "subject": subjects[0],
            "content": "1. Pick one.\nA) One\nB) Two",
            "doc_id": "week_01",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *a, **kw: True)
    response = client.post(
        "/api/generate",
        json={
            "profile": {"year_group": 5, "age": 10, "plan_week": 1},
            "subjects": ["Verbal Reasoning"],
            "is_eleven_plus": True,
            "mode": "homework",
        },
    )

    assert response.status_code == 200, response.text
    assert captured["subjects"] == ["VerbalReasoning-1year"]

@pytest.mark.parametrize("year", [1, 6])
def test_primary_generation_exposes_choice_model_for_all_year_groups(
    client, app_module, monkeypatch, year
) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert profile["year_group"] == year
        assert is_eleven_plus is False
        return [{
            "subject": "Maths",
            "content": "1. Pick the correct total.\nA) 7\nB) 8\nC) 9",
            "doc_id": f"math_y{year}_mcq",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": year,
            "subjects": ["Maths"],
            "mode": "homework",
            "profile": {},
        },
    )

    assert response.status_code == 200, response.text
    item = response.json()["homework"][0]
    assert item["questions"][0]["response_type"] == "single_choice"
    assert item["questions"][0]["options"][1] == {"label": "B", "text": "8"}


def test_standard_elevenplus_generation_exposes_choice_model(
    client, app_module, monkeypatch
) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert is_eleven_plus is True
        return [{
            "subject": "Verbal Reasoning",
            "content": "1. Choose the opposite of ANCIENT.\nA) old\nB) modern\nC) historic",
            "doc_id": "vr_mcq_001",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *a, **kw: True)
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "subjects": ["Verbal Reasoning"],
            "is_eleven_plus": True,
            "mode": "homework",
            "profile": {},
        },
    )

    assert response.status_code == 200, response.text
    item = response.json()["homework"][0]
    assert item["is_eleven_plus"] is True
    assert item["questions"][0]["response_type"] == "single_choice"
    assert [option["label"] for option in item["questions"][0]["options"]] == ["A", "B", "C"]


def test_tutor_generation_preserves_choice_options(
    client, app_module, monkeypatch
) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        return [{
            "subject": "Maths",
            "content": "1. Choose 2 + 2.\nA) 3\nB) 4\n2. Write 5 + 5.",
            "doc_id": "mixed_tutor_001",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 2,
            "subjects": ["Maths"],
            "mode": "tutor",
            "profile": {},
        },
    )

    assert response.status_code == 200, response.text
    homework = response.json()["homework"]
    assert homework[0]["response_type"] == "single_choice"
    assert homework[0]["options"][1]["text"] == "4"
    assert homework[1]["response_type"] == "text"


def test_tutor_generation_preserves_reading_passage_context(
    client, app_module, monkeypatch
) -> None:
    def fake_generate(profile, subjects, is_eleven_plus=False):
        return [{
            "subject": "English",
            "content": (
                "Read this passage.\nA fox crossed the quiet field.\n\n"
                "1. What crossed the field?\nA) A fox\nB) A dog"
            ),
            "doc_id": "english_context_001",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 3,
            "subjects": ["English"],
            "mode": "tutor",
            "profile": {},
        },
    )

    assert response.status_code == 200, response.text
    question = response.json()["homework"][0]["questions"][0]
    assert "A fox crossed the quiet field" in question["context"]
    assert question["question"] == "What crossed the field?"
    assert question["response_type"] == "single_choice"


def test_personalised_french_homework_uses_supported_primary_subject(
    client, app_module, monkeypatch
) -> None:
    captured = {}

    def fake_generate(profile, subjects, is_eleven_plus=False):
        captured["profile"] = profile
        captured["subjects"] = subjects
        return [{
            "subject": subjects[0],
            "content": "1. Match bonjour to its English meaning.",
            "doc_id": None,
            "from_rag": False,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "description": "I am in Year 4 and want to practise French greetings.",
                "year_group": 4,
                "age": 9,
            },
            "subjects": [],
            "mode": "homework",
        },
    )

    assert response.status_code == 200, response.text
    assert captured["subjects"] == ["French"]
    assert captured["profile"]["year_group"] == 4
    assert response.json()["homework"][0]["subject"] == "French"


def test_personalised_out_of_scope_request_is_blocked_before_generation(
    client, app_module, monkeypatch
) -> None:
    def unexpected_generate(*_args, **_kwargs):
        raise AssertionError("Out-of-scope content must not reach homework generation")

    monkeypatch.setattr(app_module, "generate_homework_with_profile", unexpected_generate)
    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "description": "Tell me which shares I should buy tomorrow.",
                "year_group": 5,
                "age": 10,
            },
            "subjects": [],
            "mode": "homework",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["policy_blocked"] is True
    assert "privacy" in body["error"].lower()
    assert "policy" in body["error"].lower()
    assert "primary school subjects and 11+" in body["error"]


def test_explicit_unknown_subject_is_blocked(client, app_module, monkeypatch) -> None:
    def unexpected_generate(*_args, **_kwargs):
        raise AssertionError("Unknown subject must not reach generation")

    monkeypatch.setattr(app_module, "generate_homework_with_profile", unexpected_generate)
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 4,
            "subjects": ["Cryptocurrency trading"],
            "mode": "homework",
            "profile": {},
        },
    )

    assert response.status_code == 400
    assert response.json()["policy_blocked"] is True


def test_api_unwraps_legacy_json_homework_before_returning_it(
    client, app_module, monkeypatch
) -> None:
    wrapped = json.dumps({
        "homework": "1. Say hello in French.\\n2. Say goodbye in French.",
        "correct_answers": [{"question": "1", "answer": "bonjour"}],
    })

    monkeypatch.setattr(
        app_module,
        "generate_homework_with_profile",
        lambda *_args, **_kwargs: [{
            "subject": "French",
            "content": wrapped,
            "doc_id": "legacy-french",
            "from_rag": True,
        }],
    )
    response = client.post(
        "/api/generate",
        json={
            "quick_select": True,
            "year": 4,
            "subjects": ["French"],
            "mode": "homework",
            "profile": {},
        },
    )

    assert response.status_code == 200, response.text
    content = response.json()["homework"][0]["content"]
    assert content == "1. Say hello in French.\n2. Say goodbye in French."
    assert "correct_answers" not in content


def test_guided_elevenplus_uses_structured_profile_and_requested_length(
    client, app_module, monkeypatch
) -> None:
    questions = [
        {
            "number": index,
            "question": f"Choose answer {index}.",
            "response_type": "single_choice",
            "options": [
                {"label": "A", "text": "First"},
                {"label": "B", "text": "Second"},
            ],
        }
        for index in range(1, 9)
    ]

    def fake_generate(profile, subjects, is_eleven_plus=False):
        assert subjects == ["English"]
        assert is_eleven_plus is True
        assert profile["year_group"] == 4
        assert profile["question_count"] == 5
        assert profile["confidence"] == "sometimes_tricky"
        assert "target_school" not in profile
        assert "child@example.com" not in profile["learning_needs"]
        return [{
            "subject": "English",
            "content": "full worksheet",
            "questions": questions,
            "doc_id": "guided_english",
            "from_rag": True,
        }]

    monkeypatch.setattr(app_module, "generate_homework_with_profile", fake_generate)
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *a, **kw: True)

    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "setup_source": "guided_11plus",
                "year_group": 4,
                "subject": "English",
                "confidence": "sometimes_tricky",
                "question_count": 5,
                "exam_format": "GL Assessment",
                "learning_notes": "Email child@example.com. Reading is tricky.",
                "target_school": "Must not be retained",
            },
            "subjects": ["Maths"],
            "is_eleven_plus": True,
            "mode": "homework",
            "question_count": 5,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["homework"][0]["questions"]) == 5
    assert body["homework"][0]["is_eleven_plus"] is True
    assert "Choose answer 6." not in body["homework"][0]["content"]
    assert "student_id" not in body["profile"]
    assert "learning_needs" not in body["profile"]


def test_guided_elevenplus_checks_entitlement_before_generation(
    client, app_module, monkeypatch
) -> None:
    monkeypatch.setattr(app_module, "user_has_subscription", lambda *a, **kw: False)
    monkeypatch.setattr(
        app_module,
        "generate_homework_with_profile",
        lambda *_args, **_kwargs: pytest.fail("Generation must not run before entitlement"),
    )

    response = client.post(
        "/api/generate",
        json={
            "profile": {
                "setup_source": "guided_11plus",
                "year_group": 5,
                "subject": "Maths",
                "confidence": "confident",
                "question_count": 5,
            },
            "subjects": ["Maths"],
            "is_eleven_plus": True,
            "mode": "tutor",
            "question_count": 5,
        },
    )

    assert response.status_code == 401
    assert response.json()["required_plan"] == "elevenplus_monthly"
