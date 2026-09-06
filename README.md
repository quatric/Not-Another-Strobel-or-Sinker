# Not Another Strobel or Sinker

Video editing software for girls.

A small tkinter GUI wrapped around bundled command-line tools (FFmpeg,
rclone). No network calls of its own, no telemetry, no bundled credentials
of any kind.

## Tabs

**AtGames** -- reproduces the `atgame1` filter chain (pixelation + audio
crush/pitch, a "deep-fry" effect) as a direct call into a bundled, vanilla
upstream FFmpeg build. Output is written next to the input as `<input>.mp4`.

**Pitch** -- converts a video (and every one of its subtitle streams)
between NTSC and PAL "pitch": the ~4.1% speed-and-pitch shift a film-rate
master picks up when it's played back at the other standard's frame rate.
Uses the actual ratio between the two rates, `25025/24000` (PAL's 25 fps
against NTSC's `24000/1001` fps film rate), applied consistently to video,
audio, and subtitle timestamps so everything stays in sync.

**Drive** -- a thin GUI over a bundled `rclone`. The app ships with **no**
config file and **no** remotes baked in. On first use you either import an
existing `rclone.conf` from disk or run rclone's own interactive `config`
wizard (opened in a real terminal) to add a remote; either way, the result
is written only to this app's own private config directory
(`~/Library/Application Support/NotAnotherStrobelOrSinker/rclone.conf` on
macOS), never into the app bundle or the source tree.

## Building

```bash
./build.sh
```

This copies `ffmpeg`, `ffprobe`, and `rclone` from your `PATH` into `vendor/`
(not committed -- see `.gitignore`) and then runs `pyinstaller build.spec`.
The finished app is written to `dist/`. Works on macOS, Linux, and Windows
(via Git Bash/MSYS -- e.g. `windows-latest` GitHub Actions runners).

Requirements: Python 3 with `pyinstaller`, and `ffmpeg`/`ffprobe`/`rclone`
all present on `PATH`.

CI (`.github/workflows/build.yml`) builds all three platforms on every push
and uploads each as an artifact; see that file for the exact package-manager
commands used per OS (Homebrew, apt, Chocolatey).

## Running from source

```bash
python3 gui.py
```

Falls back to whatever `ffmpeg`/`ffprobe`/`rclone` are on `PATH` if nothing
has been vendored into `vendor/` yet.

## Licensing

FFmpeg is bundled with GPL-licensed components enabled (libx264, libx265,
libvpx, libsvtav1), which means any redistribution of this app must comply
with the GPL. This project is therefore licensed under the GPLv3 -- see
`LICENSE`. rclone is MIT-licensed and imposes no additional restrictions
here.

## Contact

quatricsoftware@gmail.com. No support will be provided for this tool.

## Credits

- [FFmpeg](https://ffmpeg.org)
- [rclone](https://rclone.org)

Copyright (c) 2026 quatric
