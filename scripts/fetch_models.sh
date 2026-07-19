#!/usr/bin/env bash
# Download the MediaPipe hand models used by the LiteRT landmark tracker.
# These are Google's own BlazePalm + hand-landmark tflite networks.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="$repo_dir/models"
mkdir -p "$models_dir"

base="https://storage.googleapis.com/mediapipe-assets"

fetch() {
  local name="$1"
  echo "Fetching $name"
  curl -fsSL -o "$models_dir/$name" "$base/$name"
}

fetch "palm_detection_full.tflite"
fetch "hand_landmark_full.tflite"

echo "Models in $models_dir:"
ls -lh "$models_dir"
