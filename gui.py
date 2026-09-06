#!/usr/bin/env python3
"""Not Another Strobel or Sinker -- a small tkinter front end over bundled
command-line tools (ffmpeg, rclone)."""
import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from fractions import Fraction
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Not Another Strobel or Sinker"

# The real relationship between an NTSC film rate (24000/1001 fps) and PAL
# (25 fps): playing NTSC-timed content at PAL speed multiplies duration by
# 24000/25025 (speedup) -- the well known "PAL speedup" pitch/tempo shift.
PAL_NTSC_RATIO = Fraction(25025, 24000)  # PAL seconds per NTSC second


def resource_path(name):
    """Resolve a bundled tool by name: frozen app -> dev vendor/ -> system PATH."""
    names = [name + ".exe", name] if sys.platform.startswith("win") else [name]
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(sys._MEIPASS, "vendor"))
    dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
    for d in dirs:
        for n in names:
            candidate = os.path.join(d, n)
            if os.path.exists(candidate):
                return candidate
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    raise FileNotFoundError(f"could not locate bundled tool: {name}")


def app_config_dir():
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    path = os.path.join(base, "NotAnotherStrobelOrSinker")
    os.makedirs(path, exist_ok=True)
    return path


class ConsoleMixin:
    """Shared console-output + threaded-subprocess helpers for every tab."""

    def append_console(self, text):
        self.console.config(state="normal")
        self.console.insert(tk.END, text)
        self.console.see(tk.END)
        self.console.config(state="disabled")

    def run_cmd(self, cmd, btn, env=None, on_done=None):
        btn.config(state="disabled")
        self.console.config(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.config(state="disabled")
        self.append_console("$ " + " ".join(cmd) + "\n\n")

        def worker():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, env=env,
                )
                for line in proc.stdout:
                    self.after(0, self.append_console, line)
                proc.wait()
                self.after(0, self.append_console,
                           f"\nProcess finished with exit code {proc.returncode}\n")
            except Exception as exc:
                self.after(0, self.append_console, f"\nError: {exc}\n")
            finally:
                self.after(0, lambda: btn.config(state="normal"))
                if on_done:
                    self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()


