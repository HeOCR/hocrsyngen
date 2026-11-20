"""Restore the S17a style crops (pairs_v2/pairs/<id>_real.png) from bynli_lines_v2 after pairs_v2 was trashed.

  restore_styles.py STYLES_TXT OUT_PAIRS_JSONL

build_pairs_v2.py wrote each real crop as Image.open(LINES / image).convert("L").save(...), unedited, so the same
call recreates it. Writes a minimal pairs.jsonl ({id, book, record_id, real, real_sha256}) for gates.py --book-of,
and checks each source image against the manifest's image_sha256.
"""
import hashlib, json, sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from build_pairs import LINES  # noqa: E402

styles, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = {json.loads(l)["id"]: json.loads(l) for l in open(LINES / "manifest.jsonl")}
with open(out, "w") as fo:
    for p in styles.read_text().split():
        p = Path(p); i = p.name[: -len("_real.png")]; r = rows[i]
        assert r["split"] == "train", i
        src = LINES / r["image"]
        assert hashlib.sha256(src.read_bytes()).hexdigest() == r["image_sha256"], i
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("L").save(p)
        fo.write(json.dumps({"id": i, "book": r["book"], "record_id": r["record_id"], "real": str(p),
                             "real_sha256": r["image_sha256"]}, ensure_ascii=False) + "\n")
print("restored", len(styles.read_text().split()))
