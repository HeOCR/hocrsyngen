"""Shot list and the one-page Hebrew shot sheet for the HeOCR calibration pack v1.

  python3 experiments/scanifier_v2/calibration_pack/shot_sheet.py OUT_DIR

Schedule (deterministic, no seed):
  - P01 (target): every condition on every phone, B twice, J on a dark and on a wooden table: 10 frames per phone.
  - P02-P08: on every phone, A plus three of B C D E G I J, rotated so each page gets all seven over the three phones.
  - P09/P10 (thin copies of P02/P03): H on every phone.
  - F is never shot: it is the A frame sent through Telegram.
Writes OUT/shot_list.csv, OUT/SHOT_SHEET.md, OUT/shot_sheet.html and OUT/shot_sheet.pdf (A4, one page, printed from the
HTML by headless Chrome, which shapes and orders right-to-left text correctly).
"""
import csv, re, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FONT = REPO / "src/hocrsyngen/data/synthetic/fonts/Assistant-wght.ttf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PHONES = [("p9", "Pixel 9 Pro"), ("p4a", "Pixel 4a"), ("a33", "Galaxy A33")]
OTHERS = ["B", "C", "D", "E", "G", "I", "J"]
COND = {
    "A": "ישר מלמעלה, אור טוב, יד יציבה. זו תמונת הבסיס.",
    "B": "ביד, באור עמום, כך שהמהירות יורדת לבערך <span dir='ltr'>1/25–1/33</span> שנייה: טשטוש תנועה.",
    "C": "בזווית של <span dir='ltr'>30–45</span> מעלות: פרספקטיבה, והקצה הרחוק יוצא לא בפוקוס.",
    "D": "באור עמום מאוד, כך שה־ISO עולה לבערך <span dir='ltr'>2,000–3,200</span>: רעש.",
    "E": "ישר מלמעלה, ולשמור כמו שהטלפון שומר. לא לסובב: סיבובים שגויים הם חלק מהעניין.",
    "F": "לא מצלמים: שולחים את תמונת A בטלגרם \"כתמונה\" ושומרים את מה שהתקבל, וגם את המקור.",
    "G": "Adobe Scan במצב מסמך, שמירה כ־JPG.",
    "H": "הדף על נייר דק (P09/P10) מונח על דף מודפס אחר: דפוס שנראה דרך הנייר.",
    "I": "אגודל מכסה חלק מהשוליים.",
    "J": "על רקע: שולחן כהה (Jd) או שולחן עץ (Jw).",
}


