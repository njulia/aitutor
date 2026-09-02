from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_parent_can_read_and_change_learning_summary_preferences(authenticated_client) -> None:
    response = authenticated_client.get('/api/parent/learning-summary/preferences')
    assert response.status_code == 200, response.text
    assert response.json()['preferences']['frequency'] == 'weekly'

    updated = authenticated_client.put(
        '/api/parent/learning-summary/preferences',
        json={'enabled': True, 'frequency': 'custom', 'interval_days': 14},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['preferences']['frequency'] == 'custom'
    assert updated.json()['preferences']['interval_days'] == 14

    unsubscribed = authenticated_client.put(
        '/api/parent/learning-summary/preferences',
        json={'enabled': False, 'frequency': 'weekly', 'interval_days': 7},
    )
    assert unsubscribed.status_code == 200, unsubscribed.text
    assert unsubscribed.json()['preferences']['enabled'] is False
    assert unsubscribed.json()['preferences']['next_send_at'] is None
