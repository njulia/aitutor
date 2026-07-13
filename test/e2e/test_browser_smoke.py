from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@pytest.fixture(autouse=True)
def require_e2e_enabled():
    if os.getenv("RUN_E2E", "0").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_E2E=1 and start the website to run browser tests")


def test_homepage_and_app_load(page: Page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    expect(page).to_have_title(re.compile("Homework"))
    expect(page.get_by_text("Homework Magic").first).to_be_visible()

    page.goto(f"{BASE_URL}/app", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("Generate Homework")


def test_no_public_script_cdn_on_learner_pages(page: Page) -> None:
    requested_hosts: set[str] = set()

    def record_request(request):
        if request.resource_type == "script":
            requested_hosts.add(request.url.split("/", 3)[2])

    page.on("request", record_request)
    page.goto(f"{BASE_URL}/app", wait_until="networkidle")
    assert requested_hosts <= {BASE_URL.split("//", 1)[1]}


def test_shared_renderer_handles_primary_and_elevenplus_choice_questions(page: Page) -> None:
    page.goto(f"{BASE_URL}/app", wait_until="networkidle")
    page.evaluate(
        """
        displayHomework([{
          subject: 'Maths',
          content: '1. What is 2 + 2?\\nA) 3\\nB) 4\\n2. Write the next number after 9.',
          questions: [
            {number: 1, question: 'What is 2 + 2?', response_type: 'single_choice', options: [
              {label: 'A', text: '3'}, {label: 'B', text: '4'}
            ]},
            {number: 2, question: 'Write the next number after 9.', response_type: 'text', options: []}
          ],
          doc_id: 'year_1_mixed',
          from_rag: true,
          is_eleven_plus: false
        }]);
        """
    )

    expect(page.locator('.multiple-choice-input')).to_have_count(2)
    expect(page.locator('.question-response-input')).to_have_count(1)
    page.locator('.multiple-choice-input').nth(1).check()
    page.locator('.question-response-input').fill('10')
    expect(page.locator('.question-answer-proxy')).to_have_value('1. 4\n2. 10')

    page.evaluate(
        """
        displayHomework([{
          subject: 'Verbal Reasoning',
          content: '1. Choose the opposite of ANCIENT.\\nA) old\\nB) modern',
          questions: [{number: 1, question: 'Choose the opposite of ANCIENT.', options: [
            {label: 'A', text: 'old'}, {label: 'B', text: 'modern'}
          ]}],
          doc_id: 'elevenplus_vr',
          from_rag: true,
          is_eleven_plus: true
        }]);
        """
    )
    expect(page.locator('.multiple-choice-input')).to_have_count(2)
    expect(page.locator('.answer-column textarea:not([hidden])')).to_have_count(0)