class AtGamesTab(ttk.Frame, ConsoleMixin):
    """Reproduces the `atgame1` deep-fry filter (pixelation + crushed,
    pitched-up audio) as a direct call into the bundled, vanilla upstream
    FFmpeg -- inlined rather than shelling out to the original bash script so
    it also runs on Windows, which has no bash by default."""

    DEEP_FRY_ARGS = [
        "-vf", "scale=iw/8:ih/8,scale=iw*8:ih*8:flags=neighbor",
        "-af", "asetrate=44100*0.8408964153,aresample=44100,atempo=1.1892071150,"
               "compand=attacks=0:decays=0:points=-90/0|0/0|90/0,volume=500,"
               "acrusher=level_in=64:bits=2:mode=log",
        "-b:v", "30k", "-r", "12",
    ]

    # "G Major" is the classic YTP disaster effect: inverted video colors
    # plus audio run through a chain of pitch-shift passes (each one applied
    # the way people actually do it with a real pitch-shift tool -- change
    # pitch, keep tempo/duration the same -- rather than just resampling and
    # letting the speed drift). The numbered variants are community-defined
    # by which semitone amounts get chained; "Reverse" plays the clip
    # backwards through the same chain.
    SAMPLE_RATE = 44100
    G_MAJOR_SEMITONES = {
        "G Major 4": [0, 5],
        "G Major 7": [0, 3],
    }

    EFFECTS = ["AtGames", "G Major 4", "Reverse G Major 4", "G Major 7", "Reverse G Major 7"]

    def __init__(self, parent, console):
        ttk.Frame.__init__(self, parent, padding=10)
        self.console = console
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Input file:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.input_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self, text="Browse...", command=self.browse).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self, text="Effect:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.effect_var = tk.StringVar(value="AtGames")
        ttk.Combobox(
            self, textvariable=self.effect_var, state="readonly", values=self.EFFECTS,
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(
            self, wraplength=520, justify="left",
            text="AtGames pixelates the video and crushes the audio, same as "
                 "atgame1. The G Major effects invert the video's colors and "
                 "run the audio through a chain of pitch shifts (0 & 5 "
                 "semitones for G Major 4, 0 & 3 for G Major 7); the Reverse "
                 "variants play the clip backwards through the same chain. "
                 "Output is written next to the input.",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 10))

        self.run_btn = ttk.Button(self, text="Run", command=self.run)
        self.run_btn.grid(row=3, column=1, sticky="w", padx=5, pady=5)

    def browse(self):
        f = filedialog.askopenfilename(title="Select input video")
        if f:
            self.input_var.set(f)

    @classmethod
    def pitch_chain(cls, semitone_stages):
        """A comma-separated ffmpeg audio filter chain: each stage shifts
        pitch by the given number of semitones while keeping duration the
        same (asetrate changes pitch+speed together, atempo undoes the
        speed change), chained stage-by-stage the way a real pitch-shift
        plugin gets applied more than once."""
        parts = []
        for semitones in semitone_stages:
            factor = 2 ** (semitones / 12)
            parts.append(f"asetrate={cls.SAMPLE_RATE}*{factor:.6f}")
            parts.append(f"aresample={cls.SAMPLE_RATE}")
            parts.append(f"atempo={1 / factor:.6f}")
        return ",".join(parts)

    @classmethod
    def build_args(cls, effect):
        if effect == "AtGames":
            return cls.DEEP_FRY_ARGS
        reverse = effect.startswith("Reverse ")
        g_major_name = effect[len("Reverse "):] if reverse else effect
        audio = cls.pitch_chain(cls.G_MAJOR_SEMITONES[g_major_name])
        video = "negate"
        if reverse:
            video = "reverse," + video
            audio = "areverse," + audio
        return ["-vf", video, "-af", audio]

    def run(self):
        inp = self.input_var.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showwarning("Warning", "Please select a valid input file.")
            return
        try:
            ffmpeg = resource_path("ffmpeg")
        except FileNotFoundError as exc:
            messagebox.showerror("Error", str(exc))
            return

        effect = self.effect_var.get()
        suffix = "" if effect == "AtGames" else "." + effect.lower().replace(" ", "-")
        cmd = [ffmpeg, "-y", "-i", inp] + self.build_args(effect) + [inp + suffix + ".mp4"]
        self.run_cmd(cmd, self.run_btn)


