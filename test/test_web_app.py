import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
import os
import json
from datetime import datetime, timedelta

# Adjust the path to import the FastAPI app correctly
# Assuming web_app.py is in the parent directory of the 'test' folder
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import web_app  # Import web_app to access its internal variables like _dev_mode
from web_app import app, initialize, _split_homework_into_questions


# Ensure the app is initialized for tests
@pytest.fixture(scope="session", autouse=True)
def setup_app():
    initialize()


@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "initialized": True}


@pytest.mark.asyncio
@patch('web_app.generate_homework_with_profile')
async def test_generate_homework_success_homework_mode(mock_generate_homework_with_profile, client: AsyncClient):
    mock_generate_homework_with_profile.return_value = [
        {"subject": "Maths", "content": "1. What is 1+1?\n2. What is 2+2?", "doc_id": "math_1", "from_rag": True},
        {"subject": "English", "content": "1. Write a sentence.\n2. Spell 'cat'.", "doc_id": "english_1",
         "from_rag": False}
    ]

    response = await client.post("/api/generate", json={
        "quick_select": True,
        "year": 1,
        "subjects": ["Maths", "English"],
        "mode": "homework"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mode"] == "homework"
    assert len(data["homework"]) == 2
    assert data["homework"][0]["subject"] == "Maths"
    assert data["homework"][1]["subject"] == "English"
    mock_generate_homework_with_profile.assert_called_once()


@pytest.mark.asyncio
@patch('web_app._split_homework_into_questions')
@patch('web_app.generate_homework_with_profile')
async def test_generate_homework_success_tutor_mode(
        mock_generate_homework_with_profile, mock_split_homework_into_questions, client: AsyncClient):
    mock_generate_homework_with_profile.return_value = [
        {"subject": "Maths", "content": "1. What is 1+1?\n2. What is 2+2?", "doc_id": "math_1", "from_rag": True}
    ]
    mock_split_homework_into_questions.return_value = [
        {"subject": "Maths", "content": "1. What is 1+1?", "question_id": "q1", "original_full_content": "..."}
    ]

    response = await client.post("/api/generate", json={
        "quick_select": True,
        "year": 1,
        "subjects": ["Maths"],
        "mode": "tutor"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mode"] == "tutor"
    assert len(data["homework"]) == 1
    assert data["homework"][0]["subject"] == "Maths"
    assert data["homework"][0]["content"] == "1. What is 1+1?"
    mock_generate_homework_with_profile.assert_called_once()
    mock_split_homework_into_questions.assert_called_once()


@pytest.mark.asyncio
async def test_generate_homework_no_subjects(client: AsyncClient):
    response = await client.post("/api/generate", json={
        "quick_select": True,
        "year": 1,
        "subjects": [],
        "mode": "homework"
    })

    assert response.status_code == 400
    assert response.json() == {"success": False, "error": "No subjects selected"}


@pytest.mark.asyncio
@patch('web_app.generate_homework_with_profile', side_effect=Exception("Generation failed"))
async def test_generate_homework_failure(mock_generate_homework_with_profile, client: AsyncClient):
    response = await client.post("/api/generate", json={
        "quick_select": True,
        "year": 1,
        "subjects": ["Maths"],
        "mode": "homework"
    })

    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "Generation failed"}
    mock_generate_homework_with_profile.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.review_homework')
async def test_review_homework_success(mock_review_homework, client: AsyncClient):
    mock_review_homework.return_value = {"success": True, "review": "Great job!"}

    response = await client.post("/api/review", json={
        "homework": "1. What is 1+1?",
        "answers": "2",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "is_tutor_mode": False
    })

    assert response.status_code == 200
    assert response.json() == {"success": True, "review": "Great job!"}
    mock_review_homework.assert_called_once_with("1. What is 1+1?", "2", "Maths", {"year_group": 1},
                                                 is_tutor_mode=False)


@pytest.mark.asyncio
@patch('web_app.review_homework')
async def test_review_homework_tutor_mode_success(mock_review_homework, client: AsyncClient):
    mock_review_homework.return_value = {"success": True, "review": "Correct answer!"}

    response = await client.post("/api/review", json={
        "homework": "1. What is 1+1?",
        "answers": "2",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "is_tutor_mode": True
    })

    assert response.status_code == 200
    assert response.json() == {"success": True, "review": "Correct answer!"}
    mock_review_homework.assert_called_once_with("1. What is 1+1?", "2", "Maths", {"year_group": 1}, is_tutor_mode=True)


@pytest.mark.asyncio
@patch('web_app.review_homework', side_effect=Exception("Review failed"))
async def test_review_homework_failure(mock_review_homework, client: AsyncClient):
    response = await client.post("/api/review", json={
        "homework": "1. What is 1+1?",
        "answers": "2",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "is_tutor_mode": False
    })

    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "Review failed"}
    mock_review_homework.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.explain_deep')
async def test_explain_deep_success(mock_explain_deep, client: AsyncClient):
    mock_explain_deep.return_value = {"success": True, "explanation": "Detailed explanation."}

    response = await client.post("/api/explain-deep", json={
        "homework": "1. What is 1+1?",
        "answers": "3",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "review_feedback": "Incorrect."
    })

    assert response.status_code == 200
    assert response.json() == {"success": True, "explanation": "Detailed explanation."}
    mock_explain_deep.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.explain_deep', side_effect=Exception("Explanation failed"))
async def test_explain_deep_failure(mock_explain_deep, client: AsyncClient):
    response = await client.post("/api/explain-deep", json={
        "homework": "1. What is 1+1?",
        "answers": "3",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "review_feedback": "Incorrect."
    })

    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "Explanation failed"}
    mock_explain_deep.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.improve_practice')
async def test_improve_practice_success(mock_improve_practice, client: AsyncClient):
    mock_improve_practice.return_value = {"success": True, "practice": "More practice questions."}

    response = await client.post("/api/improve-practice", json={
        "homework": "1. What is 1+1?",
        "answers": "3",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "review_feedback": "Incorrect."
    })

    assert response.status_code == 200
    assert response.json() == {"success": True, "practice": "More practice questions."}
    mock_improve_practice.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.improve_practice', side_effect=Exception("Practice failed"))
async def test_improve_practice_failure(mock_improve_practice, client: AsyncClient):
    response = await client.post("/api/improve-practice", json={
        "homework": "1. What is 1+1?",
        "answers": "3",
        "subject": "Maths",
        "profile": {"year_group": 1},
        "review_feedback": "Incorrect."
    })

    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "Practice failed"}
    mock_improve_practice.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.process_uploaded_file')
