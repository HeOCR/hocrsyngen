from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from importlib import resources
from pathlib import Path, PurePosixPath

import jsonschema
import pytest

from hocrsyngen.cli import (
    CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION,
    CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION,
    EVIDENCE_RUN_REPORT_SCHEMA_VERSION,
    GENERATION_REPORT_SCHEMA_VERSION,
    RICH_TEMPLATE_CATALOG_SCHEMA_VERSION,
    TEMPLATE_CATALOG_SCHEMA_VERSION,
    VALIDATION_REPORT_SCHEMA_VERSION,
    _format_contract_fixture_catalog_json,
    _format_generation_report_json,
    _format_rich_template_catalog_json,
    _format_template_catalog_entry,
    _format_template_catalog_json,
    main,
)
from hocrsyngen.generator import (
    GOVERNED_TEMPLATE_IDS,
    RichTemplateCatalogEntry,
    SUPPORTED_CONDITION_BUNDLE_IDS,
    SUPPORTED_STYLE_BUNDLE_IDS,
    TemplateCapabilityMetadata,
    TemplateCatalogEntry,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.rendering_coverage import RENDERING_COVERAGE_REPORT_FILENAME
from hocrsyngen.validation import validate_batch
from hocrsyngen.validation import BatchValidationError, ValidationResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CATALOG_SCHEMA_PATH = (
    PROJECT_ROOT / "src" / "hocrsyngen" / "schemas" / "template_catalog.schema.json"
)


def _project_version() -> str:
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return pyproject["project"]["version"]


@pytest.fixture(scope="module")
def wheel_installed_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, Path, dict[str, str]]:
    tmp_path = tmp_path_factory.mktemp("wheel-installed-package")
    wheel_dir = tmp_path / "wheels"
    target_dir = tmp_path / "site"
    isolated_cwd = tmp_path / "isolated"
    wheel_dir.mkdir()
    isolated_cwd.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(PROJECT_ROOT),
        ],
        check=True,
        cwd=isolated_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wheels = sorted(wheel_dir.glob("hocrsyngen-*.whl"))
    assert len(wheels) == 1
    wheel_path = wheels[0]
    assert wheel_path.name == f"hocrsyngen-{_project_version()}-py3-none-any.whl"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target_dir),
            "--no-deps",
            str(wheel_path),
        ],
        check=True,
        cwd=isolated_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(target_dir)
    return wheel_path, target_dir, isolated_cwd, env


EXPECTED_TEMPLATE_LINES = [
    (
        "template_id=printed_letter "
        "recipe_id=printed_letter_form_v1 "
        "layout_style=printed_form "
        "font_style=printed "
        "font_id=alef-regular "
        "degradation_preset=office_scan_soft"
    ),
    (
        "template_id=handwritten_note "
        "recipe_id=handwritten_note_marginalia_v1 "
        "layout_style=handwritten_note "
        "font_style=handwritten_like "
        "font_id=gveret-levin-regular "
        "degradation_preset=notebook_scan_worn"
    ),
    (
        "template_id=archive_card "
        "recipe_id=archive_card_identifier_v1 "
        "layout_style=multi_region_page "
        "font_style=printed "
        "font_id=alef-regular "
        "degradation_preset=office_scan_soft"
    ),
    (
        "template_id=ledger "
        "recipe_id=ledger_table_v1 "
        "layout_style=tabular "
        "font_style=printed "
        "font_id=alef-regular "
        "degradation_preset=office_scan_soft"
    ),
    (
        "template_id=printed_letter_heavy_scan "
        "recipe_id=printed_letter_form_heavy_scan_v1 "
        "layout_style=printed_form "
        "font_style=printed "
        "font_id=alef-regular "
        "degradation_preset=office_scan_heavy"
    ),
    (
        "template_id=handwritten_note_heavy_wear "
        "recipe_id=handwritten_note_marginalia_heavy_wear_v1 "
        "layout_style=handwritten_note "
        "font_style=handwritten_like "
        "font_id=gveret-levin-regular "
        "degradation_preset=notebook_scan_heavy_wear"
    ),
    (
        "template_id=archive_card_faded_scan "
        "recipe_id=archive_card_identifier_faded_scan_v1 "
        "layout_style=multi_region_page "
        "font_style=printed "
        "font_id=alef-regular "
        "degradation_preset=archive_scan_faded"
    ),
]
EXPECTED_TEMPLATE_CATALOG_JSON = {
    "schema_version": TEMPLATE_CATALOG_SCHEMA_VERSION,
    "templates": [
        {
            "template_id": "printed_letter",
            "recipe_id": "printed_letter_form_v1",
            "layout_style": "printed_form",
            "font_style": "printed",
            "font_id": "alef-regular",
            "degradation_preset": "office_scan_soft",
        },
        {
            "template_id": "handwritten_note",
            "recipe_id": "handwritten_note_marginalia_v1",
            "layout_style": "handwritten_note",
            "font_style": "handwritten_like",
            "font_id": "gveret-levin-regular",
            "degradation_preset": "notebook_scan_worn",
        },
        {
            "template_id": "archive_card",
            "recipe_id": "archive_card_identifier_v1",
            "layout_style": "multi_region_page",
            "font_style": "printed",
            "font_id": "alef-regular",
            "degradation_preset": "office_scan_soft",
        },
        {
            "template_id": "ledger",
            "recipe_id": "ledger_table_v1",
            "layout_style": "tabular",
            "font_style": "printed",
            "font_id": "alef-regular",
            "degradation_preset": "office_scan_soft",
        },
        {
            "template_id": "printed_letter_heavy_scan",
            "recipe_id": "printed_letter_form_heavy_scan_v1",
            "layout_style": "printed_form",
            "font_style": "printed",
            "font_id": "alef-regular",
            "degradation_preset": "office_scan_heavy",
        },
        {
            "template_id": "handwritten_note_heavy_wear",
            "recipe_id": "handwritten_note_marginalia_heavy_wear_v1",
            "layout_style": "handwritten_note",
            "font_style": "handwritten_like",
            "font_id": "gveret-levin-regular",
            "degradation_preset": "notebook_scan_heavy_wear",
        },
        {
            "template_id": "archive_card_faded_scan",
            "recipe_id": "archive_card_identifier_faded_scan_v1",
            "layout_style": "multi_region_page",
            "font_style": "printed",
            "font_id": "alef-regular",
            "degradation_preset": "archive_scan_faded",
        },
    ],
}
EXPECTED_TEMPLATE_CATALOG_JSON_TEXT = json.dumps(
    EXPECTED_TEMPLATE_CATALOG_JSON, ensure_ascii=False, indent=2
)
EXPECTED_CONTRACT_FIXTURE_LINE = (
    "fixture_id=generation_manifest_v1_fixture_batch "
    "contract=generation_manifest.v1 "
    "sample_count=2 "
    "page_count=2 "
    "resource_path=data/contracts/generation_manifest_v1/fixture-batch "
    "manifest_resource_path=data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json"
)
EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON = {
    "schema_version": CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION,
    "fixtures": [
        {
            "fixture_id": "generation_manifest_v1_fixture_batch",
            "contract": "generation_manifest.v1",
            "sample_count": 2,
            "page_count": 2,
            "resource_path": "data/contracts/generation_manifest_v1/fixture-batch",
            "manifest_resource_path": (
                "data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json"
            ),
        }
    ],
}
EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON_TEXT = json.dumps(
    EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON, ensure_ascii=False, indent=2
)
REQUIRED_CONTRACT_FIXTURE_RESOURCE_PATHS = [
    "data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json",
    (
        "data/contracts/generation_manifest_v1/fixture-batch/assets/"
        "hocrsyngen-s00000017-000000/page_0001.jpg"
    ),
    (
        "data/contracts/generation_manifest_v1/fixture-batch/assets/"
        "hocrsyngen-s00000017-000001/page_0001.jpg"
    ),
]
INSTALLED_CLI_SMOKE_CASES = [
    "templates-text",
    "templates-json",
    "templates-json-v2",
    "contracts-text",
    "contracts-json",
    "contracts-export",
    "validate-exported-fixture",
    "generate-json",
    "generate-rendering-coverage-report",
    "validate-generated-batch",
    "wet-run-smoke",
    "wet-gallery",
    "evidence-run-json",
]


