#!/usr/bin/env bash
set -euo pipefail
source /heocr/in/job-env.sh
arm_pod_timer 4
ensure_tesseract
export OMP_THREAD_LIMIT=1 PYTHONDONTWRITEBYTECODE=1
python3 /heocr/in/train_pair.py /heocr/in /heocr/work/pair-training /heocr/out