async def test_upload_file_success(mock_process_uploaded_file, client: AsyncClient):
    mock_process_uploaded_file.return_value = ("File content", False)

    # Create a dummy file for upload
    test_file_path = "test_upload.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test file.")

    with open(test_file_path, "rb") as f:
        response = await client.post(
            "/api/upload-file",
            files={"file": ("test_upload.txt", f, "text/plain")}
        )

    os.remove(test_file_path)  # Clean up the dummy file

    assert response.status_code == 200
    assert response.json() == {"success": True, "content": "File content", "is_image": False}
    mock_process_uploaded_file.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.process_uploaded_file', side_effect=Exception("File processing error"))
async def test_upload_file_failure(mock_process_uploaded_file, client: AsyncClient):
    test_file_path = "test_upload.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test file.")

    with open(test_file_path, "rb") as f:
        response = await client.post(
            "/api/upload-file",
            files={"file": ("test_upload.txt", f, "text/plain")}
        )

    os.remove(test_file_path)

    assert response.status_code == 500
    assert response.json() == {"detail": "File processing error"}
    mock_process_uploaded_file.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.process_base64_image')
async def test_upload_photo_success(mock_process_base64_image, client: AsyncClient):
    mock_process_base64_image.return_value = "Extracted text from image."

    response = await client.post("/api/upload-photo", json={
        "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    })

    assert response.status_code == 200
    assert response.json() == {"success": True, "content": "Extracted text from image."}
    mock_process_base64_image.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.process_base64_image', side_effect=Exception("Image processing error"))
async def test_upload_photo_failure(mock_process_base64_image, client: AsyncClient):
    response = await client.post("/api/upload-photo", json={
        "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    })

    assert response.status_code == 500
    assert response.json() == {"detail": "Image processing error"}
    mock_process_base64_image.assert_called_once()


@pytest.mark.asyncio
@patch('web_app.list_local_subscriptions')
async def test_check_subscription_dev_mode_active(mock_list_local_subscriptions, client: AsyncClient):
    original_dev_mode = web_app._dev_mode
    web_app._dev_mode = True  # Temporarily set _dev_mode to True

    mock_list_local_subscriptions.return_value = [
        {"id": "sub_123", "status": "active", "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"}
    ]

    response = await client.get("/api/check-subscription")

    assert response.status_code == 200
    assert response.json()["has_subscription"] is True
    assert response.json()["subscription_id"] == "sub_123"

    web_app._dev_mode = original_dev_mode  # Restore original _dev_mode


@pytest.mark.asyncio
@patch('web_app.list_local_subscriptions')
async def test_check_subscription_dev_mode_expired(mock_list_local_subscriptions, client: AsyncClient):
    original_dev_mode = web_app._dev_mode
    web_app._dev_mode = True  # Temporarily set _dev_mode to True

    mock_list_local_subscriptions.return_value = [
        {"id": "sub_123", "status": "active", "expires_at": (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"}
    ]

    response = await client.get("/api/check-subscription")

    assert response.status_code == 200
    assert response.json()["has_subscription"] is False

    web_app._dev_mode = original_dev_mode  # Restore original _dev_mode


@pytest.mark.asyncio
@patch('web_app.list_local_subscriptions')
async def test_check_subscription_dev_mode_no_subscription(mock_list_local_subscriptions, client: AsyncClient):
    original_dev_mode = web_app._dev_mode
    web_app._dev_mode = True  # Temporarily set _dev_mode to True

    mock_list_local_subscriptions.return_value = []

    response = await client.get("/api/check-subscription")

    assert response.status_code == 200
    assert response.json()["has_subscription"] is False

    web_app._dev_mode = original_dev_mode  # Restore original _dev_mode


@pytest.mark.asyncio
@patch('web_app.stripe.Subscription.list')
async def test_check_subscription_prod_mode_active(mock_stripe_subscription_list, client: AsyncClient):
    original_dev_mode = web_app._dev_mode
    web_app._dev_mode = False  # Temporarily set _dev_mode to False

    mock_sub = MagicMock()
    mock_sub.id = "sub_prod_123"
    mock_sub.status = "active"
    mock_stripe_subscription_list.return_value.data = [mock_sub]

    response = await client.get("/api/check-subscription")

    assert response.status_code == 200
    assert response.json()["has_subscription"] is True
    assert response.json()["subscription_id"] == "sub_prod_123"

    web_app._dev_mode = original_dev_mode  # Restore original _dev_mode


@pytest.mark.asyncio
@patch('web_app.stripe.Subscription.list')
async def test_check_subscription_prod_mode_inactive(mock_stripe_subscription_list, client: AsyncClient):
    original_dev_mode = web_app._dev_mode
    web_app._dev_mode = False  # Temporarily set _dev_mode to False

    mock_stripe_subscription_list.return_value.data = []  # No active subscriptions

    response = await client.get("/api/check-subscription")

    assert response.status_code == 200
    assert response.json()["has_subscription"] is False

    web_app._dev_mode = original_dev_mode  # Restore original _dev_mode


# Test for _split_homework_into_questions utility function
def test_split_homework_into_questions_numbered():
    homework_content = "1. Question one.\n2. Question two.\n3. Question three."
    subject = "Maths"

    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 3
    assert questions[0]["content"] == "1. Question one."
    assert questions[1]["content"] == "2. Question two."
    assert questions[2]["content"] == "3. Question three."
    assert all("question_id" in q for q in questions)
    assert all("original_full_content" in q for q in questions)


def test_split_homework_into_questions_bullet_points():
    homework_content = "- First question\n* Second question\n- Third question"
    subject = "English"
    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 3
    assert questions[0]["content"] == "- First question"
    assert questions[1]["content"] == "* Second question"
    assert questions[2]["content"] == "- Third question"
    assert all("question_id" in q for q in questions)


def test_split_homework_into_questions_mixed_content():
    homework_content = "Introduction.\n1. First question.\nSome text.\n2. Second question."
    subject = "Science"
    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 4  # Introduction, Q1, Some text, Q2
    assert questions[0]["content"] == "Introduction."
    assert questions[1]["content"] == "1. First question."
    assert questions[2]["content"] == "Some text."
    assert questions[3]["content"] == "2. Second question."
    assert all("question_id" in q for q in questions)


def test_split_homework_into_questions_single_block():
    homework_content = "This is a single block of text with no clear question numbering or bullet points."
    subject = "History"
    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 1
    assert questions[0]["content"] == homework_content
    assert all("question_id" in q for q in questions)


def test_split_homework_into_questions_empty():
    homework_content = ""
    subject = "Art"
    questions = _split_homework_into_questions(homework_content, subject)
    assert len(questions) == 0


def test_split_homework_into_questions_multi_line_numbered():
    homework_content = "1. This is the first question.\nIt spans multiple lines.\n2. Second question here."
    subject = "Geography"
    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 2
    assert "1. This is the first question.\nIt spans multiple lines." in questions[0]["content"]
    assert "2. Second question here." in questions[1]["content"]


def test_split_homework_into_questions_with_sub_points():
    homework_content = "1. Main question.\n   a. Sub-point one.\n   b. Sub-point two.\n2. Another main question."
    subject = "Maths"
    questions = _split_homework_into_questions(homework_content, subject)

    # The current regex might split "a." and "b." as new questions if not careful.
    # Let's refine the regex in _split_homework_into_questions if this test fails.
    # For now, expect it to group sub-points with the main question.
    assert len(questions) == 2
    assert "1. Main question.\n   a. Sub-point one.\n   b. Sub-point two." in questions[0]["content"]
    assert "2. Another main question." in questions[1]["content"]


def test_split_homework_into_questions_header_then_numbered():
    homework_content = "Maths Homework - Addition\n\n1. Add 5 and 3.\n2. Add 10 and 7."
    subject = "Maths"
    questions = _split_homework_into_questions(homework_content, subject)

    assert len(questions) == 3  # Expecting header, then two questions
    assert "Maths Homework - Addition" in questions[0]["content"]
    assert "1. Add 5 and 3." in questions[1]["content"]
    assert "2. Add 10 and 7." in questions[2]["content"]

