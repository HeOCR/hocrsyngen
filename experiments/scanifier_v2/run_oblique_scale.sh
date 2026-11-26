#!/usr/bin/env bash
# SPDX-License-Identifier: CC0-1.0
set -euo pipefail
umask 077
started=$SECONDS
requested_lines=${1:?requested lines}
runtime=${2:?work seconds}
mkdir -p work out
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export OMP_THREAD_LIMIT=1 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_XET=1
export TESSDATA_PREFIX="$PWD/in/tessdata"

archive() {
    local status=$?
    trap - EXIT
    set +e
    if [[ -s work/views/generation_manifest.json ]]; then
        tar -cf out/output.tar -C work/views generation_manifest.json model-weights.json inventory.jsonl images layout
    else
        tail -c 14000 work/scale.log > work/diagnostic.txt
        tar -cf out/output.tar -C work diagnostic.txt
    fi
    exit "$status"
}
trap archive EXIT
exec >work/scale.log 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=2 -qq update
apt-get -o Acquire::Retries=2 -qq install -y --no-install-recommends \
    ca-certificates curl tesseract-ocr xz-utils libgl1 libgomp1 libsm6 libx11-6 libxext6 libxi6 libxrender1 libxfixes3

mkdir -p work/renderer work/blender
tar -xf in/renderer.tar -C work/renderer
curl -fsSL --retry 3 --connect-timeout 15 --max-time 600 \
    https://download.blender.org/release/Blender5.3/blender-5.3.0-linux-x64.tar.xz \
    -o work/blender.tar.xz
printf '%s  %s\n' dacb8264197a3f7fda6001285a5a506fc97ee943881261c2c3bd63c882f22e05 work/blender.tar.xz |
    sha256sum -c
tar -xf work/blender.tar.xz -C work/blender --strip-components=1
blender="$PWD/work/blender/blender"
device=OPTIX
if ! "$blender" -b --factory-startup --python-exit-code 1 --python-expr \
     "import bpy; p=bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type='OPTIX'; p.refresh_devices(); assert any(d.type=='OPTIX' for d in p.devices)"; then
    device=CUDA
    "$blender" -b --factory-startup --python-exit-code 1 --python-expr \
        "import bpy; p=bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type='CUDA'; p.refresh_devices(); assert any(d.type=='CUDA' for d in p.devices)"
fi

python3 -m pip -q install --disable-pip-version-check --only-binary=:all: \
    'diffusers==0.37.1' 'transformers==5.9.0' 'accelerate==1.13.0' \
    'huggingface-hub==1.13.0' 'safetensors==0.7.0' \
    'opencv-python-headless==4.13.0.92' 'numpy==2.3.1' 'Pillow==11.3.0'
export PYTHONPATH="$PWD/work/renderer:$PWD/work/renderer/src"
remaining=$(( runtime - (SECONDS - started) ))
(( remaining > 90 ))
python3 -u -m experiments.scanifier_v2.oblique_scale in work/views \
    --weights in/model-weights.json --assets in/scene-assets/assets.json \
    --fonts-guard work/renderer/src/hocrsyngen/data/fonts_excluded.json \
    --blender "$blender" --device "$device" --requested-lines "$requested_lines" \
    --deadline-seconds "$remaining"
