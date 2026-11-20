"""S17a: export gate-accepted add-on lines for the R8 pipeline (v2: the dose-arm set).

  export_addon_v2.py GEN_DIR TEXTS_DIR OUT_DIR

As export_addon.py (v1), except: ids are s17a2_{k:05d} so they never collide with v1.1 (s17a_{k:05d}), and the
style provenance is the restored style list (pairs_v2/style_books.jsonl, addon_styles.txt), since pairs.jsonl is gone.

Writes OUT/lines/s17a_{k:05d}.png and .gt.txt, with the label in LOGICAL order (the intended
text, never a reader's output; NFC, single line), plus OUT/manifest.jsonl and OUT/summary.json.
The R8 pipeline does its own conversion (lstmf, and the visual-order .gt.txt it uses).
"""
import hashlib, json, shutil, sys, unicodedata
from pathlib import Path

gen, texts, out = map(Path, sys.argv[1:4])
H = Path(__file__).resolve().parents[1] / "intermediates"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
g = [json.loads(l) for l in open(gen / "gates.jsonl")]
t = [json.loads(l) for l in open(texts / "texts.jsonl")]
(out / "lines").mkdir(parents=True, exist_ok=True)
prov = {"generator": str(H / "run2/last.pt"), "generator_sha256": sha(H / "run2/last.pt"),
        "style_books_sha256": sha(H / "pairs_v2/style_books.jsonl"), "styles_sha256": sha(H / "addon_styles.txt"), "texts_sha256": sha(texts / "texts.jsonl"),
        "gates_sha256": sha(gen / "gates.jsonl"), "label_order": "logical",
        "text_source": "Project Ben-Yehuda public_domain_dump 2026-03 (PD)",
        "style_node": "unknown (pair books not yet tagged under 0018)", "phase": "S17a", "domain_tag": "new_printed candidate"}
n = 0
with open(out / "manifest.jsonl", "w", encoding="utf-8") as fo:
    for r in g:
        if not r["accepted"]:
            continue
        k = r["k"]; assert t[k]["text"] == r["text"]
        lid = f"s17a2_{k:05d}"
        shutil.copyfile(gen / f"g{k:05d}.png", out / "lines" / f"{lid}.png")
        (out / "lines" / f"{lid}.gt.txt").write_text(unicodedata.normalize("NFC", r["text"]).strip() + "\n", encoding="utf-8")
        fo.write(json.dumps({"id": lid, "image": f"lines/{lid}.png", "text": r["text"], "pby_id": t[k]["pby_id"],
                             "style_book": r["style_book"], "style_node": "unknown",
                             "gate": {x: r[x] for x in ("out_frac", "out_local", "min_cover", "stray_cc", "cer_r7", "cer_best")},
                             "image_sha256": sha(out / "lines" / f"{lid}.png")}, ensure_ascii=False) + "\n")
        n += 1
json.dump({"lines": n, **prov}, open(out / "summary.json", "w"), indent=1, ensure_ascii=False)
print(n)
