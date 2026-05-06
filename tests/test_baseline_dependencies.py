from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "hocrsyngen"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

EXPECTED_BASELINE_REQUIREMENTS = ["jsonschema>=4", "Pillow>=10"]
EXPECTED_TEST_EXTRA_REQUIREMENTS = ["pytest>=8"]
EXPECTED_RUNTIME_IMPORT_MODULES = {
    "jsonschema",
    "PIL",
}
EXPECTED_REPOSITORY_SCOPE_POLICY = (
    "The baseline dependencies are `jsonschema` and `Pillow`; test dependencies "
    "add `pytest`."
)
EXPECTED_ADR_POLICY = (
    "The accepted baseline runtime dependencies are `jsonschema` and `Pillow`; "
    "the accepted test extra dependency is `pytest`."
)
EXPECTED_TESTING_POLICY = (
    "Baseline dependency policy remains aligned across source imports, "
    "`pyproject.toml`, and dependency-policy docs."
)

def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _source_top_level_imports() -> dict[Path, set[str]]:
    imports_by_path: dict[Path, set[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(_top_level_module(alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue
                if node.module is not None:
                    imports.add(_top_level_module(node.module))
        imports_by_path[path] = imports
    return imports_by_path


def _top_level_module(import_name: str) -> str:
    return import_name.split(".", 1)[0]


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def test_pyproject_baseline_dependency_sets_are_intentional() -> None:
    pyproject = _load_pyproject()

    baseline_dependencies = pyproject["project"]["dependencies"]
    test_extra_dependencies = pyproject["project"]["optional-dependencies"]["test"]

    assert baseline_dependencies == EXPECTED_BASELINE_REQUIREMENTS
    assert test_extra_dependencies == EXPECTED_TEST_EXTRA_REQUIREMENTS


def test_baseline_source_imports_do_not_cross_repository_or_dependency_boundaries() -> None:
    allowed_imports = (
        sys.stdlib_module_names | {"hocrsyngen"} | EXPECTED_RUNTIME_IMPORT_MODULES
    )
    undeclared_imports = {
        path.relative_to(PROJECT_ROOT).as_posix(): sorted(imports - allowed_imports)
        for path, imports in _source_top_level_imports().items()
        if imports - allowed_imports
    }

    assert undeclared_imports == {}


def test_dependency_policy_docs_track_pyproject_baseline_dependencies() -> None:
    pyproject = _load_pyproject()
    baseline_dependencies = pyproject["project"]["dependencies"]
    test_extra_dependencies = pyproject["project"]["optional-dependencies"]["test"]
    assert baseline_dependencies == EXPECTED_BASELINE_REQUIREMENTS
    assert test_extra_dependencies == EXPECTED_TEST_EXTRA_REQUIREMENTS

    docs_by_path = {
        path: path.read_text(encoding="utf-8")
        for path in [
            PROJECT_ROOT / "docs" / "architecture.md",
            PROJECT_ROOT / "docs" / "repository_scope.md",
            PROJECT_ROOT / "docs" / "testing_and_quality.md",
            PROJECT_ROOT / "docs" / "decisions" / "0003-baseline-dependency-policy.md",
        ]
    }

    architecture_doc = docs_by_path[PROJECT_ROOT / "docs" / "architecture.md"]
    repository_scope_doc = docs_by_path[PROJECT_ROOT / "docs" / "repository_scope.md"]
    testing_doc = docs_by_path[PROJECT_ROOT / "docs" / "testing_and_quality.md"]
    dependency_policy_doc = docs_by_path[
        PROJECT_ROOT / "docs" / "decisions" / "0003-baseline-dependency-policy.md"
    ]

    assert "- `jsonschema` for manifest schema validation." in architecture_doc
    assert "- `Pillow` for image rendering and JPEG inspection." in architecture_doc
    assert EXPECTED_REPOSITORY_SCOPE_POLICY in repository_scope_doc
    assert EXPECTED_ADR_POLICY in dependency_policy_doc
    assert EXPECTED_TESTING_POLICY in _compact_whitespace(testing_doc)

    for forbidden_term in [
        "network",
        "gpu",
        "llm",
        "diffusion",
        "torch",
        "tensorflow",
        "deep-learning",
    ]:
        assert forbidden_term in dependency_policy_doc.lower()