class PitchTab(ttk.Frame, ConsoleMixin):
    """Re-times a video (and its subtitle streams) between NTSC and PAL
    "pitch" -- the ~4.1% speed/pitch shift a film-rate master gets when it's
    played back at the other standard's frame rate."""

    def __init__(self, parent, console):
        ttk.Frame.__init__(self, parent, padding=10)
        self.console = console
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Input file:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.input_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self, text="Browse...", command=self.browse_in).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self, text="Direction:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.direction_var = tk.StringVar(value="NTSC to PAL (speed up)")
        ttk.Combobox(
            self, textvariable=self.direction_var, state="readonly",
            values=["NTSC to PAL (speed up)", "PAL to NTSC (slow down)"],
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(self, text="Output file:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.output_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self, text="Browse...", command=self.browse_out).grid(row=2, column=2, padx=5, pady=5)

        ttk.Label(
            self, wraplength=520, justify="left",
            text="Ratio used: 25025/24000 (25 fps PAL vs 24000/1001 fps NTSC film "
                 "rate). Video and audio are re-timed together (genuine pitch "
                 "shift, not a tempo-corrected speed change) and every subtitle "
                 "stream's timestamps are stretched by the same ratio so they "
                 "stay in sync.",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 10))

        self.run_btn = ttk.Button(self, text="Convert", command=self.run)
        self.run_btn.grid(row=4, column=1, sticky="w", padx=5, pady=5)

    def browse_in(self):
        f = filedialog.askopenfilename(title="Select input video")
        if f:
            self.input_var.set(f)
            root, _ = os.path.splitext(f)
            self.output_var.set(root + "_pitched.mkv")

    def browse_out(self):
        f = filedialog.asksaveasfilename(title="Output file", defaultextension=".mkv")
        if f:
            self.output_var.set(f)

    @staticmethod
    def stretch_srt(text, ratio):
        import re
        from datetime import timedelta

        def parse(ts):
            h, m, s_ms = ts.split(":")
            s, ms = s_ms.split(",")
            return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))

        def fmt(td):
            total_ms = round(td.total_seconds() * 1000)
            h, rem = divmod(total_ms, 3600000)
            m, rem = divmod(rem, 60000)
            s, ms = divmod(rem, 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        pattern = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})")

        ratio_f = float(ratio)

        def repl(m):
            return (f"{fmt(parse(m.group(1)) * ratio_f)} --> "
                    f"{fmt(parse(m.group(2)) * ratio_f)}")

        return pattern.sub(repl, text)

    def run(self):
        inp = self.input_var.get().strip()
        outp = self.output_var.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showwarning("Warning", "Please select a valid input file.")
            return
        if not outp:
            messagebox.showwarning("Warning", "Please choose an output file.")
            return

        speed_up = self.direction_var.get().startswith("NTSC")
        ratio = (1 / PAL_NTSC_RATIO) if speed_up else PAL_NTSC_RATIO
        # `ratio` is applied to subtitle wall-clock timestamps and to a/v PTS.

        self.run_btn.config(state="disabled")
        threading.Thread(target=self._convert, args=(inp, outp, ratio), daemon=True).start()

    def _convert(self, inp, outp, ratio):
        try:
            ffmpeg = resource_path("ffmpeg")
            ffprobe = resource_path("ffprobe")
        except FileNotFoundError as exc:
            self.after(0, messagebox.showerror, "Error", str(exc))
            self.after(0, lambda: self.run_btn.config(state="normal"))
            return

        log = lambda s: self.after(0, self.append_console, s)
        self.after(0, self.append_console, f"Ratio applied: {ratio} ({float(ratio):.6f})\n\n")

        workdir = outp + ".pitch_tmp"
        os.makedirs(workdir, exist_ok=True)
        try:
            # 1. how many subtitle streams does the input have?
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "s",
                 "-show_entries", "stream=index:stream_tags=language",
                 "-of", "json", inp],
                capture_output=True, text=True,
            )
            log(probe.stdout + probe.stderr)
            streams = json.loads(probe.stdout or "{}").get("streams", [])

            video_audio = os.path.join(workdir, "video_audio.mkv")
            setpts_ratio = f"{ratio.numerator}/{ratio.denominator}"
            cmd = [
                ffmpeg, "-y", "-i", inp, "-map", "0:v", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                "-filter:v", f"setpts=({setpts_ratio})*(PTS-STARTPTS)",
                "-filter:a", f"asetrate=48000/({setpts_ratio}),aresample=48000",
                "-c:a", "aac", "-b:a", "256k", video_audio,
            ]
            log("$ " + " ".join(cmd) + "\n")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                log(line)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg a/v pass exited {proc.returncode}")

            sub_files, sub_langs = [], []
            for i, s in enumerate(streams):
                lang = s.get("tags", {}).get("language", "und")
                in_srt = os.path.join(workdir, f"sub_{i}.srt")
                cmd = [ffmpeg, "-y", "-i", inp, "-map", f"0:s:{i}", "-c:s", "srt", in_srt]
                log("$ " + " ".join(cmd) + "\n")
                r = subprocess.run(cmd, capture_output=True, text=True)
                log(r.stdout + r.stderr)
                if r.returncode != 0 or not os.path.exists(in_srt):
                    continue
                with open(in_srt, "r", encoding="utf-8-sig") as fh:
                    content = fh.read()
                stretched = self.stretch_srt(content, ratio)
                out_srt = os.path.join(workdir, f"sub_{i}_stretched.srt")
                with open(out_srt, "w", encoding="utf-8") as fh:
                    fh.write(stretched)
                sub_files.append(out_srt)
                sub_langs.append(lang)

            cmd = [ffmpeg, "-y", "-i", video_audio]
            for sf in sub_files:
                cmd += ["-i", sf]
            cmd += ["-map", "0:v", "-map", "0:a"]
            for i in range(len(sub_files)):
                cmd += ["-map", str(i + 1)]
            cmd += ["-c", "copy"]
            for i, lang in enumerate(sub_langs):
                cmd += [f"-metadata:s:s:{i}", f"language={lang}"]
            cmd += ["-f", "matroska", outp]
            log("$ " + " ".join(cmd) + "\n")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                log(line)
            proc.wait()
            log(f"\nProcess finished with exit code {proc.returncode}\n")
        except Exception as exc:
            log(f"\nError: {exc}\n")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            self.after(0, lambda: self.run_btn.config(state="normal"))


