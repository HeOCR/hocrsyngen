"""Aggregate-only probe: for missed decimals, sections and dates, where their digit groups are in the output.

    python number_assembly.py <dbench dir> <run id> <reader>     # runs the known-string self-test first
    python number_assembly.py --self-test

For each missed token of shape date, section_multi or decimal_or_section (numgap.shape), it finds out whether its
digit groups are in the reader's folded output, contiguous or not, in which order, and with or without whitespace
between them. It prints counts only, never text.

The patterns are pinned by KNOWN, a table of known strings, which is checked before every run. This was added after
pipeline found (2026-11-18) that an ungrouped `|` in a gap pattern made the whole regex an alternation, which
inflated "reversed_groups_with_space" about 50 times. See PLAN.md §2.2.1.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

SEP = re.compile(r"[.,/]")
GAP_SPACE = r"\s*[.,/]?\s+[.,/]?\s*|\s+"   # some whitespace between groups, optionally with a separator


# Not inside a longer number: no digit, and no separator-then-digit, on either side.
LEFT = r"(?<!\d)(?<!\d[.,/])"
RIGHT = r"(?!\d)(?![.,/]\d)"


def pattern(groups: list[str], gap: str) -> str:
    """The groups in this order, joined by `gap`, not inside a longer number. The gap is grouped, so an alternation
    inside it stays inside it."""
    return LEFT + ("(?:" + gap + ")").join(map(re.escape, groups)) + RIGHT


def _alone(x: str) -> str:
    return LEFT + re.escape(x) + RIGHT


def classify(token: str, hyp: str) -> str:
    """Class of a missed multi-group token against the reader's folded and cleaned output `hyp`."""
    g = SEP.split(token)
    if re.search(pattern(g[::-1], r"[.,/]"), hyp):
        return "reversed_groups_no_space"
    if re.search(pattern(g[::-1], GAP_SPACE), hyp):
        return "reversed_groups_with_space"
    if re.search(pattern(g, GAP_SPACE), hyp):
        return "same_order_with_space"
    if re.search(pattern(g, r""), hyp) or re.search(pattern(g[::-1], r""), hyp):
        return "separators_dropped"
    if re.search(pattern(g, r"[.,/]"), hyp) or re.search(pattern(g, r"[.,/][.,/]"), hyp):
        return "same_order_sep_changed_or_doubled"
    if all(re.search(_alone(x), hyp) for x in g):
        return "groups_scattered"
    if any(re.search(_alone(x), hyp) for x in g if len(x) >= 2):
        return "some_groups_only"
    return "no_group"


# (missed token, reader output, expected class). Invented strings, no corpus text.
KNOWN = [
    ("3.1", "סעיף 1.3 קובע", "reversed_groups_no_space"),
    ("3.1", "סעיף 1 .3 קובע", "reversed_groups_with_space"),
    ("3.1", "סעיף 1 3 קובע", "reversed_groups_with_space"),
    ("3.1", "סעיף 3. 1 קובע", "same_order_with_space"),
    ("3.1", "סעיף 31 קובע", "separators_dropped"),
    ("3.1", "סעיף 3,1 קובע", "same_order_sep_changed_or_doubled"),
    ("3.1", "סעיף 3..1 קובע", "same_order_sep_changed_or_doubled"),
    # the bug: a lone group next to whitespace elsewhere must not count as reversed-with-space
    ("3.1", "בסעיף 3 ובפסקה 1 כאן", "groups_scattered"),
    ("3.1", "שורה 3 אחרת", "no_group"),
    ("3.1", "13.5 ו-3.12", "no_group"),           # groups only inside longer numbers do not count
    ("3.1", "בסעיף 3 ו-1.5", "no_group"),         # nor a group that starts a longer number
    ("17.11.2026", "17.11.2026.5", "no_group"),   # the whole token inside a longer number does not count
    ("2.2.4", "4. ההגדרות", "no_group"),          # a label cut to its last piece: 1-digit groups never count alone
    ("2.2.4", "2 ו-2 ו-4 בנפרד", "groups_scattered"),
    ("17.11.2026", "2026.11.17", "reversed_groups_no_space"),
    ("17.11.2026", "2026 .11 .17", "reversed_groups_with_space"),
    ("17.11.2026", "ביום 17 .11 .2026", "same_order_with_space"),
    ("17.11.2026", "ביום 17112026", "separators_dropped"),
    ("17.11.2026", "שנת 2026 בלבד", "some_groups_only"),
    ("17.11.2026", "ללא תאריך", "no_group"),
]


def self_test() -> None:
    bad = [(t, h, want, classify(t, h)) for t, h, want in KNOWN if classify(t, h) != want]
    if bad:
        raise SystemExit("number_assembly self-test failed:\n" + "\n".join(f"  {t!r} in {h!r}: want {w}, got {g}"
                                                                         for t, h, w, g in bad))


def main(argv: list[str]) -> None:
    self_test()
    if argv[1:] == ["--self-test"]:
        print(f"self-test ok ({len(KNOWN)} known strings)")
        return
    db = Path(argv[1]).resolve()
    sys.path.insert(0, str(db / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import measures as M  # eval's frozen measures (NUM, fold, clean)
    import numgap as G
    from report import j, out_text
    run, reader = db / "runs" / argv[2], argv[3]
    recs = {x["item"]: x for x in j(run / "run.json")["results"][reader]}
    for cell, cases in G.CELLS.items():
        c, tot = Counter(), 0
        for item in [i for i in recs if i.rsplit("/", 1)[0] in cases]:
            hyp = (out_text(run, reader, item) or "") if recs[item]["status"] == "ok" else ""
            R, H = G.toks("\n".join(G.ref_pages_of(item))), G.toks(hyp)
            hf = M.fold(M.clean(hyp))
            for t, n in (R - H).items():
                tot += n
                sh = G.shape(t)
                c[(sh, classify(t, hf)) if sh in ("date", "section_multi", "decimal_or_section") else "other_shapes"] += n
        print(f"== {reader} {cell}  misses {tot}")
        for key, n in sorted(c.items(), key=lambda x: -x[1]):
            print(f"   {str(key):60s} {n}")


if __name__ == "__main__":
    main(sys.argv)
