#!/bin/bash
# Vendors ffmpeg/ffprobe/rclone (vanilla upstream/community builds -- not
# the mobipeg-patched encoder) from whatever's on PATH, then builds the app
# with PyInstaller. Works on macOS, Linux, and Windows (via Git Bash/MSYS,
# e.g. in GitHub Actions' windows-latest runners).
set -euo pipefail
cd "$(dirname "$0")"

case "$OSTYPE" in
  msys*|cygwin*|win32*) EXE=".exe" ;;
  *) EXE="" ;;
esac

VENDOR=vendor
mkdir -p "$VENDOR"
# PyInstaller's COLLECT step leaves vendored binaries read-only; clear that
# before re-copying fresh ones on a rebuild.
chmod +w "$VENDOR"/* 2>/dev/null || true
rm -f "$VENDOR/ffmpeg$EXE" "$VENDOR/ffprobe$EXE" "$VENDOR/rclone$EXE"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 1; }; }
need ffmpeg
need ffprobe
need rclone
need pyinstaller

cp "$(command -v ffmpeg)" "$VENDOR/ffmpeg$EXE"
cp "$(command -v ffprobe)" "$VENDOR/ffprobe$EXE"
cp "$(command -v rclone)" "$VENDOR/rclone$EXE"
chmod +x "$VENDOR"/*

pyinstaller build.spec --noconfirm
echo "Build complete: dist/"
