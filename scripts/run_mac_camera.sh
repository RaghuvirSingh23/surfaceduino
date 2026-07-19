#!/bin/sh
set -eu

arduino_adb="${ARDUINO_ADB:-$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0/adb}"
board_serial="${SURFACEOS_BOARD_SERIAL:-505816694}"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

"$arduino_adb" -s "$board_serial" forward tcp:17000 tcp:7000 >/dev/null
exec python3 "$script_dir/mac_camera_feed.py" "$@"
