from __future__ import annotations

import re
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

EXPECTED_REQUIRES_PYTHON = ">=3.11"
EXPECTED_CI_TESTED_PYTHON_VERSIONS = ["3.11", "3.12"]
EXPECTED_PYTHON_CLASSIFIERS = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
EXPECTED_SOURCE_FLOOR_DOC = "Package metadata declares Python 3.11+"
EXPECTED_TESTED_VERSION_DOC = (
    "CI-supported and tested Python versions are currently 3.11 and 3.12"
)
EXPECTED_NEW_MINOR_DOC = (
    "New Python minor versions should be added to the CI matrix, package "
    "classifiers, and support-policy docs together before being described as "
    "CI-supported."
)


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _ci_test_matrix_python_versions() -> list[str]:
    workflow_text = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    test_job_match = re.search(
        r"jobs:\n  test:.*?python-version:\n(?P<versions>(?:          - \"[^\"]+\"\n)+)",
        workflow_text,
        flags=re.DOTALL,
    )
    assert test_job_match is not None
    return re.findall(r'- "([^"]+)"', test_job_match.group("versions"))


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def test_python_metadata_distinguishes_source_floor_from_tested_versions() -> None:
    pyproject = _load_pyproject()
    project = pyproject["project"]

    assert project["requires-python"] == EXPECTED_REQUIRES_PYTHON
    assert project["classifiers"] == EXPECTED_PYTHON_CLASSIFIERS


def test_ci_python_matrix_tracks_supported_tested_versions() -> None:
    assert _ci_test_matrix_python_versions() == EXPECTED_CI_TESTED_PYTHON_VERSIONS


def test_python_support_policy_docs_track_metadata_and_ci() -> None:
    docs_by_path = {
        path: path.read_text(encoding="utf-8")
        for path in [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "architecture.md",
            PROJECT_ROOT / "docs" / "testing_and_quality.md",
            PROJECT_ROOT
            / "docs"
            / "decisions"
            / "0003-baseline-dependency-policy.md",
        ]
    }

    for text in docs_by_path.values():
        compact_text = _compact_whitespace(text)
        assert EXPECTED_SOURCE_FLOOR_DOC in compact_text
        assert EXPECTED_TESTED_VERSION_DOC in compact_text
        assert EXPECTED_NEW_MINOR_DOC in compact_text
