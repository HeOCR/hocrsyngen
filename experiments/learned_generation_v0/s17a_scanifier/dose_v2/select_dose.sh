#!/usr/bin/env bash
# S17a dose arm selection (pre-registered): line_fold_v1 CER from score_lines.py on sel.list over every checkpoint and
# snapshot; lowest CER wins (ties: lower WER). Packs it to runs/dose2/models/arm/heb.traineddata and scores it as
# "s17a-dose2" on every set dose_decide.py reads, then runs dose_decide.py.
set -euo pipefail
H=/Users/shaypalachy/agents/environments/opensource/projects/heocr/tasks; R8B=$H/r8b-tesseract; D=$H/s17a-scanifier/runs/dose2; cd $H
[ "$(cat $D/arm.exit 2>/dev/null)" = 0 ] || { echo "DOSE_SELECT_FAILED: arm did not exit 0"; exit 1; }
grep -q "Finished!" $D/arm.out || { echo "DOSE_SELECT_FAILED: no Finished!"; exit 1; }
py() { uv run --no-project --with rapidfuzz --with numpy --with pillow python "$@"; }
if [ "${SKIP_SEL:-0}" != 1 ]; then
: > $D/sel_scores.tsv
for c in $D/arm/heb*.checkpoint; do
  n=dose2_$(basename $c .checkpoint)
  py eval-domains/scripts/score_lines.py run sel "$n=$c" --starter
  py -c "import sys; sys.path.insert(0,'eval-domains/scripts'); import score_lines as S; r=S.score('sel',['$n'],only='r8b-tesseract/data/sel.list',quiet=True)['$n']; print(f\"{r['cer']}\t{r['wer']}\t$c\")" | tee -a $D/sel_scores.tsv
done
fi
# awk reads all its input, so sort never gets SIGPIPE under pipefail (head -1 killed the 2026-11-13 run here).
best=$(sort -t$'\t' -k1,1g -k2,2g $D/sel_scores.tsv | awk -F'\t' 'NR==1{print $3}'); echo "selected $best" | tee $D/selected.txt
mkdir -p $D/models/arm; ln -sfn /opt/homebrew/share/tessdata/configs $D/models/arm/configs
lstmtraining --stop_training --continue_from $best --traineddata $R8B/starter/heb/heb.traineddata --model_output $D/models/arm/heb.traineddata
shasum -a 256 $D/models/arm/heb.traineddata | tee -a $D/selected.txt
for s in olb_dev kevarpirezikhron00haco.full yediothateva06bernuoft.full brainin_v3 brainin_nli silman bodek reshumot_dev rab_dev ws_dev; do
  py eval-domains/scripts/score_lines.py run $s "s17a-dose2=$D/models/arm/heb.traineddata"
done
py s17a-scanifier/scripts/dose_decide.py s17a-dose2 $D/train_dose.list $D/decision.json | tee $D/decision.out
echo "DOSE_SELECT_DONE"
