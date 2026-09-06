#!/bin/bash
# Vendors ffmpeg/ffprobe (vanilla upstream, i.e. plain Homebrew/system
# builds -- not the mobipeg-patched encoder), rclone, and atgame1, then
# builds the app with PyInstaller.
set -euo pipefail
cd "$(dirname "$0")"

VENDOR=vendor
mkdir -p "$VENDOR"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 1; }; }
need ffmpeg
need ffprobe
need rclone
need atgame1
need pyinstaller

cp "$(command -v ffmpeg)" "$VENDOR/ffmpeg"
cp "$(command -v ffprobe)" "$VENDOR/ffprobe"
cp "$(command -v rclone)" "$VENDOR/rclone"
cp "$(command -v atgame1)" "$VENDOR/atgame1"
chmod +x "$VENDOR"/*

pyinstaller build.spec --noconfirm
echo "Build complete: dist/"
