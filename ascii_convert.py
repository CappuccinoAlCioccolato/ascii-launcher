#!/usr/bin/env python3
"""
ascii_convert.py — standalone, offline PNG/GIF -> ASCII converter.

Local port of the asciiart.eu "Image to ASCII" algorithm. No API, no network.
Runs anywhere Pillow is installed; you do not need Hermes for this file.

Usage:
    python ascii_convert.py INPUT [options]

INPUT is a still image (png/jpg/...), an animated GIF, or a directory of
images (one file per frame, sorted by name).

Examples:
    python ascii_convert.py logo.png                       # mono, 80 cols
    python ascii_convert.py logo.png --color               # original colours
    python ascii_convert.py intro.gif --width 100          # animation
    python ascii_convert.py frames/ --ramp normal --color  # frames dir
    python ascii_convert.py logo.png --mono-color cyan --brightness 120

Outputs launchscreen.json (plus frames/*.txt with --write-frames) into the
data dir (--data-dir DIR), ready for the CLI/desktop launchscreen to play.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (  # noqa: E402
    CHARSETS,
    MONO_COLORS,
    build_launchscreen,
    data_dir,
    save_spec,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PNG/GIF -> ASCII (asciiart.eu port)")
    ap.add_argument("input", help="Image file, animated GIF, or directory of frames")
    ap.add_argument("--width", type=int, default=252, help="Characters per row (default 252)")
    ap.add_argument("--ramp", default="codepage437", choices=list(CHARSETS),
                    help="Character set (default codepage437 = block shades)")
    ap.add_argument("--color", action="store_true", help="Keep original image colours")
    ap.add_argument("--mono-color", default="blue", help="Monochrome colour name or hex")
    ap.add_argument("--space-density", type=int, default=1)
    ap.add_argument("--brightness", type=int, default=100)
    ap.add_argument("--contrast", type=int, default=100)
    ap.add_argument("--saturation", type=int, default=100)
    ap.add_argument("--sepia", type=int, default=0)
    ap.add_argument("--hue", type=int, default=0)
    ap.add_argument("--grayscale", type=int, default=0)
    ap.add_argument("--invert", type=int, default=0)
    ap.add_argument("--sharpen", action="store_true")
    ap.add_argument("--sharpness", type=float, default=9.0)
    ap.add_argument("--edge", action="store_true")
    ap.add_argument("--edge-intensity", type=float, default=1.0)
    ap.add_argument("--threshold", type=int, default=None)
    ap.add_argument("--dither", default=None, choices=["floyd-steinberg", "jnn", "stucki", "atkinson"])
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--still-duration", type=int, default=3000, help="ms for a still image (default 3000)")
    ap.add_argument("--animation-duration", type=int, default=6000, help="ms for an animation (default 6000)")
    ap.add_argument("--frame-delay", type=int, default=80, help="ms per frame (default 80)")
    ap.add_argument("--data-dir", default=None, help="Output dir (default: hermes plugin-data)")
    ap.add_argument("--write-frames", action="store_true", help="Also write frames/*.txt")
    ap.add_argument("--print", action="store_true", dest="print_", help="Print the ASCII to stdout")
    args = ap.parse_args(argv)

    src = Path(args.input).expanduser()
    if not src.exists():
        print(f"error: input not found: {src}", file=sys.stderr)
        return 2

    mono = args.mono_color
    if mono not in MONO_COLORS and not mono.startswith("#"):
        print(f"warning: unknown mono color '{mono}', using blue", file=sys.stderr)
        mono = "blue"

    try:
        spec = build_launchscreen(
            src,
            width=args.width,
            ramp=args.ramp,
            color_mode="color" if args.color else "mono",
            mono_color=mono,
            space_density=args.space_density,
            filters={
                "brightness": args.brightness,
                "contrast": args.contrast,
                "saturation": args.saturation,
                "sepia": args.sepia,
                "hue": args.hue,
                "grayscale": args.grayscale,
                "invert": args.invert,
            },
            sharpen=args.sharpen,
            sharpness=args.sharpness,
            edge=args.edge,
            edge_intensity=args.edge_intensity,
            threshold=args.threshold,
            dither=args.dither,
            max_frames=args.max_frames,
            still_duration_ms=args.still_duration,
            animation_duration_ms=args.animation_duration,
            frame_delay_ms=args.frame_delay,
        )
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1

    out_dir = Path(args.data_dir).expanduser() if args.data_dir else data_dir()
    out = save_spec(spec, out_dir, write_frames=args.write_frames)
    n = len(spec["frames"])
    print(f"{'animation' if n > 1 else 'still'}  {n} frame(s)  {spec['width']}x{spec['height']}")
    print(f"color_mode={spec['color_mode']}  ramp={spec['ramp']}  mono={spec['mono_color']}")
    print(f"duration={spec['duration_ms']}ms  frame_delay={spec['frame_delay_ms']}ms")
    print(f"wrote {out}")

    if args.print_:
        from engine import frame_to_ansi
        print(frame_to_ansi(spec["frames"][0], spec["mono_color_ansi"], spec["color_mode"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
