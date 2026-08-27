from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_homepage_and_app_load(page: Page, e2e_base_url: str) -> None:
    page.goto(e2e_base_url, wait_until="domcontentloaded")
    expect(page).to_have_title(re.compile("Homework"))
    expect(page.get_by_text("Homework Magic").first).to_be_visible()

    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("Plan today’s homework with me")


def test_no_public_script_cdn_on_learner_pages(page: Page, e2e_base_url: str) -> None:
    requested_urls: list[str] = []
    page.on("request", lambda request: requested_urls.append(request.url))
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    page.wait_for_function("typeof displayHomework === 'function'")

    script_hosts = {
        urlparse(url).netloc
        for url in requested_urls
        if urlparse(url).path.endswith(".js")
    }
    assert script_hosts <= {urlparse(e2e_base_url).netloc}


def test_shared_renderer_handles_primary_and_elevenplus_choice_questions(
    page: Page, e2e_base_url: str
) -> None:
    page.goto(f"{e2e_base_url}/app", wait_until="domcontentloaded")
    page.wait_for_function("typeof displayHomework === 'function'")
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

    expect(page.locator(".multiple-choice-input")).to_have_count(2)
    expect(page.locator(".question-response-input")).to_have_count(1)
    page.locator(".multiple-choice-option").nth(1).click()
    page.locator(".question-response-input").fill("10")
    expect(page.locator(".question-answer-proxy")).to_have_value("1. 4\n2. 10")

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
    expect(page.locator(".multiple-choice-input")).to_have_count(2)
    expect(page.locator(".answer-column textarea:not([hidden])")).to_have_count(0)
