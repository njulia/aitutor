from src.webapp.school_finder_routes import _is_secondary_school


def test_sparse_secondary_academy_is_found_without_phase_tags():
    assert _is_secondary_school({"name": "Chobham Academy"}) is True


def test_primary_academy_is_not_promoted_to_secondary():
    assert _is_secondary_school({"name": "Example Primary Academy"}) is False
    assert _is_secondary_school({"name": "Example Academy", "school:level": "primary"}) is False


def test_explicit_secondary_still_wins():
    assert _is_secondary_school({"name": "Example School", "school:level": "secondary"}) is True
