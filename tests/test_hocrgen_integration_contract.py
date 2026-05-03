from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path, PurePosixPath


FIXTURE_ID = "generation_manifest_v1_fixture_batch"


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _json_output(completed: subprocess.CompletedProcess[str]) -> dict:
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def _assert_valid_validation_report(
    payload: dict,
    *,
    path: Path,
    sample_count: int,
    page_count: int,
) -> None:
    assert payload["schema_version"] == "validation_report.v1"
    assert payload["valid"] is True
    assert payload["sample_count"] == sample_count
    assert payload["page_count"] == page_count
    assert payload["path"] == str(path)


def test_hocrgen_adapter_contract_uses_public_installed_cli_json_boundary(
    installed_package: tuple[Path, Path, dict[str, str]],
    tmp_path: Path,
) -> None:
    target_dir, isolated_cwd, env = installed_package
    executable = str(target_dir / "bin" / "hocrsyngen")

    templates = _json_output(
        _run([executable, "templates", "--format", "json"], cwd=isolated_cwd, env=env)
    )
    assert templates["schema_version"] == "template_catalog.v1"
    assert isinstance(templates["templates"], list)
    assert {entry["template_id"] for entry in templates["templates"]} >= {
        "printed_letter",
        "handwritten_note",
    }
    for entry in templates["templates"]:
        assert {
            "template_id",
            "recipe_id",
            "layout_style",
            "font_style",
            "font_id",
            "degradation_preset",
        } <= set(entry)

    contracts = _json_output(
        _run([executable, "contracts", "--format", "json"], cwd=isolated_cwd, env=env)
    )
    assert contracts["schema_version"] == "contract_fixture_catalog.v1"
    [fixture] = [
        fixture
        for fixture in contracts["fixtures"]
        if fixture["fixture_id"] == FIXTURE_ID
    ]
    assert fixture["contract"] == "generation_manifest.v1"
    assert fixture["sample_count"] == 2
    assert fixture["page_count"] == 2
    assert fixture["manifest_resource_path"].endswith("generation_manifest.json")

    exported_fixture_dir = tmp_path / "exported-fixture"
    fixture_export = _json_output(
        _run(
            [
                executable,
                "contracts",
                "export",
                "--fixture-id",
                FIXTURE_ID,
                "--output",
                str(exported_fixture_dir),
                "--format",
                "json",
            ],
            cwd=isolated_cwd,
            env=env,
        )
    )
    assert fixture_export["schema_version"] == "contract_fixture_export.v1"
    assert fixture_export["fixture_id"] == FIXTURE_ID
    assert fixture_export["contract"] == "generation_manifest.v1"
    assert fixture_export["sample_count"] == 2
    assert fixture_export["page_count"] == 2
    assert fixture_export["output_path"] == str(exported_fixture_dir)
    assert fixture_export["manifest_path"] == str(
        exported_fixture_dir / "generation_manifest.json"
    )
    exported_manifest_path = exported_fixture_dir / "generation_manifest.json"
    assert exported_manifest_path.is_file()
    exported_manifest = json.loads(exported_manifest_path.read_text(encoding="utf-8"))
    for sample in exported_manifest["samples"]:
        for page in sample["pages"]:
            asset_path = PurePosixPath(page["asset_path"])
            assert not asset_path.is_absolute()
            assert ".." not in asset_path.parts
            assert "\\" not in page["asset_path"]
            assert (exported_fixture_dir / Path(*asset_path.parts)).is_file()

    exported_validation = _json_output(
        _run(
            [executable, "validate", str(exported_fixture_dir), "--format", "json"],
            cwd=isolated_cwd,
            env=env,
        )
    )
    _assert_valid_validation_report(
        exported_validation,
        path=exported_fixture_dir,
        sample_count=2,
        page_count=2,
    )

    generated_dir = tmp_path / "generated-batch"
    generation = _json_output(
        _run(
            [
                executable,
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(generated_dir),
                "--format",
                "json",
            ],
            cwd=isolated_cwd,
            env=env,
        )
    )
    assert generation["schema_version"] == "generation_report.v1"
    assert generation["sample_count"] == 2
    assert generation["page_count"] >= generation["sample_count"]
    assert generation["output_path"] == str(generated_dir)
    assert generation["manifest_path"] == str(
        generated_dir / "generation_manifest.json"
    )

    generated_validation = _json_output(
        _run(
            [executable, "validate", str(generated_dir), "--format", "json"],
            cwd=isolated_cwd,
            env=env,
        )
    )
    _assert_valid_validation_report(
        generated_validation,
        path=generated_dir,
        sample_count=2,
        page_count=generation["page_count"],
    )


def test_hocrgen_adapter_contract_invalid_validation_reports_json_nonzero(
    installed_package: tuple[Path, Path, dict[str, str]],
    tmp_path: Path,
) -> None:
    target_dir, isolated_cwd, env = installed_package
    executable = str(target_dir / "bin" / "hocrsyngen")
    invalid_dir = tmp_path / "missing-manifest"
    invalid_dir.mkdir()

    completed = _run(
        [
            executable,
            "validate",
            str(invalid_dir),
            "--format",
            "json",
        ],
        cwd=isolated_cwd,
        env=env,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    invalid_validation = json.loads(completed.stdout)
    assert invalid_validation["schema_version"] == "validation_report.v1"
    assert invalid_validation["valid"] is False
    assert invalid_validation["path"] == str(invalid_dir)
    assert invalid_validation["error"] == (
        f"Missing manifest: {invalid_dir / 'generation_manifest.json'}"
    )


def test_hocrgen_adapter_contract_tests_do_not_import_private_boundaries() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert "hocrgen" not in imported_modules
    assert not any(
        module == "hocrsyngen" or module.startswith("hocrsyngen.")
        for module in imported_modules
    )
