#!/usr/bin/env python3
"""
cli_launcher.py — play the ASCII launchscreen, then launch Hermes.

This is the CLI launchscreen: a drop-in wrapper around `hermes`. It shows the
generated ASCII art (still image for 3 s, animation for 6 s, both tweakable)
and then execs hermes with whatever arguments you passed.

Usage:
    python cli_launcher.py                 # play + run `hermes`
    python cli_launcher.py -p project      # read the intro from a named profile
    python cli_launcher.py --no-intro      # skip straight to hermes
    python cli_launcher.py -c "..."        # extra args go to hermes
    python cli_launcher.py --play-only     # just preview, don't launch

It reads launchscreen.json from the data dir (generate it with
ascii_convert.py, or the plugin's /ascii or `hermes ascii-launchscreen gen`),
resolving the Hermes home the same way `hermes` does — pass `-p NAME` (or set
HERMES_HOME) to target a named profile. If no spec exists it launches hermes
directly without an intro.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import data_dir, fit_frame, frame_to_ansi, load_spec  # noqa: E402


def clear() -> None:
    # Pure-ANSI clear — no subprocess, works on any modern terminal.
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def play(spec: dict, cols: int | None = None, rows: int | None = None) -> None:
    frames = spec.get("frames") or []
    if not frames:
        return
    color_mode = spec.get("color_mode", "mono")
    mono_ansi = spec.get("mono_color_ansi", 34)
    duration_ms = int(spec.get("duration_ms", 6000))
    frame_delay_ms = int(spec.get("frame_delay_ms", 80))

    if cols is None or rows is None:
        try:
            size = shutil.get_terminal_size(fallback=(120, 40))
        except Exception:  # noqa: BLE001
            size = None
        cols = size.columns if size else 120
        rows = size.lines if size else 40

    # Fit each frame to the terminal *before* colourising, so colour-mode
    # frames are truncated cleanly on the grid instead of mid-ANSI-sequence.
    ansi_frames = [
        frame_to_ansi(fit_frame(f, cols, rows - 1), mono_ansi, color_mode)
        for f in frames
    ]

    def show(f: str) -> None:
        clear()
        print(f, flush=True)

    if len(frames) == 1:
        show(ansi_frames[0])
        time.sleep(duration_ms / 1000)
    else:
        end = time.monotonic() + duration_ms / 1000
        while time.monotonic() < end:
            for f in ansi_frames:
                show(f)
                time.sleep(frame_delay_ms / 1000)
                if time.monotonic() >= end:
                    break
    clear()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ASCII launchscreen + hermes launcher")
    ap.add_argument("--no-intro", action="store_true", help="Skip the intro")
    ap.add_argument("--play-only", action="store_true", help="Play the intro and exit")
    ap.add_argument("-p", "--profile", default="", help="Hermes profile to read the intro from and launch")
    ap.add_argument("--data-dir", default=None, help="Directory containing launchscreen.json")
    args, hermes_args = ap.parse_known_args(argv)

    if not args.no_intro:
        if args.data_dir:
            spec = load_spec(Path(args.data_dir).expanduser() / "launchscreen.json")
        else:
            spec = load_spec(data_dir(args.profile) / "launchscreen.json")
        if spec:
            try:
                play(spec)
            except KeyboardInterrupt:
                clear()

    if args.play_only:
        return 0

    if args.profile:
        hermes_args = ["-p", args.profile, *hermes_args]
    cmd = ["hermes", *hermes_args]
    if sys.platform == "win32":
        return os.spawnv(os.P_WAIT, shutil.which("hermes") or "hermes", cmd)
    os.execvp("hermes", cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
