from pathlib import Path

from src.webapp.runtime import is_30_day_study_plan_enabled


def test_30_day_study_plan_flag_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_11PLUS_30_DAY_STUDY_PLAN", raising=False)
    assert is_30_day_study_plan_enabled() is False


def test_30_day_study_plan_flag_accepts_common_true_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ENABLE_11PLUS_30_DAY_STUDY_PLAN", value)
        assert is_30_day_study_plan_enabled() is True


def test_30_day_study_plan_flag_accepts_false_values(monkeypatch):
    for value in ("0", "false", "no", "off", "anything-else"):
        monkeypatch.setenv("ENABLE_11PLUS_30_DAY_STUDY_PLAN", value)
        assert is_30_day_study_plan_enabled() is False


def test_deploy_scripts_default_the_flag_to_off():
    for name in ("deploy_code_gcp.sh", "deploy_gcp.sh"):
        text = Path("deploy", name).read_text(encoding="utf-8")
        assert 'ENABLE_11PLUS_30_DAY_STUDY_PLAN="${ENABLE_11PLUS_30_DAY_STUDY_PLAN:-false}"' in text
