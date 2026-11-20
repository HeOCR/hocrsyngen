#!/usr/bin/env bash
set -euo pipefail
source /heocr/in/job-env.sh
arm_pod_timer 6
ensure_tesseract
export OMP_THREAD_LIMIT=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 PYTHONDONTWRITEBYTECODE=1
python3 -m venv --system-site-packages /heocr/work/venv
runtime=/heocr/work/venv/bin/python
"$runtime" -m pip install --no-index --find-links /heocr/in/wheels --require-hashes \
    -r /heocr/in/gpu-requirements.lock > /heocr/out/python-install.log 2>&1
"$runtime" -m pip freeze > /heocr/out/python-versions.log
"$runtime" /heocr/in/level2.py /heocr/in /heocr/work/paired-job /heocr/out
