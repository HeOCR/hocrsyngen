from __future__ import annotations

import ast
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "hocrsyngen"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

EXPECTED_BASELINE_DEPENDENCIES = {"jsonschema", "pillow"}
EXPECTED_TEST_EXTRA_DEPENDENCIES = {"pytest"}

FORBIDDEN_IMPORT_GROUPS = {
    "hocrgen": {
        "hocrgen",
    },
    "network_or_rest": {
        "aiohttp",
        "boto3",
        "botocore",
        "ftplib",
        "grpc",
        "http",
        "httpx",
        "requests",
        "socket",
        "smtplib",
        "urllib",
        "websocket",
        "websockets",
    },
    "gpu_llm_or_deep_learning": {
        "accelerate",
        "diffusers",
        "jax",
        "keras",
        "langchain",
        "llama_cpp",
        "mlx",
        "ollama",
        "openai",
        "tensorflow",
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
    },
}


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _dependency_name(requirement: str) -> str:
    name = requirement.split(";", 1)[0].split("[", 1)[0].strip()
    normalized = []
    for character in name:
        if character.isalnum() or character in "._-":
            normalized.append(character)
        else:
            break
    return "".join(normalized).lower().replace("_", "-")


def _dependency_names(requirements: list[str]) -> set[str]:
    return {_dependency_name(requirement) for requirement in requirements}


def _source_imports() -> dict[Path, set[str]]:
    imports_by_path: dict[Path, set[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)
        imports_by_path[path] = imports
    return imports_by_path


def _top_level_module(import_name: str) -> str:
    return import_name.split(".", 1)[0]


def test_pyproject_baseline_dependency_sets_are_intentional() -> None:
    pyproject = _load_pyproject()

    baseline_dependencies = _dependency_names(pyproject["project"]["dependencies"])
    test_extra_dependencies = _dependency_names(
        pyproject["project"]["optional-dependencies"]["test"]
    )

    assert baseline_dependencies == EXPECTED_BASELINE_DEPENDENCIES
    assert test_extra_dependencies == EXPECTED_TEST_EXTRA_DEPENDENCIES


def test_baseline_source_imports_do_not_cross_repository_or_dependency_boundaries() -> None:
    forbidden_imports = {
        group: {
            path.relative_to(PROJECT_ROOT).as_posix(): sorted(
                import_name
                for import_name in imports
                if _top_level_module(import_name) in forbidden_top_level_modules
            )
            for path, imports in _source_imports().items()
            if any(
                _top_level_module(import_name) in forbidden_top_level_modules
                for import_name in imports
            )
        }
        for group, forbidden_top_level_modules in FORBIDDEN_IMPORT_GROUPS.items()
    }

    assert forbidden_imports == {
        "hocrgen": {},
        "network_or_rest": {},
        "gpu_llm_or_deep_learning": {},
    }


def test_dependency_policy_docs_track_pyproject_baseline_dependencies() -> None:
    pyproject = _load_pyproject()
    baseline_dependencies = pyproject["project"]["dependencies"]
    test_extra_dependencies = pyproject["project"]["optional-dependencies"]["test"]
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

    assert all(
        _dependency_name(requirement) in architecture_doc.lower()
        for requirement in baseline_dependencies
    )
    assert all(
        _dependency_name(requirement) in repository_scope_doc.lower()
        for requirement in baseline_dependencies
    )
    assert all(
        _dependency_name(requirement) in testing_doc.lower()
        for requirement in test_extra_dependencies
    )
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
