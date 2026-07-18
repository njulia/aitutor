from __future__ import annotations

from src.progress_db import save_homework_session


def test_logged_in_client_id_is_account_owned_learner(authenticated_client, app_module, monkeypatch) -> None:
    account = authenticated_client.get('/api/account')
    assert account.status_code == 200
    learners = account.json()['students']
    default = next((item for item in learners if item['is_default']), learners[0])

    identity = authenticated_client.get('/api/client-id')
    assert identity.status_code == 200
    assert identity.json()['client_id'] == default['id']
    assert '@' not in identity.json()['client_id']

    save_homework_session(
        student_id=default['id'],
        subject='Maths',
        year_group=3,
        homework_content='1. 2 + 2',
        student_answers='4',
        score=1,
        max_score=1,
        review_text='Correct',
    )
    monkeypatch.setattr(app_module, 'user_has_subscription', lambda *args, **kwargs: True)

    # This is the route used by static/progress.html. It must resolve the
    # signed-in account's default learner without requiring JavaScript to know
    # or expose the learner ID.
    default_progress = authenticated_client.get('/api/progress')
    assert default_progress.status_code == 200, default_progress.text
    default_body = default_progress.json()
    assert default_body['summary']['overall']['avg_accuracy'] == 100.0

    # Keep the explicit learner route for multi-learner family accounts and
    # existing API clients.
    progress = authenticated_client.get(f"/api/progress/{default['id']}")
    assert progress.status_code == 200, progress.text
    body = progress.json()
    assert body['summary']['overall']['avg_accuracy'] == 100.0

    forbidden = authenticated_client.get('/api/progress/student_not_owned')
    assert forbidden.status_code == 403
