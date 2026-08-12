from __future__ import annotations

import importlib


def test_school_report_acknowledge_excludes_and_reject_does_not(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCOUNT_DB_PATH", str(tmp_path / "accounts.db"))
    mod = importlib.import_module("src.webapp.school_finder_exclusions")
    mod._ENGINE = None
    mod._ENGINE_URL = None

    pending = mod.create_school_report(
        source_id="osm:node:123",
        name="Example Academy",
        latitude=51.5,
        longitude=-0.1,
        reason="This is a primary school",
    )
    assert pending["status"] == "pending"
    assert mod.list_school_reports("pending")[0]["report_id"] == pending["report_id"]

    reviewed = mod.review_school_report(
        report_id=pending["report_id"],
        action="acknowledge",
        reviewed_by="admin@example.com",
        review_note="Verified against the school record.",
    )
    assert reviewed["status"] == "acknowledged"
    assert mod.is_school_excluded(
        source_id="osm:node:123", name="Example Academy", latitude=51.5, longitude=-0.1
    )

    pending2 = mod.create_school_report(
        source_id="osm:node:456",
        name="Another School",
        latitude=51.51,
        longitude=-0.11,
        reason="This is not secondary",
    )
    reviewed2 = mod.review_school_report(
        report_id=pending2["report_id"],
        action="reject",
        reviewed_by="admin@example.com",
    )
    assert reviewed2["status"] == "rejected"
    assert not mod.is_school_excluded(
        source_id="osm:node:456", name="Another School", latitude=51.51, longitude=-0.11
    )
