#!/usr/bin/env bash
set -euo pipefail

case "$(uname -s)" in
  Linux)
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
      libraqm-dev \
      libfribidi-dev \
      libharfbuzz-dev \
      libjpeg-dev \
      zlib1g-dev \
      libfreetype6-dev \
      liblcms2-dev \
      libopenjp2-7-dev \
      libtiff-dev \
      libwebp-dev \
      pkg-config
    ;;
  Darwin)
    brew update
    brew install libraqm pkg-config jpeg zlib freetype lcms2 openjpeg libtiff webp
    ;;
  *)
    echo "Unsupported runner OS for native Pillow/libraqm dependency installation: $(uname -s)" >&2
    exit 1
    ;;
esac