def _packaged_contract_fixture() -> Path:
    return (
        resources.files("hocrsyngen")
        / "data"
        / "contracts"
        / "generation_manifest_v1"
        / "fixture-batch"
    )


def _run_installed_cli(
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


def _json_from_successful_cli(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def _assert_batch_assets_are_portable(batch_dir: Path) -> None:
    manifest = json.loads(
        (batch_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )
    for sample in manifest["samples"]:
        for page in sample["pages"]:
            asset_path_text = page["asset_path"]
            asset_path = PurePosixPath(asset_path_text)
            assert not asset_path.is_absolute()
            assert ".." not in asset_path.parts
            assert "\\" not in asset_path_text
            assert (batch_dir / Path(*asset_path.parts)).is_file()


def _export_fixture_through_installed_cli(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    output_dir: Path,
) -> None:
    fixture_export = _json_from_successful_cli(
        _run_installed_cli(
            command
            + [
                "contracts",
                "export",
                "--fixture-id",
                "generation_manifest_v1_fixture_batch",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ],
            cwd=cwd,
            env=env,
        )
    )
    assert fixture_export == {
        "schema_version": CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION,
        "fixture_id": "generation_manifest_v1_fixture_batch",
        "contract": "generation_manifest.v1",
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }
    _assert_batch_assets_are_portable(output_dir)


def _generate_batch_through_installed_cli(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    output_dir: Path,
) -> None:
    generation = _json_from_successful_cli(
        _run_installed_cli(
            command
            + [
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ],
            cwd=cwd,
            env=env,
        )
    )
    assert generation == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }
    generated_manifest = json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )
    assert "schema_version" not in generated_manifest
    assert len(generated_manifest["samples"]) == 2
    _assert_batch_assets_are_portable(output_dir)


def _assert_installed_cli_smoke_case(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    output_root: Path,
    cli_case: str,
) -> None:
    output_root.mkdir()

    if cli_case == "templates-text":
        templates = _run_installed_cli(command + ["templates"], cwd=cwd, env=env)
        assert templates.stderr == ""
        assert templates.stdout.splitlines() == EXPECTED_TEMPLATE_LINES
        return

    if cli_case == "templates-json":
        templates_json = _json_from_successful_cli(
            _run_installed_cli(
                command + ["templates", "--format", "json"],
                cwd=cwd,
                env=env,
            )
        )
        assert templates_json == EXPECTED_TEMPLATE_CATALOG_JSON
        return

    if cli_case == "templates-json-v2":
        templates_json = _json_from_successful_cli(
            _run_installed_cli(
                command + ["templates", "--format", "json", "--catalog-version", "v2"],
                cwd=cwd,
                env=env,
            )
        )
        schema = json.loads(TEMPLATE_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(templates_json, schema)
        assert templates_json["schema_version"] == RICH_TEMPLATE_CATALOG_SCHEMA_VERSION
        return

    if cli_case == "contracts-text":
        contracts = _run_installed_cli(command + ["contracts"], cwd=cwd, env=env)
        assert contracts.stderr == ""
        assert contracts.stdout.splitlines() == [EXPECTED_CONTRACT_FIXTURE_LINE]
        return

    if cli_case == "contracts-json":
        contracts_json = _json_from_successful_cli(
            _run_installed_cli(
                command + ["contracts", "--format", "json"],
                cwd=cwd,
                env=env,
            )
        )
        assert contracts_json == EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON
        return

    if cli_case == "contracts-export":
        _export_fixture_through_installed_cli(
            command=command,
            cwd=cwd,
            env=env,
            output_dir=output_root / "exported-fixture",
        )
        return

    if cli_case == "validate-exported-fixture":
        exported_fixture_dir = output_root / "exported-fixture"
        _export_fixture_through_installed_cli(
            command=command,
            cwd=cwd,
            env=env,
            output_dir=exported_fixture_dir,
        )
        exported_validation = _json_from_successful_cli(
            _run_installed_cli(
                command + ["validate", str(exported_fixture_dir), "--format", "json"],
                cwd=cwd,
                env=env,
            )
        )
        assert exported_validation == {
            "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
            "valid": True,
            "sample_count": 2,
            "page_count": 2,
            "path": str(exported_fixture_dir),
        }
        return

    if cli_case == "generate-json":
        _generate_batch_through_installed_cli(
            command=command,
            cwd=cwd,
            env=env,
            output_dir=output_root / "generated-batch",
        )
        return

    if cli_case == "generate-rendering-coverage-report":
        generated_dir = output_root / "generated-coverage-batch"
        generation = _json_from_successful_cli(
            _run_installed_cli(
                command
                + [
                    "generate",
                    "--count",
                    "2",
                    "--seed",
                    "17",
                    "--output",
                    str(generated_dir),
                    "--rendering-coverage-report",
                    "--format",
                    "json",
                ],
                cwd=cwd,
                env=env,
            )
        )
        assert generation == {
            "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
            "sample_count": 2,
            "page_count": 2,
            "output_path": str(generated_dir),
            "manifest_path": str(generated_dir / "generation_manifest.json"),
            "rendering_coverage_report_path": str(
                generated_dir / RENDERING_COVERAGE_REPORT_FILENAME
            ),
        }
        assert (generated_dir / RENDERING_COVERAGE_REPORT_FILENAME).is_file()
        _assert_batch_assets_are_portable(generated_dir)
        return

    if cli_case == "validate-generated-batch":
        generated_dir = output_root / "generated-batch"
        _generate_batch_through_installed_cli(
            command=command,
            cwd=cwd,
            env=env,
            output_dir=generated_dir,
        )
        generated_validation = _json_from_successful_cli(
            _run_installed_cli(
                command + ["validate", str(generated_dir), "--format", "json"],
                cwd=cwd,
                env=env,
            )
        )
        assert generated_validation == {
            "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
            "valid": True,
            "sample_count": 2,
            "page_count": 2,
            "path": str(generated_dir),
        }
        return

    if cli_case == "wet-run-smoke":
        wet_run_dir = output_root / "wet-smoke"
        wet_run = _json_from_successful_cli(
            _run_installed_cli(
                command
                + [
                    "wet-run",
                    "--profile",
                    "smoke",
                    "--seed",
                    "17",
                    "--output",
                    str(wet_run_dir),
                    "--format",
                    "json",
                ],
                cwd=cwd,
                env=env,
            )
        )
        assert wet_run["report_version"] == "wet_test_run.v1"
        assert wet_run["profile"] == "smoke"
        assert wet_run["validation"] == {
            "valid": True,
            "sample_count": len(GOVERNED_TEMPLATE_IDS) + 1,
            "page_count": len(GOVERNED_TEMPLATE_IDS) + 1,
        }
        assert (wet_run_dir / "reports" / "wet_test_run.json").is_file()
        assert (wet_run_dir / "reports" / "wet_test_checksums.txt").is_file()
        _assert_batch_assets_are_portable(wet_run_dir / "batch")
        _assert_batch_assets_are_portable(
            wet_run_dir / "control_batches" / "non_default_style_condition"
        )
        return

    if cli_case == "wet-gallery":
        wet_run_dir = output_root / "wet-gallery-run"
        gallery_dir = wet_run_dir / "gallery"
        _json_from_successful_cli(
            _run_installed_cli(
                command
                + [
                    "wet-run",
                    "--profile",
                    "smoke",
                    "--seed",
                    "17",
                    "--output",
                    str(wet_run_dir),
                    "--format",
                    "json",
                ],
                cwd=cwd,
                env=env,
            )
        )
        gallery = _json_from_successful_cli(
            _run_installed_cli(
                command
                + [
                    "wet-gallery",
                    str(wet_run_dir),
                    "--output",
                    str(gallery_dir),
                    "--format",
                    "json",
                ],
                cwd=cwd,
                env=env,
            )
        )
        assert gallery["report_version"] == "wet_gallery_report.v1"
        assert gallery["page_count"] == len(GOVERNED_TEMPLATE_IDS) + 1
        assert gallery["index_path"] == "gallery/index.html"
        assert (gallery_dir / "index.html").is_file()
        assert "../batch/assets/" in (gallery_dir / "index.html").read_text(
            encoding="utf-8"
        )
        return

    if cli_case == "evidence-run-json":
        completed = _run_installed_cli(
            command
            + [
                "evidence-run",
                "--count",
                "1",
                "--seed",
                "17",
                "--output-root",
                str(output_root),
                "--run-id",
                "candidate-evidence",
                "--format",
                "json",
                "--color",
                "never",
            ],
            cwd=cwd,
            env=env,
        )
        assert "[01] Prepare output directory" in completed.stderr
        assert "release_eligible=false" in completed.stderr
        payload = json.loads(completed.stdout)
        run_dir = output_root / "candidate-evidence"
        assert payload["schema_version"] == EVIDENCE_RUN_REPORT_SCHEMA_VERSION
        assert payload["release_eligible"] is False
        assert payload["count"] == 1
        assert payload["seed"] == 17
        assert payload["output_root"] == str(run_dir)
        assert payload["reports"]["generated_validation"]["valid"] is True
        assert (run_dir / "RUN_NOTES.md").is_file()
        assert (run_dir / "SHA256SUMS").is_file()
        assert (run_dir / "candidate_evidence_run_report.json").is_file()
        assert (run_dir / "generated_batch" / "generation_manifest.json").is_file()
        assert (run_dir / "reports" / "template_catalog_v2.json").is_file()
        _assert_batch_assets_are_portable(run_dir / "generated_batch")
        return

    raise AssertionError(f"unknown installed CLI smoke case: {cli_case}")


def test_contracts_cli_smoke_outputs_stable_catalog_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["contracts"]) == 0

    assert capsys.readouterr().out.splitlines() == [EXPECTED_CONTRACT_FIXTURE_LINE]


def test_contracts_cli_json_outputs_deterministic_catalog(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["contracts", "--format", "json"]) == 0

    stdout = capsys.readouterr().out
    assert stdout == f"{EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON_TEXT}\n"
    assert json.loads(stdout) == EXPECTED_CONTRACT_FIXTURE_CATALOG_JSON


def test_contracts_cli_json_counts_match_packaged_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with resources.as_file(_packaged_contract_fixture()) as batch_dir:
        result = validate_batch(batch_dir)

    assert main(["contracts", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    [fixture] = payload["fixtures"]
    assert fixture["sample_count"] == result.sample_count
    assert fixture["page_count"] == result.page_count


def test_format_contract_fixture_catalog_json_uses_public_schema_only() -> None:
    output = _format_contract_fixture_catalog_json([])

    assert json.loads(output) == {
        "schema_version": CONTRACT_FIXTURE_CATALOG_SCHEMA_VERSION,
        "fixtures": [],
    }


def test_contracts_export_cli_json_exports_valid_fixture_batch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "exported-fixture"

    assert (
        main(
            [
                "contracts",
                "export",
                "--fixture-id",
                "generation_manifest_v1_fixture_batch",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "schema_version": CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION,
        "fixture_id": "generation_manifest_v1_fixture_batch",
        "contract": "generation_manifest.v1",
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }
    result = validate_batch(output_dir)
    assert result.sample_count == 2
    assert result.page_count == 2


def test_contracts_export_cli_refuses_existing_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    marker = output_dir / "marker.txt"
    marker.write_text("keep\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "contracts",
                "export",
                "--fixture-id",
                "generation_manifest_v1_fixture_batch",
                "--output",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 2
    assert "output path already exists" in capsys.readouterr().err
    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_contracts_export_cli_cleans_staging_directory_after_validation_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "exported-fixture"

    def fail_exported_batch_validation(path: Path) -> ValidationResult:
        if path.name == "fixture-batch":
            return ValidationResult(sample_count=2, page_count=2)
        raise BatchValidationError("forced exported fixture validation failure")

    monkeypatch.setattr("hocrsyngen.cli.validate_batch", fail_exported_batch_validation)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "contracts",
                "export",
                "--fixture-id",
                "generation_manifest_v1_fixture_batch",
                "--output",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "forced exported fixture validation failure" in captured.err
    assert not output_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_contracts_export_module_entry_point_smoke(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "module-contract-export"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hocrsyngen.cli",
            "contracts",
            "export",
            "--fixture-id",
            "generation_manifest_v1_fixture_batch",
            "--output",
            str(output_dir),
            "--format",
            "json",
        ],
        check=True,
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "schema_version": CONTRACT_FIXTURE_EXPORT_SCHEMA_VERSION,
        "fixture_id": "generation_manifest_v1_fixture_batch",
        "contract": "generation_manifest.v1",
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }
    result = validate_batch(output_dir)
    assert result.sample_count == 2
    assert result.page_count == 2


def test_format_template_catalog_entry() -> None:
    assert (
        _format_template_catalog_entry(
            TemplateCatalogEntry(
                template_id="printed_letter",
                recipe_id="printed_letter_form_v1",
                layout_style="printed_form",
                font_style="printed",
                font_id="alef-regular",
                degradation_preset="office_scan_soft",
            )
        )
        == EXPECTED_TEMPLATE_LINES[0]
    )


def test_format_template_catalog_json_uses_public_schema_only() -> None:
    output = _format_template_catalog_json(
        [
            TemplateCatalogEntry(
                template_id="printed_letter",
                recipe_id="printed_letter_form_v1",
                layout_style="printed_form",
                font_style="printed",
                font_id="alef-regular",
                degradation_preset="office_scan_soft",
            )
        ]
    )

    assert json.loads(output) == {
        "schema_version": TEMPLATE_CATALOG_SCHEMA_VERSION,
        "templates": [
            {
                "template_id": "printed_letter",
                "recipe_id": "printed_letter_form_v1",
                "layout_style": "printed_form",
                "font_style": "printed",
                "font_id": "alef-regular",
                "degradation_preset": "office_scan_soft",
            }
        ],
    }


def test_format_rich_template_catalog_json_uses_v2_public_schema() -> None:
    output = _format_rich_template_catalog_json(
        [
            RichTemplateCatalogEntry(
                template_id="archive_card",
                recipe_id="archive_card_identifier_v1",
                layout_style="multi_region_page",
                font_style="printed",
                font_id="alef-regular",
                degradation_preset="office_scan_soft",
                capability_metadata=TemplateCapabilityMetadata(
                    document_family="archive_card",
                    base_family="archive_card",
                    page_regions=(
                        "title",
                        "body",
                        "footer",
                        "table_cells",
                        "stamp_area",
                        "identifier_area",
                    ),
                    annotation_types=("synthetic_stamp",),
                    identifier_types=("archive_id", "date", "footer_label"),
                    layout_density="dense",
                    review_features=(
                        "has_stable_regions",
                        "has_visible_identifier",
                        "has_visible_stamp",
                    ),
                ),
            )
        ]
    )

    assert json.loads(output) == {
        "schema_version": RICH_TEMPLATE_CATALOG_SCHEMA_VERSION,
        "templates": [
            {
                "template_id": "archive_card",
                "recipe_id": "archive_card_identifier_v1",
                "layout_style": "multi_region_page",
                "font_style": "printed",
                "font_id": "alef-regular",
                "degradation_preset": "office_scan_soft",
                "document_family": "archive_card",
                "base_family": "archive_card",
                "page_regions": [
                    "title",
                    "body",
                    "footer",
                    "table_cells",
                    "stamp_area",
                    "identifier_area",
                ],
                "annotation_types": ["synthetic_stamp"],
                "identifier_types": ["archive_id", "date", "footer_label"],
                "layout_density": "dense",
                "review_features": [
                    "has_stable_regions",
                    "has_visible_identifier",
                    "has_visible_stamp",
                ],
            }
        ],
    }


def test_templates_cli_smoke_outputs_stable_catalog_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["templates"]) == 0

    assert capsys.readouterr().out.splitlines() == EXPECTED_TEMPLATE_LINES


def test_templates_cli_text_format_matches_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["templates", "--format", "text"]) == 0

    assert capsys.readouterr().out.splitlines() == EXPECTED_TEMPLATE_LINES


def test_templates_cli_json_outputs_deterministic_catalog(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["templates", "--format", "json"]) == 0

    stdout = capsys.readouterr().out
    assert stdout == f"{EXPECTED_TEMPLATE_CATALOG_JSON_TEXT}\n"
    assert json.loads(stdout) == EXPECTED_TEMPLATE_CATALOG_JSON


def test_templates_cli_json_v2_outputs_richer_catalog_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["templates", "--format", "json", "--catalog-version", "v2"]) == 0

    payload = json.loads(capsys.readouterr().out)
    schema = json.loads(TEMPLATE_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(payload, schema)
    assert payload["schema_version"] == RICH_TEMPLATE_CATALOG_SCHEMA_VERSION
    catalog = {entry["template_id"]: entry for entry in payload["templates"]}
    assert catalog["printed_letter"]["document_family"] == "letter"
    assert catalog["printed_letter"]["base_family"] == "printed_letter"
    assert catalog["printed_letter_heavy_scan"]["base_family"] == "printed_letter"
    assert "form_rows" in catalog["printed_letter"]["page_regions"]
    assert catalog["handwritten_note"]["document_family"] == "notebook_note"
    assert "marginal_note" in catalog["handwritten_note"]["annotation_types"]
    assert catalog["archive_card"]["document_family"] == "archive_card"
    assert catalog["archive_card_faded_scan"]["base_family"] == "archive_card"
    assert {"archive_id", "date", "footer_label"} <= set(
        catalog["archive_card"]["identifier_types"]
    )
    assert catalog["ledger"]["document_family"] == "ledger"
    assert catalog["ledger"]["base_family"] == "ledger"
    assert catalog["ledger"]["layout_style"] == "tabular"
    assert {"ledger_id", "date", "page_number", "footer_label"} <= set(
        catalog["ledger"]["identifier_types"]
    )
    assert "has_reviewable_table" in catalog["ledger"]["review_features"]
    for entry in catalog.values():
        assert {
            "document_family",
            "base_family",
            "page_regions",
            "annotation_types",
            "identifier_types",
            "layout_density",
            "review_features",
        } <= set(entry)
        assert isinstance(entry["page_regions"], list)
        assert isinstance(entry["annotation_types"], list)
        assert isinstance(entry["identifier_types"], list)
        assert isinstance(entry["review_features"], list)


def test_templates_cli_v2_rejects_text_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["templates", "--catalog-version", "v2"])

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "templates: --catalog-version v2 requires --format json" in stderr


def test_templates_cli_reports_invalid_packaged_resource_cleanly(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_catalog() -> None:
        raise ValueError(
            "Synthetic font manifest is missing a valid 'fonts' list: /tmp/manifest.yaml"
        )

    monkeypatch.setattr("hocrsyngen.cli.template_catalog", fail_catalog)

    with pytest.raises(SystemExit) as exc_info:
        main(["templates"])

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert (
        "templates: Synthetic font manifest is missing a valid 'fonts' list" in stderr
    )
    assert "Traceback" not in stderr


def test_format_generation_report_json_uses_public_schema_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture-batch"

    output = _format_generation_report_json(output_dir, sample_count=2, page_count=2)

    assert json.loads(output) == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }


def test_format_generation_report_json_can_include_rendering_coverage_path(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "fixture-batch"

    output = _format_generation_report_json(
        output_dir,
        sample_count=2,
        page_count=2,
        rendering_coverage_report_path=(
            output_dir / RENDERING_COVERAGE_REPORT_FILENAME
        ),
    )

    assert json.loads(output) == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
        "rendering_coverage_report_path": str(
            output_dir / RENDERING_COVERAGE_REPORT_FILENAME
        ),
    }


def test_generate_cli_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "fixture-batch"

    assert (
        main(["generate", "--count", "2", "--seed", "17", "--output", str(output_dir)])
        == 0
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    manifest_path = output_dir / "generation_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(payload["samples"]) == 2
    assert {
        sample["provenance"]["template_id"]: sample["provenance"]["font_id"]
        for sample in payload["samples"]
    } == {
        "printed_letter": "alef-regular",
        "handwritten_note": "gveret-levin-regular",
    }
    for sample in payload["samples"]:
        assert (output_dir / sample["pages"][0]["asset_path"]).is_file()
    assert not (output_dir / RENDERING_COVERAGE_REPORT_FILENAME).exists()


def test_generate_cli_accepts_explicit_archive_card_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "archive-card-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "37",
                "--output",
                str(output_dir),
                "--template-id",
                "archive_card",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["sample_count"] == 1
    payload = json.loads((output_dir / "generation_manifest.json").read_text(encoding="utf-8"))
    [sample] = payload["samples"]
    assert sample["recipe_id"] == "archive_card_identifier_v1"
    assert sample["provenance"]["template_id"] == "archive_card"
    assert sample["provenance"]["font_id"] == "alef-regular"
    assert (output_dir / sample["pages"][0]["asset_path"]).is_file()


def test_generate_cli_json_outputs_deterministic_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "fixture-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        json.dumps(
            {
                "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
                "sample_count": 2,
                "page_count": 2,
                "output_path": str(output_dir),
                "manifest_path": str(output_dir / "generation_manifest.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    manifest = json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )
    assert "schema_version" not in manifest
    assert len(manifest["samples"]) == 2
    assert not (output_dir / RENDERING_COVERAGE_REPORT_FILENAME).exists()


def test_generate_cli_writes_opt_in_rendering_coverage_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "coverage-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--rendering-coverage-report",
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 2,
        "page_count": 2,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
        "rendering_coverage_report_path": str(
            output_dir / RENDERING_COVERAGE_REPORT_FILENAME
        ),
    }
    sidecar = json.loads(
        (output_dir / RENDERING_COVERAGE_REPORT_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert sidecar["report_version"] == "rendering_coverage_report.v1"
    assert sidecar["batch"]["manifest_path"] == "generation_manifest.json"
    assert "report_version" not in json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )


def test_wet_run_smoke_cli_writes_auditable_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-17"

    assert (
        main(
            [
                "wet-run",
                "--profile",
                "smoke",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    stdout_payload = json.loads(captured.out)
    run_payload = json.loads(
        (output_dir / "reports" / "wet_test_run.json").read_text(encoding="utf-8")
    )
    assert stdout_payload == run_payload
    assert run_payload["report_version"] == "wet_test_run.v1"
    assert run_payload["profile"] == "smoke"
    assert run_payload["status"] == "passed"
    assert run_payload["config"] == {
        "seed": 17,
        "total_count": len(GOVERNED_TEMPLATE_IDS) + 1,
        "primary_count": len(GOVERNED_TEMPLATE_IDS),
        "supplemental_count": 1,
        "primary_template_ids": GOVERNED_TEMPLATE_IDS,
        "supplemental_controls": [
            {
                "batch_id": "non_default_style_condition",
                "template_ids": ["printed_letter"],
                "persona": "style_open_drift_v1",
                "condition": "condition_low_contrast_v1",
            }
        ],
        "primary_rendering_coverage_report": False,
        "output_path": ".",
        "batch_path": "batch",
    }
    assert run_payload["validation"] == {
        "valid": True,
        "sample_count": len(GOVERNED_TEMPLATE_IDS) + 1,
        "page_count": len(GOVERNED_TEMPLATE_IDS) + 1,
    }
    assert run_payload["scope"]["manifest_v1_changed"] is False
    assert run_payload["scope"]["hocrgen_behavior_added"] is False
    assert run_payload["reports"] == {
        "template_catalog_v2_path": "reports/template_catalog_v2.json",
        "checksum_path": "reports/wet_test_checksums.txt",
        "checksum_file_includes_wet_test_run": True,
    }

    manifest_path = output_dir / run_payload["generated_batch"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "schema_version" not in manifest
    assert [
        sample["provenance"]["template_id"] for sample in manifest["samples"]
    ] == GOVERNED_TEMPLATE_IDS
    validate_batch(output_dir / "batch")
    [supplemental_batch] = run_payload["supplemental_batches"]
    assert supplemental_batch["batch_id"] == "non_default_style_condition"
    assert supplemental_batch["template_ids"] == ["printed_letter"]
    assert supplemental_batch["persona"] == "style_open_drift_v1"
    assert supplemental_batch["condition"] == "condition_low_contrast_v1"
    supplemental_manifest = json.loads(
        (output_dir / supplemental_batch["manifest_path"]).read_text(encoding="utf-8")
    )
    [supplemental_sample] = supplemental_manifest["samples"]
    assert supplemental_sample["controls"] == {
        "persona": "style_open_drift_v1",
        "condition": "condition_low_contrast_v1",
    }
    validate_batch(output_dir / supplemental_batch["batch_path"])

    for relative_path in [
        run_payload["generated_batch"]["manifest_path"],
        *run_payload["generated_batch"]["asset_paths"],
        supplemental_batch["manifest_path"],
        *supplemental_batch["asset_paths"],
        *run_payload["artifact_checksums"].keys(),
    ]:
        path = PurePosixPath(relative_path)
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert (output_dir / Path(*path.parts)).is_file()

    for relative_path, expected_digest in run_payload["artifact_checksums"].items():
        assert sha256_file(output_dir / Path(*PurePosixPath(relative_path).parts)) == expected_digest

    checksum_lines = (
        output_dir / "reports" / "wet_test_checksums.txt"
    ).read_text(encoding="utf-8").splitlines()
    checksum_paths = {line.split("  ", 1)[1] for line in checksum_lines}
    assert "reports/wet_test_run.json" in checksum_paths
    assert "batch/generation_manifest.json" in checksum_paths
    assert "reports/wet_test_run.json" not in run_payload["artifact_checksums"]
    assert run_payload["checksum_contract"] == {
        "algorithm": "sha256",
        "artifact_checksums_exclude": [
            "reports/wet_test_run.json",
            "reports/wet_test_checksums.txt",
        ],
        "checksum_file_includes": [
            *sorted(run_payload["artifact_checksums"]),
            "reports/wet_test_run.json",
        ],
    }


def test_wet_run_smoke_can_retain_rendering_coverage_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-coverage"

    assert (
        main(
            [
                "wet-run",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--rendering-coverage-report",
                "--format",
                "json",
            ]
        )
        == 0
    )

    run_payload = json.loads(capsys.readouterr().out)
    assert (
        run_payload["generated_batch"]["rendering_coverage_report_path"]
        == f"batch/{RENDERING_COVERAGE_REPORT_FILENAME}"
    )
    sidecar_path = (
        output_dir / run_payload["generated_batch"]["rendering_coverage_report_path"]
    )
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["report_version"] == "rendering_coverage_report.v1"
    assert run_payload["artifact_checksums"][f"batch/{RENDERING_COVERAGE_REPORT_FILENAME}"] == sha256_file(sidecar_path)


def test_wet_gallery_cli_writes_static_gallery_with_escaped_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-17"
    gallery_dir = output_dir / "gallery"

    assert (
        main(
            [
                "wet-run",
                "--profile",
                "smoke",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    manifest_path = output_dir / "batch" / "generation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["samples"][0]["text"]["logical_order"] = '<b>שלום & "בדיקה"</b>'
    second_page = dict(manifest["samples"][0]["pages"][0])
    second_page["page_id"] = f"{second_page['page_id']}-copy"
    manifest["samples"][0]["pages"].append(second_page)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "wet-gallery",
                str(output_dir),
                "--output",
                str(gallery_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)
    assert report == {
        "report_version": "wet_gallery_report.v1",
        "run_path": ".",
        "index_path": "gallery/index.html",
        "page_count": len(GOVERNED_TEMPLATE_IDS) + 2,
        "sample_count": len(GOVERNED_TEMPLATE_IDS) + 1,
        "batch_count": 2,
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_sidecar_included": False,
            "llm_triage_included": False,
            "network_required": False,
        },
    }
    html_text = (gallery_dir / "index.html").read_text(encoding="utf-8")
    assert "../batch/assets/" in html_text
    assert "../control_batches/non_default_style_condition/assets/" in html_text
    assert "src=\"/" not in html_text
    assert "href=\"/" not in html_text
    assert "&lt;b&gt;שלום &amp; &quot;בדיקה&quot;&lt;/b&gt;" in html_text
    assert '<b>שלום & "בדיקה"</b>' not in html_text
    assert "white-space: pre-wrap;" in html_text
    for expected in [
        "sample id",
        "page id",
        "template id",
        "recipe id",
        "style/persona",
        "condition",
        "degradation",
        "font id",
    ]:
        assert expected in html_text


def test_wet_gallery_rejects_stale_manifest_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-17"
    gallery_dir = output_dir / "gallery"

    assert main(["wet-run", "--seed", "17", "--output", str(output_dir)]) == 0
    capsys.readouterr()
    run_report_path = output_dir / "reports" / "wet_test_run.json"
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
    run_report["generated_batch"]["manifest_path"] = "reports/template_catalog_v2.json"
    run_report_path.write_text(
        json.dumps(run_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["wet-gallery", str(output_dir), "--output", str(gallery_dir)])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert (
        "wet-gallery: wet-test run manifest_path must match the validated batch manifest"
        in captured.err
    )


def test_wet_gallery_rejects_reusing_existing_gallery_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-17"
    gallery_dir = output_dir / "gallery"

    assert main(["wet-run", "--seed", "17", "--output", str(output_dir)]) == 0
    capsys.readouterr()
    gallery_dir.mkdir()
    (gallery_dir / "index.html").write_text("existing\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["wet-gallery", str(output_dir), "--output", str(gallery_dir)])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "wet-gallery: gallery output directory already exists and is not empty" in captured.err


def test_wet_run_smoke_rejects_reusing_existing_run_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "wet-tests" / "smoke-17"

    assert main(["wet-run", "--seed", "17", "--output", str(output_dir)]) == 0
    capsys.readouterr()

    with pytest.raises(SystemExit) as excinfo:
        main(["wet-run", "--seed", "17", "--output", str(output_dir)])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "wet-run: wet-run output directory already exists and is not empty" in captured.err


def test_wet_run_smoke_writes_failure_report_without_partial_batch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "wet-tests" / "failed-smoke"

    def fail_generation(*args: object, **kwargs: object) -> object:
        raise ValueError("simulated generation failure")

    monkeypatch.setattr("hocrsyngen.wet_run.generate_batch", fail_generation)

    with pytest.raises(SystemExit) as excinfo:
        main(["wet-run", "--seed", "17", "--output", str(output_dir)])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "simulated generation failure" in captured.err
    assert not (output_dir / "batch").exists()
    failure_report = json.loads(
        (output_dir / "reports" / "wet_test_run.json").read_text(encoding="utf-8")
    )
    assert failure_report["status"] == "failed"
    assert failure_report["validation"] == {"valid": False}
    assert failure_report["error"] == {
        "type": "ValueError",
        "message": "simulated generation failure",
    }


def test_generate_cli_accepts_persona_style_bundle_control(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "style-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--persona",
                "style_compact_steady_v1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["sample_count"] == 2
    manifest = json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )
    assert [sample["controls"] for sample in manifest["samples"]] == [
        {"condition": None, "persona": "style_compact_steady_v1"},
        {"condition": None, "persona": "style_compact_steady_v1"},
    ]
    assert all("style" not in sample for sample in manifest["samples"])


def test_generate_cli_help_lists_persona_style_bundle_choices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["generate", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--persona" in help_text
    assert "Synthetic style bundle id" in help_text
    for persona in SUPPORTED_STYLE_BUNDLE_IDS:
        assert persona in help_text


def test_generate_cli_accepts_condition_bundle_control(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "condition-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "2",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--condition",
                "condition_low_contrast_v1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["sample_count"] == 2
    manifest = json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )
    assert [sample["controls"] for sample in manifest["samples"]] == [
        {"condition": "condition_low_contrast_v1", "persona": None},
        {"condition": "condition_low_contrast_v1", "persona": None},
    ]
    assert all("condition" not in {key for key in sample if key != "controls"} for sample in manifest["samples"])


def test_generate_cli_help_lists_condition_bundle_choices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["generate", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--condition" in help_text
    assert "Synthetic rendering condition bundle id" in help_text
    for condition in SUPPORTED_CONDITION_BUNDLE_IDS:
        assert condition in help_text


def test_generate_cli_json_reports_zero_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "empty-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                "0",
                "--seed",
                "17",
                "--output",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out) == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 0,
        "page_count": 0,
        "output_path": str(output_dir),
        "manifest_path": str(output_dir / "generation_manifest.json"),
    }
    assert (
        json.loads(
            (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
        )["samples"]
        == []
    )


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--count", "-1"),
        ("--seed", "-1"),
    ],
)
def test_generate_cli_rejects_negative_numeric_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], option: str, value: str
) -> None:
    output_dir = tmp_path / "should-not-exist"
    args = ["generate", "--count", "1", "--seed", "17", "--output", str(output_dir)]
    args[args.index(option) + 1] = value

    with pytest.raises(SystemExit) as exc_info:
        main(args)

    assert exc_info.value.code == 2
    assert "must be non-negative" in capsys.readouterr().err
    assert not output_dir.exists()


def test_generate_cli_rejects_existing_file_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "not-a-directory"
    output_path.write_text("existing file\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["generate", "--count", "1", "--seed", "17", "--output", str(output_path)])

    assert exc_info.value.code == 2
    assert "output path exists and is not a directory" in capsys.readouterr().err
    assert output_path.read_text(encoding="utf-8") == "existing file\n"


def test_generate_cli_rejects_invalid_template_without_partial_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "should-not-exist"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "17",
                "--template-id",
                "typo_template",
                "--output",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 2
    assert "invalid choice: 'typo_template'" in capsys.readouterr().err
    assert not output_dir.exists()


def test_generate_cli_rejects_invalid_persona_style_without_partial_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "should-not-exist"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "17",
                "--persona",
                "real_writer_claim",
                "--output",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice: 'real_writer_claim'" in captured.err
    assert "style_standard_v1" in captured.err
    assert not output_dir.exists()


def test_generate_cli_rejects_invalid_condition_without_partial_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "should-not-exist"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "17",
                "--condition",
                "medical_claim",
                "--output",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice: 'medical_claim'" in captured.err
    assert "condition_standard_v1" in captured.err
    assert not output_dir.exists()


def test_generate_cli_reports_missing_packaged_resource_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_path = tmp_path / "missing" / "manifest.yaml"

    def fail_generation(**_kwargs) -> None:
        raise FileNotFoundError(missing_path)

    monkeypatch.setattr("hocrsyngen.cli.generate_batch", fail_generation)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "17",
                "--output",
                str(tmp_path / "out"),
            ]
        )

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "required packaged resource is missing" in stderr
    assert str(missing_path) in stderr
    assert "Traceback" not in stderr


def test_generate_cli_reports_invalid_packaged_resource_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_generation(**_kwargs) -> None:
        raise ValueError(
            "Synthetic font file is invalid or unreadable: /tmp/invalid.ttf"
        )

    monkeypatch.setattr("hocrsyngen.cli.generate_batch", fail_generation)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--count",
                "1",
                "--seed",
                "17",
                "--output",
                str(tmp_path / "out"),
            ]
        )

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "Synthetic font file is invalid or unreadable" in stderr
    assert "Traceback" not in stderr


def test_validate_cli_json_reports_packaged_contract_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with resources.as_file(_packaged_contract_fixture()) as batch_dir:
        assert main(["validate", str(batch_dir), "--format", "json"]) == 0

        captured = capsys.readouterr()
        assert captured.err == ""
        assert json.loads(captured.out) == {
            "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
            "valid": True,
            "sample_count": 2,
            "page_count": 2,
            "path": str(batch_dir),
        }


def test_evidence_run_cli_creates_operator_evidence_with_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "evidence-run",
                "--count",
                "1",
                "--seed",
                "17",
                "--output-root",
                str(tmp_path),
                "--run-id",
                "candidate-evidence",
                "--format",
                "json",
                "--color",
                "never",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "\x1b[" not in captured.err
    assert "[01] Prepare output directory" in captured.err
    assert "[09] Validate generated candidate batch" in captured.err
    assert "release_eligible=false" in captured.err

    report = json.loads(captured.out)
    run_dir = tmp_path / "candidate-evidence"
    assert report["schema_version"] == EVIDENCE_RUN_REPORT_SCHEMA_VERSION
    assert report["release_eligible"] is False
    assert report["count"] == 1
    assert report["seed"] == 17
    assert report["output_root"] == str(run_dir)
    assert report["fixture_batch_path"] == str(run_dir / "fixture_batch")
    assert report["generated_batch_path"] == str(run_dir / "generated_batch")
    assert report["reports"]["template_catalog_v2"]["schema_version"] == (
        RICH_TEMPLATE_CATALOG_SCHEMA_VERSION
    )
    assert report["reports"]["fixture_validation"]["valid"] is True
    assert report["reports"]["generated_validation"]["valid"] is True

    report_path = run_dir / "candidate_evidence_run_report.json"
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert (run_dir / "RUN_NOTES.md").read_text(encoding="utf-8").count(
        "release_eligible: false"
    ) == 1
    checksum_text = (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "candidate_evidence_run_report.json" in checksum_text
    assert "generated_batch/generation_manifest.json" in checksum_text
    assert "reports/generated_validation_report.json" in checksum_text
    assert (run_dir / "reports" / "generation_report.json").is_file()
    assert (run_dir / "reports" / "generated_validation_report.json").is_file()
    _assert_batch_assets_are_portable(run_dir / "generated_batch")


@pytest.mark.parametrize(
    "entry_point",
    ["console-script", "python-module"],
)
@pytest.mark.parametrize("cli_case", INSTALLED_CLI_SMOKE_CASES)
def test_installed_package_public_cli_smoke_matrix(
    installed_package: tuple[Path, Path, dict[str, str]],
    entry_point: str,
    cli_case: str,
) -> None:
    target_dir, isolated_cwd, env = installed_package
    command = (
        [str(target_dir / "bin" / "hocrsyngen")]
        if entry_point == "console-script"
        else [sys.executable, "-m", "hocrsyngen.cli"]
    )

    _assert_installed_cli_smoke_case(
        command=command,
        cwd=isolated_cwd,
        env=env,
        output_root=isolated_cwd / f"installed-{entry_point}-{cli_case}",
        cli_case=cli_case,
    )


def test_installed_package_console_entry_point_and_packaged_resources(
    installed_package: tuple[Path, Path, dict[str, str]],
) -> None:
    _target_dir, isolated_cwd, env = installed_package
    resource_check = (
        "from importlib import resources\n"
        "required = [\n"
        "    'schemas/generation_manifest.schema.json',\n"
        "    'schemas/template_catalog.schema.json',\n"
        "    'data/synthetic/fonts/manifest.yaml',\n"
        "    'data/synthetic/fonts/Alef-Regular.ttf',\n"
        "    'data/synthetic/fonts/GveretLevin-Regular.ttf',\n"
        "    'data/synthetic/texts/hebrew_lines.txt',\n"
        "    'data/contracts/generation_manifest_v1/fixture-batch/generation_manifest.json',\n"
        "    'data/contracts/generation_manifest_v1/fixture-batch/assets/hocrsyngen-s00000017-000000/page_0001.jpg',\n"
        "    'data/contracts/generation_manifest_v1/fixture-batch/assets/hocrsyngen-s00000017-000001/page_0001.jpg',\n"
        "]\n"
        "root = resources.files('hocrsyngen')\n"
        "missing = [path for path in required if not (root / path).is_file()]\n"
        "assert not missing, missing\n"
    )
    subprocess.run(
        [sys.executable, "-c", resource_check],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    installed_contract_fixture_check = (
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "from importlib import resources\n"
        "fixture = resources.files('hocrsyngen') / 'data' / 'contracts' / 'generation_manifest_v1' / 'fixture-batch'\n"
        "with resources.as_file(fixture) as fixture_path:\n"
        "    completed = subprocess.run(\n"
        "        [sys.executable, '-m', 'hocrsyngen.cli', 'validate', str(fixture_path), '--format', 'json'],\n"
        "        check=True,\n"
        "        stdout=subprocess.PIPE,\n"
        "        stderr=subprocess.PIPE,\n"
        "        text=True,\n"
        "    )\n"
        "    assert completed.stderr == ''\n"
        "    payload = json.loads(completed.stdout)\n"
        "    assert payload == {\n"
        "        'schema_version': 'validation_report.v1',\n"
        "        'valid': True,\n"
        "        'sample_count': 2,\n"
        "        'page_count': 2,\n"
        "        'path': str(fixture_path),\n"
        "    }\n"
    )
    subprocess.run(
        [sys.executable, "-c", installed_contract_fixture_check],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    invalid_batch = isolated_cwd / "missing-manifest"
    invalid_batch.mkdir()
    module_validate_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "hocrsyngen.cli",
            "validate",
            str(invalid_batch),
            "--format",
            "json",
        ],
        check=False,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert module_validate_json.returncode == 1
    assert module_validate_json.stderr == ""
    assert json.loads(module_validate_json.stdout) == {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "valid": False,
        "path": str(invalid_batch),
        "error": f"Missing manifest: {invalid_batch / 'generation_manifest.json'}",
    }


def test_wheel_distribution_metadata_and_packaged_resources(
    wheel_installed_package: tuple[Path, Path, Path, dict[str, str]],
) -> None:
    wheel_path, target_dir, isolated_cwd, env = wheel_installed_package
    assert wheel_path.is_file()

    wheel_install_check = (
        "import json\n"
        "import sys\n"
        "from importlib import resources\n"
        "from pathlib import Path\n"
        "import hocrsyngen\n"
        "target_dir = Path(sys.argv[1]).resolve()\n"
        "required = json.loads(sys.argv[2])\n"
        "root = resources.files('hocrsyngen')\n"
        "module_path = Path(hocrsyngen.__file__).resolve()\n"
        "missing = [path for path in required if not (root / path).is_file()]\n"
        "print(json.dumps({\n"
        "    'module_path': str(module_path),\n"
        "    'module_in_target': module_path.is_relative_to(target_dir),\n"
        "    'missing_resources': missing,\n"
        "}, sort_keys=True))\n"
    )
    wheel_install_result = subprocess.run(
        [
            sys.executable,
            "-c",
            wheel_install_check,
            str(target_dir),
            json.dumps(REQUIRED_CONTRACT_FIXTURE_RESOURCE_PATHS),
        ],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert wheel_install_result.stderr == ""
    assert json.loads(wheel_install_result.stdout) == {
        "module_path": str((target_dir / "hocrsyngen" / "__init__.py").resolve()),
        "module_in_target": True,
        "missing_resources": [],
    }

    dist_metadata_check = (
        "from importlib.metadata import distribution\n"
        "dist = distribution('hocrsyngen')\n"
        "print(dist.metadata['Name'])\n"
        "print(dist.version)\n"
    )
    dist_metadata_result = subprocess.run(
        [sys.executable, "-c", dist_metadata_check],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert dist_metadata_result.stderr == ""
    assert dist_metadata_result.stdout.splitlines() == [
        "hocrsyngen",
        _project_version(),
    ]


@pytest.mark.parametrize(
    "entry_point",
    ["console-script", "python-module"],
)
@pytest.mark.parametrize("cli_case", INSTALLED_CLI_SMOKE_CASES)
def test_wheel_distribution_public_cli_smoke_matrix(
    wheel_installed_package: tuple[Path, Path, Path, dict[str, str]],
    entry_point: str,
    cli_case: str,
) -> None:
    _wheel_path, target_dir, isolated_cwd, env = wheel_installed_package
    command = (
        [str(target_dir / "bin" / "hocrsyngen")]
        if entry_point == "console-script"
        else [sys.executable, "-m", "hocrsyngen.cli"]
    )

    _assert_installed_cli_smoke_case(
        command=command,
        cwd=isolated_cwd,
        env=env,
        output_root=isolated_cwd / f"wheel-{entry_point}-{cli_case}",
        cli_case=cli_case,
    )
