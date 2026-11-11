#!/usr/bin/env python3
"""
make_tutorial.py — render the ascii-launchscreen tutorial video (<= 90 s).

Screencast-style: a simulated terminal showing the real plugin commands and
their real ASCII output, step by step:

  1. gen 08.jpg           -> still image becomes ASCII
  2. tweak (shades+invert) -> matches the reference (white bg, block shades)
  3. durations 3 s / 6 s
  4. hermes starts        -> launchscreen plays in the same terminal, then prompt

Uses only the plugin's own engine (real output) + Pillow + ffmpeg.
"""
from __future__ import annotations

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
FPS = 25
SIZE = (1280, 720)
BG = (13, 15, 22)
TERM_BG = (9, 10, 16)
PROMPT = (120, 200, 120)
CMD = (220, 220, 230)

SRC_08 = Path(r"C:\Users\gabri\Downloads\nous_frames_v2\nous_frames_v2\08.jpg")


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


def _ascii_image(spec: dict, idx: int, cell_w: int, cell_h: int, paper: bool = False) -> Image.Image:
    fr = spec["frames"][idx]
    rows = fr["text"].split("\n")
    w, h = spec["width"], spec["height"]
    bg = (255, 255, 255, 255) if paper else (0, 0, 0, 0)
    img = Image.new("RGBA", (w * cell_w, h * cell_h), bg)
    d = ImageDraw.Draw(img)
    font = _font(cell_h)
    color_mode = spec["color_mode"]
    fg = fr.get("fg")
    mono = (70, 70, 78) if paper else _hex_rgb(spec.get("mono_color_hex", "#3b82f6"))
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            c = mono
            if color_mode == "color" and fg and y < len(fg) and x < len(fg[y]) and fg[y][x]:
                c = tuple(fg[y][x])
            d.text((x * cell_w, y * cell_h), ch, font=font, fill=c)
    return img


def terminal(command: str, art: Image.Image | None, caption: str = "") -> Image.Image:
    """A terminal window: title bar, prompt+command, then the ASCII art."""
    img = Image.new("RGB", SIZE, TERM_BG)
    d = ImageDraw.Draw(img)
    # title bar
    d.rectangle([0, 0, SIZE[0], 34], fill=(30, 32, 44))
    d.ellipse([14, 12, 24, 22], fill=(255, 95, 86))
    d.ellipse([34, 12, 44, 22], fill=(255, 189, 46))
    d.ellipse([54, 12, 64, 22], fill=(39, 201, 63))
    d.text((80, 8), "hermes — ascii-launchscreen", font=_font(15), fill=(200, 200, 210))
    # prompt
    d.text((28, 48), "hermes", font=_font(24), fill=(168, 85, 247))
    d.text((28, 82), "$ " + command, font=_font(22), fill=CMD)
    # art, scaled to fit below the command
    if art is not None:
        avail_w = SIZE[0] - 56
        avail_h = SIZE[1] - 130 - (40 if caption else 0)
        ratio = min(avail_w / art.width, avail_h / art.height, 1.0)
        nw, nh = max(1, int(art.width * ratio)), max(1, int(art.height * ratio))
        art = art.resize((nw, nh), Image.LANCZOS)
        x = (SIZE[0] - nw) // 2
        y = 120 + (avail_h - nh) // 2
        img.paste(art, (x, y), art)
    if caption:
        d.text((28, SIZE[1] - 34), caption, font=_font(20), fill=(120, 200, 120))
    return img


def title_card(lines: list[tuple[str, int, tuple]]) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(img)
    y = SIZE[1] // 3
    for txt, sz, col in lines:
        font = _font(sz)
        bbox = d.textbbox((0, 0), txt, font=font)
        tw = bbox[2] - bbox[0]
        d.text(((SIZE[0] - tw) // 2 - bbox[0], y), txt, font=font, fill=col)
        y += sz + 30
    return img


def _hold(img: Image.Image, seconds: float) -> list[Image.Image]:
    return [img] * int(seconds * FPS)


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found", file=sys.stderr)
        return 1
    DEMO.mkdir(exist_ok=True)

    if not SRC_08.exists():
        print(f"source not found: {SRC_08}", file=sys.stderr)
        return 1

    # Real plugin output
    before = build_launchscreen(SRC_08, width=120, color_mode="mono")
    after = build_launchscreen(SRC_08, width=120, color_mode="mono",
                               ramp="shades", filters={"invert": 100})
    anim = build_launchscreen(DEMO / "bounce.gif", width=100, color_mode="color")

    before_art = _ascii_image(before, 0, 5, 10)
    after_art = _ascii_image(after, 0, 5, 10, paper=True)

    frames: list[Image.Image] = []

    # Title
    frames += _hold(title_card([
        ("ascii-launchscreen", 72, (230, 230, 230)),
        ("PNG -> ASCII launchscreen for Hermes", 34, (59, 130, 246)),
        ("tutorial — plugin workflow", 30, (140, 140, 160)),
    ]), 3)

    # Step 1
    frames += _hold(terminal(
        'ascii-launchscreen gen 08.jpg --width 120',
        before_art, "1 · insert the still image -> ASCII"),
        5)

    # Step 2
    frames += _hold(terminal(
        'ascii-launchscreen gen 08.jpg --width 120 --ramp shades --invert 100',
        after_art, "2 · tweak -> white background, block shades (matches the reference)"),
        6)

    # Step 3
    frames += _hold(title_card([
        ("3 · durations", 56, (230, 230, 230)),
        ("still image: 3 s", 34, (168, 85, 247)),
        ("animation: 6 s", 34, (168, 85, 247)),
    ]), 3)

    # Step 4 — the launchscreen animation in a terminal, then the prompt
    n_anim = len(anim["frames"])
    for k in range(int(6 * FPS)):
        art = _ascii_image(anim, k % n_anim, 5, 10)
        frames.append(terminal("hermes", art, "4 · launchscreen plays on start — same terminal"))
    # prompt appears
    prompt_img = Image.new("RGB", SIZE, TERM_BG)
    pd = ImageDraw.Draw(prompt_img)
    pd.text((28, 48), "hermes", font=_font(24), fill=(168, 85, 247))
    pd.text((28, 90), "You >", font=_font(26), fill=(220, 220, 230))
    frames += _hold(prompt_img, 2)

    # Outro
    frames += _hold(title_card([
        ("github.com/CappuccinoAlCioccolato/ascii-launcher", 30, (230, 230, 230)),
        ("Pillow only — no API, no network", 26, (140, 140, 160)),
    ]), 2)

    tmp = DEMO / "tutorial_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(frames):
        f.save(tmp / f"f_{i:05d}.png")
    out = DEMO / "tutorial.mp4"
    subprocess.run([
        ffmpeg, "-y", "-framerate", str(FPS), "-i", str(tmp / "f_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ], check=True, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out} ({len(frames)} frames @ {FPS}fps = {len(frames)/FPS:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
