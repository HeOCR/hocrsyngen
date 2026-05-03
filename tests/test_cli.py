from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from hocrsyngen.cli import (
    GENERATION_REPORT_SCHEMA_VERSION,
    TEMPLATE_CATALOG_SCHEMA_VERSION,
    VALIDATION_REPORT_SCHEMA_VERSION,
    _format_generation_report_json,
    _format_template_catalog_entry,
    _format_template_catalog_json,
    main,
)
from hocrsyngen.generator import TemplateCatalogEntry


@pytest.fixture(scope="module")
def installed_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, dict[str, str]]:
    project_root = Path(__file__).resolve().parents[1]
    tmp_path = tmp_path_factory.mktemp("installed-package")
    target_dir = tmp_path / "site"
    isolated_cwd = tmp_path / "isolated"
    isolated_cwd.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target_dir),
            "--no-deps",
            "--no-build-isolation",
            str(project_root),
        ],
        check=True,
        cwd=isolated_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(target_dir)
    return target_dir, isolated_cwd, env


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
    ],
}
EXPECTED_TEMPLATE_CATALOG_JSON_TEXT = json.dumps(
    EXPECTED_TEMPLATE_CATALOG_JSON, ensure_ascii=False, indent=2
)


def _packaged_contract_fixture() -> Path:
    return (
        resources.files("hocrsyngen")
        / "data"
        / "contracts"
        / "generation_manifest_v1"
        / "fixture-batch"
    )


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


def test_installed_package_console_entry_point_and_packaged_resources(
    installed_package: tuple[Path, Path, dict[str, str]],
) -> None:
    target_dir, isolated_cwd, env = installed_package
    resource_check = (
        "from importlib import resources\n"
        "required = [\n"
        "    'schemas/generation_manifest.schema.json',\n"
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

    console_templates = subprocess.run(
        [str(target_dir / "bin" / "hocrsyngen"), "templates"],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert console_templates.stdout.splitlines() == EXPECTED_TEMPLATE_LINES

    console_templates_json = subprocess.run(
        [str(target_dir / "bin" / "hocrsyngen"), "templates", "--format", "json"],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert json.loads(console_templates_json.stdout) == EXPECTED_TEMPLATE_CATALOG_JSON

    module_templates = subprocess.run(
        [sys.executable, "-m", "hocrsyngen.cli", "templates"],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert module_templates.stdout.splitlines() == EXPECTED_TEMPLATE_LINES

    console_output = isolated_cwd / "console-out"
    subprocess.run(
        [
            str(target_dir / "bin" / "hocrsyngen"),
            "generate",
            "--count",
            "1",
            "--seed",
            "17",
            "--output",
            str(console_output),
        ],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    module_output = isolated_cwd / "module-out"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "hocrsyngen.cli",
            "generate",
            "--count",
            "0",
            "--seed",
            "17",
            "--output",
            str(module_output),
        ],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    console_manifest = json.loads(
        (console_output / "generation_manifest.json").read_text(encoding="utf-8")
    )
    console_asset = Path(console_manifest["samples"][0]["pages"][0]["asset_path"])
    assert not console_asset.is_absolute()
    assert (console_output / console_asset).is_file()
    assert (
        json.loads(
            (module_output / "generation_manifest.json").read_text(encoding="utf-8")
        )["samples"]
        == []
    )

    console_validate_json = subprocess.run(
        [
            str(target_dir / "bin" / "hocrsyngen"),
            "validate",
            str(console_output),
            "--format",
            "json",
        ],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert console_validate_json.stderr == ""
    assert json.loads(console_validate_json.stdout) == {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "valid": True,
        "sample_count": 1,
        "page_count": 1,
        "path": str(console_output),
    }

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


def test_installed_package_generate_json_entry_point(
    installed_package: tuple[Path, Path, dict[str, str]],
) -> None:
    _target_dir, isolated_cwd, env = installed_package
    module_generate_json_output = isolated_cwd / "module-json-out"
    module_generate_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "hocrsyngen.cli",
            "generate",
            "--count",
            "1",
            "--seed",
            "17",
            "--output",
            str(module_generate_json_output),
            "--format",
            "json",
        ],
        check=True,
        cwd=isolated_cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert module_generate_json.stderr == ""
    assert json.loads(module_generate_json.stdout) == {
        "schema_version": GENERATION_REPORT_SCHEMA_VERSION,
        "sample_count": 1,
        "page_count": 1,
        "output_path": str(module_generate_json_output),
        "manifest_path": str(module_generate_json_output / "generation_manifest.json"),
    }
    module_generate_json_manifest = json.loads(
        (module_generate_json_output / "generation_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert "schema_version" not in module_generate_json_manifest