def schedule():
    rows = []
    for j, (code, name) in enumerate(PHONES):
        for c in ["A", "B", "B2", "C", "D", "E", "G", "I", "Jd", "Jw"]:
            rows.append(("P01", c, code))
        for i, pg in enumerate(range(2, 9)):
            cs = ["A"] + [OTHERS[(3 * j + i + k) % 7] for k in range(3)]
            for c in cs:
                rows.append((f"P{pg:02d}", ("Jd" if pg % 2 == 0 else "Jw") if c == "J" else c, code))
        for pg in ("P09", "P10"):
            rows.append((pg, "H", code))
    for pg in [f"P{k:02d}" for k in range(2, 9)]:   # every page gets all seven over the phones
        got = {r[1][0] for r in rows if r[0] == pg}
        assert set(OTHERS) <= got, (pg, got)
    return rows


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    rows = schedule()
    with open(out / "shot_list.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["page", "condition", "phone", "file_name"])
        for pg, c, ph in rows:
            w.writerow([pg, c, ph, f"{pg}-{c}-{ph}.jpg"])
    tele = sum(1 for r in rows if r[1] == "A")
    by_page = {}
    for pg, c, ph in rows:
        by_page.setdefault(pg, {}).setdefault(ph, []).append(c)
    head = "<tr><th>דף</th>" + "".join(f"<th>{n} (<span dir='ltr'>{c}</span>)</th>" for c, n in PHONES) + "</tr>"
    body = "".join("<tr><td>%s</td>%s</tr>" % (pg, "".join(f"<td dir='ltr' style='text-align: right'>{' '.join(by_page[pg].get(c, []))}</td>" for c, _ in PHONES))
                   for pg in sorted(by_page))
    conds = "".join(f"<li><b>{k}</b> – {v}</li>" for k, v in COND.items())
    html = f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>
@font-face {{ font-family: heb; src: url("{FONT.name}"); font-weight: 200 800; }}
@page {{ size: A4; margin: 11mm; }}
body {{ font-family: heb; font-size: 9.5pt; line-height: 1.3; margin: 0; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 0.6pt solid #000; padding: 1.5pt 4pt; text-align: right; }}
th {{ background: #eee; }} td:first-child {{ font-weight: 700; }} ul {{ padding-right: 14pt; margin: 0; }}
</style></head><body>
<h2 style="font-size: 14pt; margin: 0">ערכת כיול HeOCR v1 – דף צילום</h2>
<p style="margin: 2pt 0"><b>הדפסה:</b> בגודל אמיתי (100%, לא "התאם לדף"). P01 בצבע. <span dir='ltr'>P01–P08</span> על נייר רגיל (80 גרם), <span dir='ltr'>P09–P10</span> על נייר דק (<span dir='ltr'>60–70</span> גרם). לרשום את דגם המדפסת.</p>
<p style="margin: 2pt 0"><b>לא מצלמים שוב תמונה שיצאה גרועה – זה בדיוק מה שאנחנו צריכים.</b> כל הדף בתמונה, כולל ארבעת הריבועים בפינות (גם בתנאי I).</p>
<h3 style="font-size: 11pt; margin: 4pt 0 1pt 0">התנאים</h3><ul style="margin: 0">{conds}</ul>
<h3 style="font-size: 11pt; margin: 4pt 0 1pt 0">מה לצלם בכל טלפון</h3>
<table border="1" cellspacing="0" cellpadding="2" style="border-collapse: collapse; font-size: 8.5pt">{head}{body}</table>
<p style="margin: 3pt 0">B2 = עוד תמונה בתנאי B. בסך הכול {len(rows)} תמונות ({len(rows) // 3} בכל טלפון), ועוד {tele} שליחות טלגרם (F) של תמונות A.</p>
<p style="margin: 2pt 0"><b>שמות קבצים:</b> דף-תנאי-טלפון, למשל <span dir="ltr">P04-C-p4a.jpg</span>, <span dir="ltr">P01-B2-p9.jpg</span>, <span dir="ltr">P02-F-a33.jpg</span> (העותק שהתקבל בטלגרם). הקוד בתחתית הדף מגבה את השם.</p>
<p style="margin: 2pt 0"><b>העברה:</b> המקורות דרך Google Photos באיכות מקורית ("Original quality"), הורדה של הקובץ המקורי. בלי צילומי מסך ובלי שיתוף בקישור. לשמור על נתוני ה־EXIF.</p>
<p style="margin: 2pt 0">התמונות האלה לכיול ול־dev בלבד, אף פעם לא לבדיקה (test). PS-v1 לא נוגעים.</p>
</body></html>"""
    md = ["# ערכת כיול HeOCR v1 – דף צילום", "", "**לא מצלמים שוב תמונה שיצאה גרועה – זה בדיוק מה שאנחנו צריכים.**", "",
          "הדפסה בגודל אמיתי (100%). P01 בצבע. P09-P10 על נייר דק.", "", "## התנאים", ""]
    md += [f"- **{k}** – {re.sub(r'</?span[^>]*>', '', v)}" for k, v in COND.items()]
    md += ["", "## מה לצלם בכל טלפון", "", "| דף | " + " | ".join(f"{n} ({c})" for c, n in PHONES) + " |", "|---|---|---|---|"]
    md += [f"| {pg} | " + " | ".join(" ".join(by_page[pg].get(c, [])) for c, _ in PHONES) + " |" for pg in sorted(by_page)]
    md += ["", f"B2 = עוד תמונה בתנאי B. בסך הכול {len(rows)} תמונות, ועוד {tele} שליחות טלגרם (F) של תמונות A.", "",
           "**שמות קבצים:** דף-תנאי-טלפון, למשל `P04-C-p4a.jpg`. **העברה:** Google Photos באיכות מקורית, הורדת המקור, עם EXIF.", "",
           "התמונות לכיול ול־dev בלבד, אף פעם לא ל־test."]
    (out / "SHOT_SHEET.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "shot_sheet.html").write_text(html, encoding="utf-8")
    shutil.copy(FONT, out / FONT.name)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={(out / 'shot_sheet.pdf').resolve()}",
                    (out / "shot_sheet.html").resolve().as_uri()], check=True, capture_output=True, timeout=120)
    (out / FONT.name).unlink()
    n = (out / "shot_sheet.pdf").read_bytes().count(b"/Type /Page\n") or "?"
    print({"frames": len(rows), "per_phone": len(rows) // 3, "telegram_sends": tele, "pdf_pages": n})


if __name__ == "__main__":
    main()