class DriveTab(ttk.Frame, ConsoleMixin):
    """A thin, deliberately minimal wrapper around a bundled rclone binary:
    load a config, reauthenticate with Google if the login expired, upload
    or download. No manual remote-editing or path typing. Nothing
    credential-bearing ships with the app: the config file lives only in the
    user's own app-support directory, and only gets there if the user
    explicitly loads an existing rclone.conf."""

    def __init__(self, parent, console):
        ttk.Frame.__init__(self, parent, padding=10)
        self.console = console
        self.columnconfigure(1, weight=1)
        self.config_path = os.path.join(app_config_dir(), "rclone.conf")

        ttk.Label(self, text="Config:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        ttk.Label(self, text=self.config_path, wraplength=420, justify="left").grid(
            row=0, column=1, columnspan=2, sticky="w", padx=5, pady=5)

        top_btns = ttk.Frame(self)
        top_btns.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(top_btns, text="Load config...", command=self.import_conf).pack(
            side=tk.LEFT, padx=(0, 5))
        ttk.Button(top_btns, text="Reauthenticate with Google", command=self.reauthenticate).pack(
            side=tk.LEFT)

        ttk.Label(self, text="Account:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.remote_var = tk.StringVar()
        self.remote_cb = ttk.Combobox(self, textvariable=self.remote_var, state="readonly")
        self.remote_cb.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(self, text="File or folder:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.local_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.local_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self, text="Browse...", command=self.browse_local).grid(row=3, column=2, padx=5, pady=5)

        btns = ttk.Frame(self)
        btns.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        self.upload_btn = ttk.Button(btns, text="Upload to Drive", command=self.upload)
        self.upload_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.download_btn = ttk.Button(btns, text="Download from Drive", command=self.download)
        self.download_btn.pack(side=tk.LEFT)

        self.after(200, self.refresh_remotes)

    def rclone_env(self):
        env = os.environ.copy()
        env["RCLONE_CONFIG"] = self.config_path
        return env

    def import_conf(self):
        f = filedialog.askopenfilename(title="Select an existing rclone.conf")
        if not f:
            return
        try:
            shutil.copyfile(f, self.config_path)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not import config: {exc}")
            return
        self.append_console(f"Loaded {f} -> {self.config_path}\n")
        self.refresh_remotes()

    def refresh_remotes(self):
        if not os.path.exists(self.config_path):
            self.remote_cb["values"] = []
            return
        try:
            rclone = resource_path("rclone")
        except FileNotFoundError:
            return
        r = subprocess.run([rclone, "listremotes", "--config", self.config_path],
                            capture_output=True, text=True)
        remotes = [line.strip() for line in r.stdout.splitlines() if line.strip()]
        self.remote_cb["values"] = remotes
        if remotes and not self.remote_var.get():
            self.remote_var.set(remotes[0])

    def reauthenticate(self):
        remote = self.remote_var.get().strip()
        if not remote:
            messagebox.showwarning("Warning", "Load a config and pick an account first.")
            return
        try:
            rclone = resource_path("rclone")
        except FileNotFoundError as exc:
            messagebox.showerror("Error", str(exc))
            return
        # Opens the account's sign-in page in the default browser and waits
        # for it to complete -- this is what actually needs "Google" opened,
        # not anything the app does directly.
        cmd = [rclone, "config", "reconnect", remote, "--config", self.config_path]
        self.run_cmd(cmd, self.upload_btn, env=self.rclone_env())

    def browse_local(self):
        f = filedialog.askopenfilename(title="Select a file")
        if not f:
            f = filedialog.askdirectory(title="Or select a folder")
        if f:
            self.local_var.set(f)

    def _copy(self, upload):
        remote = self.remote_var.get().strip()
        local = self.local_var.get().strip()
        if not remote:
            messagebox.showwarning("Warning", "Load a config and pick an account first.")
            return
        if not local:
            messagebox.showwarning("Warning", "Please select a file or folder.")
            return
        try:
            rclone = resource_path("rclone")
        except FileNotFoundError as exc:
            messagebox.showerror("Error", str(exc))
            return
        src, dst = (local, remote) if upload else (remote, local)
        cmd = [rclone, "copy", src, dst, "-P", "--config", self.config_path]
        btn = self.upload_btn if upload else self.download_btn
        self.run_cmd(cmd, btn, env=self.rclone_env())

    def upload(self):
        self._copy(upload=True)

    def download(self):
        self._copy(upload=False)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v1.0")
        self.minsize(900, 620)
        self.configure(padx=15, pady=15)

        try:
            base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base, "icon.png")
            if sys.platform != "darwin" and os.path.exists(icon_path):
                self._icon_img = tk.PhotoImage(file=icon_path)
                self.tk.call("wm", "iconphoto", self._w, self._icon_img)
        except Exception:
            pass

        style = ttk.Style(self)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        elif "clam" in style.theme_names():
            style.theme_use("clam")

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self, text="Console Output:").pack(anchor="w", pady=(10, 0))
        console_frame = ttk.Frame(self)
        console_frame.pack(fill=tk.BOTH, expand=True)
        self.console = tk.Text(console_frame, height=10, state="disabled",
                                bg="#1e1e1e", fg="#cccccc", font=("Menlo", 12))
        self.console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(console_frame, command=self.console.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.config(yscrollcommand=scrollbar.set)

        for label, cls in (("AtGames", AtGamesTab), ("Pitch", PitchTab), ("Drive", DriveTab)):
            frame = cls(notebook, self.console)
            notebook.add(frame, text=label)

        # macOS can restore a stale window frame from a previous run of this
        # same app path, which may be narrower than the content actually
        # needs and cause widgets to overlap -- force our own computed size.
        self.update_idletasks()
        self._min_width = max(self.winfo_reqwidth(), 900)
        self._min_height = max(self.winfo_reqheight(), 620)
        self.geometry(f"{self._min_width}x{self._min_height}")
        # A bundled macOS app can have its window frame restored (by the OS,
        # keyed to the app bundle) to whatever size it last closed at, which
        # can be narrower than the content needs and overlap widgets. That
        # restoration happens once the window is actually mapped, i.e. after
        # this constructor returns -- so reassert our own minimum size once
        # the event loop is running to win that race.
        self.after(150, self._enforce_min_size)

    def _enforce_min_size(self):
        if self.winfo_width() < self._min_width or self.winfo_height() < self._min_height:
            self.geometry(f"{self._min_width}x{self._min_height}")


if __name__ == "__main__":
    App().mainloop()
