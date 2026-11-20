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
    for package in libraqm pkgconf jpeg zlib freetype little-cms2 openjpeg libtiff webp; do
      if brew list --formula "$package" >/dev/null 2>&1; then
        echo "Homebrew formula already installed: $package"
      else
        brew install "$package"
      fi
    done
    ;;
  *)
    echo "Unsupported runner OS for native Pillow/libraqm dependency installation: $(uname -s)" >&2
    exit 1
    ;;
esac
