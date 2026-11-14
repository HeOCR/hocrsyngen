#!/usr/bin/env bash
# S17a dose arm: R8b's train.sh recipe unchanged (continue from R7 lr1e4 heb_0.634_52608_117100, R8 starter, lr 1e-4
# with reset, target 0.01, no eval list, one epoch = list length, heb_checkpoint snapshot every 20 min, final snapshot),
# on runs/dose2/train_dose.list. Starts SIGSTOPped; the power scheduler releases it on AC.
set -uo pipefail
kill -STOP $$
H=/Users/shaypalachy/agents/environments/opensource/projects/heocr/tasks; R7=$H/r7-tesseract-real; R8B=$H/r8b-tesseract
cd $H/s17a-scanifier/runs/dose2
mkdir -p arm; rm -f arm.exit; LIST=train_dose.list; ITERS=$(wc -l < $LIST | tr -d ' ')
echo "$(date '+%F %T') start dose arm, $ITERS iterations (one epoch)"
( while sleep 1200; do [ -f arm/heb_checkpoint ] && cp arm/heb_checkpoint "arm/heb_snap_$(date +%H%M%S).checkpoint"; done ) &
SNAP=$!
lstmtraining --continue_from $R7/runs/lr1e4/heb_0.634_52608_117100.checkpoint --old_traineddata $R7/starter/heb/heb.traineddata \
  --traineddata $R8B/starter/heb/heb.traineddata --model_output arm/heb \
  --train_listfile $LIST \
  --learning_rate 0.0001 --reset_learning_rate \
  --max_iterations $ITERS --target_error_rate 0.01 --debug_interval -1
rc=$?
kill $SNAP 2>/dev/null; cp arm/heb_checkpoint "arm/heb_snap_final.checkpoint" 2>/dev/null || true
echo $rc > arm.exit; echo "$(date '+%F %T') lstmtraining exit $rc"
exit $rc
