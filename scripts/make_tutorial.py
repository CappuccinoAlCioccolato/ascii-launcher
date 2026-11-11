#!/usr/bin/env python3
"""
make_tutorial.py — ascii-launchscreen tutorial video (<= 90 s).

Shows the real workflow at full reference resolution (252 columns, zoomed to
view), no placeholder animation:

  1. png -> ascii          (the still image becomes ASCII art)
  2. tweak tool            (--invert, --ramp shades change the result live)
  3. durations             (still 3 s, animation 6 s)
  4. hermes starts         (launchscreen plays automatically, same terminal)
  5. how to reproduce      (exact commands)

Uses the plugin's own engine + Pillow + ffmpeg. Real output only.
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
CMD = (220, 220, 230)

SRC_08 = Path(r"C:\Users\gabri\Downloads\nous_frames_v2\nous_frames_v2\08.jpg")
FRAMES_DIR = Path(r"C:\Users\gabri\Downloads\nous_frames_v2\nous_frames_v2")
WIDTH = 252


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


def render_ascii(spec: dict, idx: int, cell_w: int = 8, cell_h: int = 16,
                 paper: bool = False) -> Image.Image:
    """Render one frame at a large crisp cell size (the caller scales it down)."""
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


def _fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    ratio = min(box_w / img.width, box_h / img.height, 1.0)
    nw, nh = max(1, int(img.width * ratio)), max(1, int(img.height * ratio))
    return img.resize((nw, nh), Image.LANCZOS)


def _caption(img: Image.Image, text: str) -> None:
    ImageDraw.Draw(img).text((28, SIZE[1] - 34), text, font=_font(20), fill=(120, 200, 120))


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


def terminal(command: str, art: Image.Image | None, caption: str = "") -> Image.Image:
    img = Image.new("RGB", SIZE, TERM_BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, SIZE[0], 34], fill=(30, 32, 44))
    d.ellipse([14, 12, 24, 22], fill=(255, 95, 86))
    d.ellipse([34, 12, 44, 22], fill=(255, 189, 46))
    d.ellipse([54, 12, 64, 22], fill=(39, 201, 63))
    d.text((80, 8), "hermes — ascii-launchscreen", font=_font(15), fill=(200, 200, 210))
    d.text((28, 48), "hermes", font=_font(24), fill=(168, 85, 247))
    d.text((28, 82), "$ " + command, font=_font(22), fill=CMD)
    if art is not None:
        fitted = _fit(art, SIZE[0] - 56, SIZE[1] - 130 - (40 if caption else 0))
        x = (SIZE[0] - fitted.width) // 2
        y = 120 + ((SIZE[1] - 130 - (40 if caption else 0)) - fitted.height) // 2
        img.paste(fitted, (x, y), fitted)
    if caption:
        _caption(img, caption)
    return img


def split(photo_path: Path, ascii_art: Image.Image, caption: str) -> Image.Image:
    """Left: the source photo. Right: the ASCII art. png -> ascii."""
    img = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(img)
    half = SIZE[0] // 2
    photo = Image.open(photo_path).convert("RGB")
    p = _fit(photo, half - 90, SIZE[1] - 150)
    img.paste(p, ((half - 90 - p.width) // 2, (SIZE[1] - 150 - p.height) // 2 + 20))
    d.text((half // 2, 30), "png", font=_font(30), fill=(230, 230, 230), anchor="mm")
    a = _fit(ascii_art, half - 90, SIZE[1] - 150)
    img.paste(a, (half + (half - 90 - a.width) // 2, (SIZE[1] - 150 - a.height) // 2 + 20), a)
    d.text((half + half // 2, 30), "ascii", font=_font(30), fill=(230, 230, 230), anchor="mm")
    d.text((half, SIZE[1] // 2), "->", font=_font(40), fill=(59, 130, 246), anchor="mm")
    _caption(img, caption)
    return img


def commands_card() -> Image.Image:
    cmds = [
        "hermes ascii-launchscreen gen 08.jpg --width 252",
        "hermes ascii-launchscreen gen 08.jpg --width 252 --invert 100",
        "hermes ascii-launchscreen gen 08.jpg --width 252 --ramp shades --invert 100",
        "hermes ascii-launchscreen gen frames/ --color --animation-duration 6000",
        "hermes                 # launchscreen plays automatically",
    ]
    img = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(img)
    d.text((80, 60), "how to reproduce", font=_font(40), fill=(230, 230, 230))
    y = 150
    for c in cmds:
        d.text((80, y), "$ " + c, font=_font(24), fill=(120, 200, 120))
        y += 56
    return img


def _hold(img: Image.Image, seconds: float) -> list[Image.Image]:
    return [img] * int(seconds * FPS)


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found", file=sys.stderr)
        return 1
    DEMO.mkdir(exist_ok=True)
    if not SRC_08.exists() or not FRAMES_DIR.exists():
        print(f"source missing: {SRC_08}", file=sys.stderr)
        return 1

    print("building specs...")
    default_spec = build_launchscreen(SRC_08, width=WIDTH, color_mode="mono")
    invert_spec = build_launchscreen(SRC_08, width=WIDTH, color_mode="mono",
                                     filters={"invert": 100})
    shades_spec = build_launchscreen(SRC_08, width=WIDTH, color_mode="mono",
                                     ramp="shades", filters={"invert": 100})
    anim_spec = build_launchscreen(FRAMES_DIR, width=WIDTH, color_mode="color")

    print("rendering ascii images (252 cols)...")
    default_art = render_ascii(default_spec, 0)
    invert_art = render_ascii(invert_spec, 0, paper=True)
    shades_art = render_ascii(shades_spec, 0, paper=True)
    anim_frames = [render_ascii(anim_spec, i) for i in range(len(anim_spec["frames"]))]

    frames: list[Image.Image] = []

    # 1. title
    frames += _hold(title_card([
        ("ascii-launchscreen", 72, (230, 230, 230)),
        ("PNG -> ASCII launchscreen for Hermes", 34, (59, 130, 246)),
    ]), 3)

    # 2. png -> ascii
    frames += _hold(split(SRC_08, shades_art, "1 · png -> ascii · 252 columns, zoomed to view"), 6)

    # 3. tweak tool — three states, the result changes live
    frames += _hold(terminal('ascii-launchscreen gen 08.jpg --width 252', default_art,
                             '2 · tweak: default (dark background, solid blocks)'), 4)
    frames += _hold(terminal('ascii-launchscreen gen 08.jpg --width 252 --invert 100', invert_art,
                             '2 · tweak: + --invert 100 (white background)'), 4)
    frames += _hold(terminal('ascii-launchscreen gen 08.jpg --width 252 --ramp shades --invert 100', shades_art,
                             '2 · tweak: + --ramp shades (soft shades, no solid blocks)'), 4)

    # 4. durations
    frames += _hold(title_card([
        ("3 · durations", 56, (230, 230, 230)),
        ("still image: 3 s", 34, (168, 85, 247)),
        ("animation: 6 s", 34, (168, 85, 247)),
    ]), 3)

    # 5. launchscreen plays on start (animation, 6 s), then prompt
    n = len(anim_frames)
    for k in range(int(6 * FPS)):
        frames.append(terminal("hermes", anim_frames[k % n],
                               '4 · launchscreen plays on start — same terminal'))
    prompt_img = Image.new("RGB", SIZE, TERM_BG)
    pd = ImageDraw.Draw(prompt_img)
    pd.text((28, 48), "hermes", font=_font(24), fill=(168, 85, 247))
    pd.text((28, 90), "You >", font=_font(26), fill=(220, 220, 230))
    frames += _hold(prompt_img, 2)

    # 6. how to reproduce
    frames += _hold(commands_card(), 6)

    # 7. outro
    frames += _hold(title_card([
        ("github.com/CappuccinoAlCioccolato/ascii-launcher", 30, (230, 230, 230)),
        ("Pillow only — no API, no network", 26, (140, 140, 160)),
    ]), 2)

    print(f"encoding {len(frames)} frames...")
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
