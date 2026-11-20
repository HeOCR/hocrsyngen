from __future__ import annotations

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
CANONICAL_POLICY_PATH = PROJECT_ROOT / "docs" / "testing_and_quality.md"
CANONICAL_POLICY_REFERENCE = "docs/testing_and_quality.md"


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _ci_test_matrix_python_versions() -> list[str]:
    workflow_lines = CI_WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    test_job_index = next(
        (
            index
            for index, line in enumerate(workflow_lines)
            if line == "  test:"
        ),
        None,
    )
    assert test_job_index is not None, (
        f"{CI_WORKFLOW_PATH.relative_to(PROJECT_ROOT)} must define a test job."
    )

    test_job_lines: list[str] = []
    for line in workflow_lines[test_job_index + 1 :]:
        if line and _leading_spaces(line) <= 2:
            break
        test_job_lines.append(line)

    python_version_line_index = next(
        (
            index
            for index, line in enumerate(test_job_lines)
            if line.strip() == "python-version:"
        ),
        None,
    )
    assert python_version_line_index is not None, (
        f"{CI_WORKFLOW_PATH.relative_to(PROJECT_ROOT)} must declare a "
        "python-version matrix list for the test job."
    )

    versions: list[str] = []
    for line in test_job_lines[python_version_line_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            break
        versions.append(stripped.removeprefix("- ").strip("\"'"))

    assert versions, (
        f"{CI_WORKFLOW_PATH.relative_to(PROJECT_ROOT)} python-version matrix "
        "must list supported/tested Python versions."
    )
    return versions


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def test_python_metadata_distinguishes_source_floor_from_tested_versions() -> None:
    pyproject = _load_pyproject()
    project = pyproject["project"]
    python_classifiers = [
        classifier
        for classifier in project["classifiers"]
        if classifier.startswith("Programming Language :: Python")
    ]

    assert project["requires-python"] == EXPECTED_REQUIRES_PYTHON
    assert python_classifiers == EXPECTED_PYTHON_CLASSIFIERS


def test_ci_python_matrix_tracks_supported_tested_versions() -> None:
    assert _ci_test_matrix_python_versions() == EXPECTED_CI_TESTED_PYTHON_VERSIONS


def test_python_support_policy_docs_track_metadata_and_ci() -> None:
    canonical_policy = _compact_whitespace(
        CANONICAL_POLICY_PATH.read_text(encoding="utf-8")
    )
    assert EXPECTED_SOURCE_FLOOR_DOC in canonical_policy
    assert EXPECTED_TESTED_VERSION_DOC in canonical_policy
    assert EXPECTED_NEW_MINOR_DOC in canonical_policy

    for path in [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "architecture.md",
        PROJECT_ROOT / "docs" / "decisions" / "0003-baseline-dependency-policy.md",
    ]:
        assert CANONICAL_POLICY_REFERENCE in path.read_text(encoding="utf-8")
