"""Aggregate-only probe 3: for missed decimals/sections/dates whose groups are present, contiguous or not, in which
order, and with or without whitespace between the groups. Counts only."""
import sys, re
from collections import Counter
from pathlib import Path
DB = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(DB / "scripts")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import measures as M
from report import out_text, j
import numgap as G
RUN = DB / "runs" / sys.argv[2]; reader = sys.argv[3]
rj = j(RUN / "run.json"); recs = {x["item"]: x for x in rj["results"][reader]}
SEP = re.compile(r"[.,/]")
P = lambda gs, gap: r"(?<![\d.,/])" + ("(?:" + gap + ")").join(map(re.escape, gs)) + r"(?![\d])"  # gap grouped: an ungrouped | split the whole pattern (pipeline, 2026-11-18)
for cell, cases in G.CELLS.items():
    c = Counter(); tot = 0
    for item in [i for i in recs if i.rsplit("/", 1)[0] in cases]:
        hyp = (out_text(RUN, reader, item) or "") if recs[item]["status"] == "ok" else ""
        R = G.toks("\n".join(G.ref_pages_of(item))); H = G.toks(hyp)
        hf = M.fold(M.clean(hyp))
        for t, n in (R - H).items():
            tot += n
            sh = G.shape(t)
            if sh not in ("date", "section_multi", "decimal_or_section"):
                c["other_shapes"] += n; continue
            g = SEP.split(t); s = SEP.findall(t)
            rev_exact = s[::-1] and "".join(x + y for x, y in zip(g[::-1], s[::-1] + [""]))
            if re.search(P(g[::-1], r"[.,/]"), hf): k = "reversed_groups_no_space"
            elif re.search(P(g[::-1], r"\s*[.,/]?\s+[.,/]?\s*|\s+"), hf): k = "reversed_groups_with_space"
            elif re.search(P(g, r"\s*[.,/]?\s+[.,/]?\s*|\s+"), hf): k = "same_order_with_space"
            elif re.search(P(g, r""), hf) or re.search(P(g[::-1], r""), hf): k = "separators_dropped"
            elif re.search(P(g, r"[.,/]"), hf) or re.search(P(g, r"[.,/][.,/]"), hf): k = "same_order_sep_changed_or_doubled"
            elif all(re.search(r"(?<!\d)" + re.escape(x) + r"(?!\d)", hf) for x in g): k = "groups_scattered"
            elif any(re.search(r"(?<!\d)" + re.escape(x) + r"(?!\d)", hf) for x in g if len(x) >= 2): k = "some_groups_only"
            else: k = "no_group"
            c[(sh, k)] += n
    print(f"== {reader} {cell}  misses {tot}")
    for key, n in sorted(c.items(), key=lambda x: -x[1]):
        print(f"   {str(key):60s} {n}")
