#!/usr/bin/env bash
# S17a dose arm, after generate.py: gates -> sheets -> export -> lstmf -> arm list. Waits on battery (AC only).
# Stops before training: heocr-eval's check_train_overlap.py must report CLEAN first.
set -euo pipefail
H=/Users/shaypalachy/agents/environments/opensource/projects/heocr/tasks; S=$H/s17a-scanifier; cd $S
ac() { until pmset -g batt | grep -q "AC Power"; do sleep 60; done; }
e() { DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run --no-project --python 3.12 --with torch==2.12.0 --with numpy==2.4.6 --with scipy==1.17.1 --with pillow==12.2.0 --with rapidfuzz python "$@"; }
G=intermediates/addon2_gen
until grep -q "median_cer" intermediates/addon2_gen.log 2>/dev/null; do grep -q "Traceback" intermediates/addon2_gen.log 2>/dev/null && { echo "DOSE_FAILED: generate"; exit 1; }; sleep 60; done
[ "$(wc -l < $G/gen.jsonl | tr -d ' ')" = 20000 ] || { echo "DOSE_FAILED: gen.jsonl not 20000 lines"; exit 1; }
echo "$(date '+%F %T') gates"; ac
e scripts/gates.py $G --book-of intermediates/pairs_v2/style_books.jsonl > intermediates/addon2_gates.log 2>&1
echo "$(date '+%F %T') sheets"
e scripts/gate_sheets.py $G dose2/sheets --v11 outputs/s17a_addon_v1.1/manifest.jsonl > dose2/digits.log 2>&1
echo "$(date '+%F %T') export"
e scripts/export_addon_v2.py $G intermediates/addon2_texts outputs/s17a_addon_v2
echo "$(date '+%F %T') lstmf"; ac
mkdir -p runs/dose2/addon2_src/train/s17a2
for f in outputs/s17a_addon_v2/lines/*; do ln -sf "$S/$f" runs/dose2/addon2_src/train/s17a2/; done
cd $H && e r8-tesseract/scripts/make_lstmf.py s17a-scanifier/runs/dose2/addon2_src s17a-scanifier/runs/dose2/addon2_lstmf --workers 8 > s17a-scanifier/runs/dose2/make_lstmf.out 2>&1
echo "$(date '+%F %T') list"
e s17a-scanifier/scripts/build_dose_list.py s17a-scanifier/runs/dose2/addon2_lstmf/train.list s17a-scanifier/runs/dose2/train_dose.list > s17a-scanifier/runs/dose2/build_list.out 2>&1
echo "$(date '+%F %T') DOSE_READY_FOR_EVAL_CHECK"
