"""ascii-launchscreen plugin — registration.

Registers:
  * ascii_generate / ascii_play tools
  * `hermes ascii-launchscreen <gen|play|launch|status>` CLI command
  * `/ascii` in-session slash command
  * a bundled skill (skill_view("ascii-launchscreen:ascii-launchscreen"))
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from . import engine, schemas, tools

logger = logging.getLogger(__name__)


def _play(spec: dict) -> None:
    frames = spec.get("frames") or []
    if not frames:
        return
    color_mode = spec.get("color_mode", "mono")
    mono_ansi = spec.get("mono_color_ansi", 34)
    duration_ms = int(spec.get("duration_ms", 8000))
    frame_delay_ms = int(spec.get("frame_delay_ms", 80))
    ansi = [engine.frame_to_ansi(f, mono_ansi, color_mode) for f in frames]

    def clear() -> None:
        # Pure-ANSI clear — no subprocess, works on any modern terminal.
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()

    try:
        if len(frames) == 1:
            clear()
            print(ansi[0], flush=True)
            time.sleep(duration_ms / 1000)
        else:
            end = time.monotonic() + duration_ms / 1000
            while time.monotonic() < end:
                for f in ansi:
                    clear()
                    print(f, flush=True)
                    time.sleep(frame_delay_ms / 1000)
                    if time.monotonic() >= end:
                        break
    except KeyboardInterrupt:
        pass
    finally:
        clear()


def _cli_run(args: argparse.Namespace) -> int:
    sub = getattr(args, "sub", None)
    if sub == "gen":
        src = Path(args.source).expanduser()
        if not src.exists():
            print(f"error: input not found: {src}")
            return 2
        spec = engine.build_launchscreen(
            src,
            width=args.width,
            ramp=args.ramp,
            color_mode="color" if args.color else "mono",
            mono_color=args.mono_color,
            still_duration_ms=args.still_duration,
            animation_duration_ms=args.animation_duration,
            frame_delay_ms=args.frame_delay,
        )
        out = engine.save_spec(spec, tools._plugin_data_dir(), write_frames=True)
        n = len(spec["frames"])
        print(f"{'animation' if n > 1 else 'still'}  {n} frame(s)  {spec['width']}x{spec['height']}  {spec['color_mode']}")
        print(f"duration={spec['duration_ms']}ms  frame_delay={spec['frame_delay_ms']}ms")
        print(f"wrote {out}")
        return 0
    if sub == "play":
        spec = engine.load_spec(tools._plugin_data_dir() / "launchscreen.json")
        if not spec:
            print("No launchscreen generated yet. Run: hermes ascii-launchscreen gen <image>")
            return 1
        _play(spec)
        return 0
    if sub == "launch":
        spec = engine.load_spec(tools._plugin_data_dir() / "launchscreen.json")
        if spec:
            _play(spec)
        cmd = ["hermes", *getattr(args, "hermes_args", [])]
        if sys.platform == "win32":
            return os.spawnv(os.P_WAIT, shutil.which("hermes") or "hermes", cmd)
        os.execvp("hermes", cmd)
        return 0
    if sub == "status":
        spec = engine.load_spec(tools._plugin_data_dir() / "launchscreen.json")
        if not spec:
            print("No launchscreen generated yet.")
            return 0
        print(f"kind={spec['kind']}  frames={len(spec['frames'])}  {spec['width']}x{spec['height']}")
        print(f"color_mode={spec['color_mode']}  ramp={spec['ramp']}  mono={spec['mono_color']}")
        print(f"duration={spec['duration_ms']}ms  frame_delay={spec['frame_delay_ms']}ms")
        print(f"source={spec.get('source', '?')}")
        return 0
    print("Usage: hermes ascii-launchscreen <gen|play|launch|status>")
    return 1


def _cli_setup(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="sub")
    g = subs.add_parser("gen", help="Generate a launchscreen from an image/GIF/folder")
    g.add_argument("source")
    g.add_argument("--width", type=int, default=80)
    g.add_argument("--ramp", default="codepage437")
    g.add_argument("--color", action="store_true")
    g.add_argument("--mono-color", default="blue")
    g.add_argument("--still-duration", type=int, default=5000)
    g.add_argument("--animation-duration", type=int, default=8000)
    g.add_argument("--frame-delay", type=int, default=80)
    subs.add_parser("play", help="Play the current launchscreen in the terminal")
    l = subs.add_parser("launch", help="Play the launchscreen, then start hermes")
    l.add_argument("hermes_args", nargs=argparse.REMAINDER)
    subs.add_parser("status", help="Show the current launchscreen")
    subparser.set_defaults(func=_cli_run)


def _handle_ascii(raw_args: str) -> str:
    raw = (raw_args or "").strip()
    if raw.startswith("gen ") or raw == "gen":
        return "Generate via: hermes ascii-launchscreen gen <image> (or the ascii_generate tool)."
    spec = engine.load_spec(tools._plugin_data_dir() / "launchscreen.json")
    if not spec:
        return "No launchscreen yet — run the ascii_generate tool or `hermes ascii-launchscreen gen <image>`."
    frames = spec.get("frames") or []
    if raw.startswith("show") or raw.isdigit():
        idx = int(raw) if raw.isdigit() else int(raw.split()[-1] or 0)
        idx = min(idx, len(frames) - 1)
        return engine.frame_to_ansi(frames[idx], spec.get("mono_color_ansi", 34), spec.get("color_mode", "mono"))
    return (
        f"Launchscreen: {spec['kind']}, {len(frames)} frame(s), {spec['width']}x{spec['height']}, "
        f"{spec['color_mode']}. `/ascii show 0` to preview a frame."
    )


def register(ctx):
    ctx.register_tool(name="ascii_generate", toolset="ascii-launchscreen",
                      schema=schemas.ASCII_GENERATE, handler=tools.ascii_generate)
    ctx.register_tool(name="ascii_play", toolset="ascii-launchscreen",
                      schema=schemas.ASCII_PLAY, handler=tools.ascii_play)

    ctx.register_cli_command(
        name="ascii-launchscreen",
        help="Generate, play, and launch with an ASCII launchscreen",
        setup_fn=_cli_setup,
        handler_fn=_cli_run,
    )

    ctx.register_command("ascii", _handle_ascii, description="Show/describe the ASCII launchscreen")

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)
