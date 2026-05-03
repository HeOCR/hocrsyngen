from __future__ import annotations

import json
from pathlib import Path

from hocrsyngen.cli import main


def test_generate_cli_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture-batch"

    assert main(["generate", "--count", "2", "--seed", "17", "--output", str(output_dir)]) == 0

    manifest_path = output_dir / "generation_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(payload["samples"]) == 2
    for sample in payload["samples"]:
        assert (output_dir / sample["pages"][0]["asset_path"]).is_file()
