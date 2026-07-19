from __future__ import annotations

import pytest

from scripts.homework_generator import rebuild_all_homework as rebuild

pytestmark = pytest.mark.unit


def test_discovers_every_primary_subject_generator() -> None:
    from src.models import UK_PRIMARY_SUBJECTS

    specs = rebuild.discover_generators()

    assert {spec.subject for spec in specs} == set(UK_PRIMARY_SUBJECTS)
    assert len({spec.module_name for spec in specs}) == len(specs)
    assert all(spec.file_name.startswith("homework_") for spec in specs)


def test_list_generators_does_not_open_rag(monkeypatch, capsys) -> None:
    import src.homework_rag as homework_rag

    monkeypatch.setattr(
        homework_rag,
        "get_homework_rag_store",
        lambda: (_ for _ in ()).throw(AssertionError("list mode must not open the database")),
    )

    assert rebuild.main(["--list-generators"]) == 0
    output = capsys.readouterr().out
    assert "Maths: homework_math_generator.py" in output
    assert "PSHE: homework_pshe_generator.py" in output


def test_delete_primary_years_uses_year_filters_only() -> None:
    class Backend:
        def __init__(self):
            self.filters = []

        def delete_by_metadata(self, filters):
            self.filters.append(filters)
            return 3

    backend = Backend()
    store = type("Store", (), {"store": backend})()

    deleted = rebuild._delete_primary_years(store)

    assert deleted == 18
    assert backend.filters == [{"year_group": year} for year in range(1, 7)]


def test_subject_filter_requires_a_matching_generator() -> None:
    specs = rebuild.discover_generators()

    selected = rebuild._selected_generators(specs, ["German", "music"])

    assert {spec.subject for spec in selected} == {"German", "Music"}
    with pytest.raises(ValueError, match="Unknown primary subject"):
        rebuild._selected_generators(specs, ["Cryptocurrency"])

