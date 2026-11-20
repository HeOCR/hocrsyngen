#!/bin/bash
# R8c step 0: which degradation makes R8b-main lose to R7 the way it does on Brainin IA? Dev-only diagnostics.
set -euo pipefail
cd ~/agents/environments/opensource/projects/heocr/tasks
A=s17a-scanifier/r8c-aug; D=$A/diagnostics; L=eval-domains/intermediates/r8b_score/lists
PY="uv run --no-project --with numpy --with scipy --with pillow --with rapidfuzz python"
R7=r8-tesseract/models/r7/heb.traineddata; R8B=$(ls -d eval-domains/intermediates/score_lines/models/r8b-main-fold/*.traineddata 2>/dev/null || echo eval-domains/intermediates/score_lines/models/r8b-main-fold)
cat $L/kevarpirezikhron00haco.heldout.list $L/yediothateva06bernuoft.heldout.list > $D/kyh.list
declare -A V=( [levels]=levels [speckle]=speckle [downscale]=downscale [unsharp]=unsharp [grain]=grain [jpeg]=jpeg
               [down_sharp]=downscale,unsharp [all]=levels,speckle,downscale,unsharp,grain,jpeg [all_blur]=levels,speckle,downscale,blur,grain,jpeg )
for v in levels speckle downscale unsharp grain jpeg down_sharp all all_blur; do
  s=r8c_diag_$v
  [ -s $D/$v/aug.list ] || $PY $A/scripts/scan_aug.py $D/kyh.list $D/$v --ops ${V[$v]} --workers 10
  cp $D/$v/aug.list $L/$s.list
  [ -s eval-domains/intermediates/score_lines/$s/eval.list ] || $PY eval-domains/scripts/score_lines.py build $s
  for m in r7=$R7 r8b-main-fold=$R8B; do
    n=${m%%=*}; [ -s eval-domains/intermediates/score_lines/$s/out/$n.txt ] || $PY eval-domains/scripts/score_lines.py run $s $m &
  done; wait
done
# size diagnostic: Brainin IA upscaled to a 37 px band
s=r8c_diag_ia_up37
[ -s $D/ia_up37/aug.list ] || $PY $A/scripts/scan_aug.py $L/brainin_v3.list $D/ia_up37 --ops "" --upscale-band 37 --workers 10
cp $D/ia_up37/aug.list $L/$s.list
[ -s eval-domains/intermediates/score_lines/$s/eval.list ] || $PY eval-domains/scripts/score_lines.py build $s
for m in r7=$R7 r8b-main-fold=$R8B; do n=${m%%=*}; [ -s eval-domains/intermediates/score_lines/$s/out/$n.txt ] || $PY eval-domains/scripts/score_lines.py run $s $m & done; wait
echo step0 done
