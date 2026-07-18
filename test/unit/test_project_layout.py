from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_test_and_documentation_directories_are_present() -> None:
    assert (ROOT / "test" / "unit").is_dir()
    assert (ROOT / "test" / "api").is_dir()
    assert (ROOT / "test" / "integration").is_dir()
    assert (ROOT / "test" / "e2e").is_dir()
    assert (ROOT / "doc").is_dir()


def test_required_test_documents_exist() -> None:
    required = {
        "README.md",
        "TESTING.md",
        "END_TO_END_TESTING.md",
        "TEST_PLAN.md",
        "CI_CD.md",
        "PRIVACY_SAFETY_TESTING.md",
    }
    assert required <= {path.name for path in (ROOT / "doc").glob("*.md")}


def test_github_actions_uses_real_test_directory_and_enables_e2e() -> None:
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "pytest test/unit test/api test/integration" in workflow
    assert "pytest test/e2e" in workflow
    assert 'RUN_E2E: "1"' in workflow
    assert "pytest tests/" not in workflow
