from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.elevenplus import rebuild_all_elevenplus as rebuild

pytestmark = pytest.mark.unit


def test_registry_covers_all_three_pages_and_four_subjects() -> None:
    specs = rebuild.discover_generators()

    assert len(specs) == 12
    assert {spec.family for spec in specs} == {"practice", "topic_mastery", "year_round"}
    assert all(sum(item.family == family for item in specs) == 4 for family in {
        "practice", "topic_mastery", "year_round",
    })
    assert rebuild._expected_total(specs, None) == 2528


def test_list_generators_does_not_open_the_database(monkeypatch, capsys) -> None:
    import src.elevenplus_rag as rag

    monkeypatch.setattr(
        rag,
        "get_elevenplus_rag_store",
        lambda: (_ for _ in ()).throw(AssertionError("list mode must not open RAG")),
    )

    assert rebuild.main(["--list-generators"]) == 0
    output = capsys.readouterr().out
    assert "practice: Maths -> elevenplus_math_generator.py" in output
    assert "topic_mastery: English -> elevenplus_english_topic_mastery_generator.py" in output
    assert "year_round: Non-Verbal Reasoning -> elevenplus_nvr_year_round_plan_generator.py" in output
    assert "static/elevenplus-topic-mastery.html" in output


def test_clean_deletes_only_the_dedicated_elevenplus_collection() -> None:
    class Backend:
        def __init__(self):
            self.records = 19
            self.filters = []

        def count(self):
            return self.records

        def delete_by_metadata(self, filters):
            self.filters.append(filters)
            deleted = self.records
            self.records = 0
            return deleted

    backend = Backend()
    deleted = rebuild._delete_elevenplus_collection(SimpleNamespace(store=backend))

    assert deleted == 19
    assert backend.filters == [{}]


@pytest.mark.parametrize(
    ("module_name", "builder_name", "subject"),
    [
        ("scripts.elevenplus.elevenplus_math_generator", "generate_11plus_batch", "Maths"),
        ("scripts.elevenplus.elevenplus_english_generator", "generate_11plus_english_batch", "English"),
        ("scripts.elevenplus.elevenplus_vr_generator", "generate_11plus_vr_batch", "VerbalReasoning"),
        ("scripts.elevenplus.elevenplus_nvr_generator", "generate_11plus_nvr_batch", "NonVerbalReasoning"),
    ],
)
def test_ordinary_generators_mark_records_as_practice(module_name, builder_name, subject) -> None:
    module = __import__(module_name, fromlist=[builder_name])
    batch = getattr(module, builder_name)(count=1)

    assert len(batch) == 1
    assert batch[0]["metadata"]["year_group"] == 6
    assert batch[0]["metadata"]["subject"] == subject
    assert batch[0]["metadata"]["content_type"] == "practice"
    assert batch[0]["metadata"]["correct_answers"]


def test_general_count_override_changes_only_practice_total() -> None:
    specs = rebuild.discover_generators()
    # 4 ordinary sets + 220 mastery sets + 208 year-round sets.
    assert rebuild._expected_total(specs, 1) == 432

