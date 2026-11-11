#!/usr/bin/env python3
"""
make_demo.py — generate original demo sources, convert them, and render the
ASCII launchscreen to an MP4 (for the hackathon demo video, <= 90 s).

Produces:
    demo/demo.png        a still "HERMES" logo
    demo/bounce.gif      an animated bouncing-ball GIF
    demo/demo.mp4        the rendered video (title -> logo mono -> logo colour
                         -> bounce animation -> outro)

Requires Pillow + ffmpeg on PATH. Uses only the plugin's own engine.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from engine import build_launchscreen  # noqa: E402

DEMO = ROOT / "demo"
FPS = 20
BG = (11, 11, 18)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for c in [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/CascadiaCode.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = (h or "#3b82f6").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_logo(path: Path) -> None:
    w, h = 560, 200
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    font = _font(96)
    text = "HERMES"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (w - tw) // 2 - bbox[0], (h - th) // 2 - bbox[1]
    # colour sweep across the letters
    cols = [(59, 130, 246), (168, 85, 247), (236, 72, 153), (234, 88, 12), (16, 185, 129), (59, 130, 246)]
    for i, ch in enumerate(text):
        d.text((x + (i * tw / len(text)), y), ch, font=font, fill=cols[i % len(cols)])
    img.save(path)


def make_bounce(path: Path, n: int = 24, size=(300, 200)) -> None:
    frames = []
    for i in range(n):
        img = Image.new("RGB", size, BG)
        d = ImageDraw.Draw(img)
        t = i / n
        y = int(size[1] * 0.15 + abs(math.sin(t * 2 * math.pi)) * size[1] * 0.62)
        x = int(size[0] * 0.2 + t * size[0] * 0.6)
        r = 22
        d.ellipse([x - r, y - r, x + r, y + r], fill=(234, 88, 12))
        d.ellipse([x - r + 6, y - r + 6, x + r - 6, y + r - 6], outline=(255, 255, 255))
        frames.append(img)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=80, loop=0)


def render_frame(spec: dict, idx: int, cell_w: int = 9, cell_h: int = 18) -> Image.Image:
    fr = spec["frames"][idx]
    rows = fr["text"].split("\n")
    w, h = spec["width"], spec["height"]
    img = Image.new("RGB", (w * cell_w, h * cell_h), BG)
    d = ImageDraw.Draw(img)
    font = _font(cell_h - 2)
    color_mode = spec["color_mode"]
    fg = fr.get("fg")
    mono = _hex_rgb(spec.get("mono_color_hex", "#3b82f6"))
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            c = mono
            if color_mode == "color" and fg and y < len(fg) and x < len(fg[y]) and fg[y][x]:
                c = tuple(fg[y][x])
            d.text((x * cell_w, y * cell_h), ch, font=font, fill=c)
    return img


def title_card(lines: list[str], size=(1280, 720)) -> Image.Image:
    img = Image.new("RGB", size, BG)
    d = ImageDraw.Draw(img)
    y = size[1] // 3
    for i, (txt, sz, col) in enumerate(lines):
        font = _font(sz)
        bbox = d.textbbox((0, 0), txt, font=font)
        tw = bbox[2] - bbox[0]
        d.text(((size[0] - tw) // 2 - bbox[0], y), txt, font=font, fill=col)
        y += sz + 26
    return img


def _write_frames(outdir: Path, images: list[Image.Image]) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    for img in images:
        img.save(outdir / f"frame_{n:05d}.png")
        n += 1
    return n


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found on PATH — cannot encode the video.", file=sys.stderr)
        return 1

    DEMO.mkdir(exist_ok=True)
    logo = DEMO / "logo.png"
    bounce = DEMO / "bounce.gif"
    make_logo(logo)
    make_bounce(bounce)
    print(f"demo sources: {logo.name}, {bounce.name}")

    logo_mono = build_launchscreen(logo, width=60, color_mode="mono", mono_color="blue")
    logo_color = build_launchscreen(logo, width=60, color_mode="color")
    bounce_color = build_launchscreen(bounce, width=64, color_mode="color")

    def hold(img: Image.Image, seconds: float) -> list[Image.Image]:
        return [img] * int(seconds * FPS)

    seg_title = title_card([
        ("ASCII LAUNCHSCREEN", 64, (230, 230, 230)),
        ("a Hermes plugin — local PNG -> ASCII", 32, (59, 130, 246)),
        ("CLI intro  +  desktop overlay", 28, (140, 140, 160)),
    ])
    seg_logo_mono = render_frame(logo_mono, 0)
    seg_logo_color = render_frame(logo_color, 0)
    seg_outro = title_card([
        ("github.com/CappuccinoAlCioccolato/ascii-launcher", 30, (230, 230, 230)),
        ("Pillow only — no API, no network", 26, (140, 140, 160)),
    ])

    frames: list[Image.Image] = []
    frames += hold(seg_title, 3)
    frames += hold(seg_logo_mono, 4)
    frames += hold(seg_logo_color, 4)
    # bounce animation: loop the GIF frames for 8 seconds at ~12.5 fps -> 100 renders
    nb = len(bounce_color["frames"])
    for k in range(100):
        frames.append(render_frame(bounce_color, k % nb))
    frames += hold(seg_outro, 3)

    tmp = DEMO / "frames_tmp"
    n = _write_frames(tmp, frames)
    out = DEMO / "demo.mp4"
    cmd = [
        ffmpeg, "-y", "-framerate", str(FPS), "-i", str(tmp / "frame_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out}  ({n} frames @ {FPS}fps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
