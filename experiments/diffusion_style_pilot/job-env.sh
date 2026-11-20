#!/usr/bin/env bash
# Common setup for a single bounded heocr-compute pod job.
set -euo pipefail

arm_pod_timer() {
    local wall_hours=$1 ttl
    ttl=$(python3 - "$wall_hours" <<'PY'
import datetime as dt
import json
from pathlib import Path
import sys

run_id = json.loads(Path('/heocr/out/pod.json').read_text())['run_id']
start = dt.datetime.strptime(run_id[:15], '%Y%m%d-%H%M%S').replace(tzinfo=dt.timezone.utc)
deadline = start + dt.timedelta(hours=int(sys.argv[1]))
remaining = int((deadline - dt.datetime.now(dt.timezone.utc)).total_seconds())
if remaining <= 600:
    raise SystemExit('No time left beyond the result transfer window')
print(remaining)
PY
)
    if [[ $(sh /heocr/deadman.sh "$ttl") != armed ]]; then
        printf '%s\n' 'Refusing to start without a pod self-termination timer.' >&2
        return 1
    fi
}

ensure_tesseract() {
    local tess_tag=5.5.3 tess_commit=db0ec62f81b0737fbbe184d8fea40af5738f8eef
    if ! command -v lstmtraining >/dev/null || ! command -v tesseract >/dev/null || \
        [[ $(tesseract --version 2>&1 | head -n 1) != "tesseract $tess_tag" ]]; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq g++ make autoconf automake libtool pkg-config git python3-venv \
            libleptonica-dev libicu-dev libpango1.0-dev libcairo2-dev libgl1 libglib2.0-0t64 > /heocr/out/tess-dependencies.log
        git clone --quiet --depth 1 --branch "$tess_tag" https://github.com/tesseract-ocr/tesseract.git /heocr/work/tesseract-src
        test "$(git -C /heocr/work/tesseract-src rev-parse HEAD)" = "$tess_commit"
        (
            cd /heocr/work/tesseract-src
            ./autogen.sh
            ./configure --prefix=/opt/heocr-tess --disable-doc
            make -j"$(nproc)"
            make install
            make training -j"$(nproc)"
            make training-install
        ) > /heocr/out/tess-build.log 2>&1
        export PATH="/opt/heocr-tess/bin:$PATH" LD_LIBRARY_PATH="/opt/heocr-tess/lib:${LD_LIBRARY_PATH:-}"
    fi
    test "$(tesseract --version 2>&1 | head -n 1)" = "tesseract $tess_tag"
    command -v combine_tessdata >/dev/null
    command -v lstmtraining >/dev/null
    tesseract --version > /heocr/out/tesseract-version.log 2>&1
}
