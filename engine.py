"""
ascii-launchscreen engine — offline PNG/GIF -> ASCII converter.

A faithful, local port of the asciiart.eu "Image to ASCII" algorithm,
reverse-engineered from the page's minified source. Pure Pillow, no network,
no API. Used by the standalone CLI, the Hermes plugin tools, the CLI
launchscreen launcher, and (via launchscreen.json) the desktop overlay.

Reverse-engineered algorithm (from the live minified source):

  * The image is drawn at a character grid of
        width  = W            (characters)
        height = floor(0.55 * floor(W / aspect))     aspect = img_w / img_h
    The 0.55 factor is the terminal font-cell aspect correction: characters
    are roughly twice as tall as wide, so the pixel grid is squashed
    vertically by 0.55 to keep proportions.

  * A CSS filter chain is applied in this order:
        brightness(%) -> contrast(%) -> saturate(%) -> sepia(%) ->
        hue-rotate(deg) -> grayscale(%) -> invert(%)

  * Per pixel, luminance = 0.30*R + 0.59*G + 0.11*B  (alpha < 16 -> space).

  * Character index = floor(luminance * (len(ramp) - 1) / 255) where
        ramp = CHARSET[scale] + " " * space_density
    Darkest character first: black -> first char, white -> trailing spaces.

  * Optional stages (all off by default on asciiart.eu): Sobel edge detection,
    3x3 unsharp mask ("sharpen"), simple luminance threshold, and four
    error-diffusion dithers (Floyd-Steinberg, JJN, Stucki, Atkinson), each
    quantizing luminance to 15 levels.

The "color mode" is an extension on top of the grayscale port: instead of
discarding the filtered RGB, each cell keeps its foreground colour so the
result can be rendered in ANSI true-colour (CLI) or coloured spans (desktop).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# --------------------------------------------------------------------------- #
# Character sets (asciiart.eu exact strings, darkest -> lightest)
# --------------------------------------------------------------------------- #
CHARSETS: dict[str, str] = {
    "minimalist": "#+-.",
    "normal": "@%#*+=-:.",          # the page's default scale
    "normal2": "&$Xx+;:.",
    "alphabetic": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "alphanumeric": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz",
    "numerical": "0896452317",
    "extended": "@%#{}[]()<>^*+=~-:.",
    "math": "+-\u00d7\u00f7=\u2260\u2248\u221e\u221a\u03c0",
    "arrow": "\u2191\u2197\u2192\u2198\u2193\u2199\u2190\u2196",
    "grayscale": "@$BWM#*oahkbdpwmZO0QCJYXzcvnxrjft/|()1{}[]-_+~<>i!lI;:,\"^`'. ",
    "codepage437": "\u2588\u2593\u2592\u2591",  # block shades (what the sample frames use)
    "shades": "\u2593\u2592\u2591",  # 3 shades + space, no solid block (white-bg look)
}
DEFAULT_RAMP = "codepage437"

# Named monochrome colours -> (ANSI SGR code, hex for HTML).
MONO_COLORS: dict[str, tuple[int, str]] = {
    "black": (30, "#000000"),
    "red": (31, "#e5484d"),
    "green": (32, "#30a46c"),
    "yellow": (33, "#e5c07b"),
    "blue": (34, "#3b82f6"),
    "magenta": (35, "#d6409f"),
    "cyan": (36, "#00bcd4"),
    "white": (37, "#e6e6e6"),
    "gray": (90, "#8b8b8b"),
    "bright-white": (97, "#ffffff"),
}
DEFAULT_MONO_COLOR = "blue"

# CSS filter defaults (identity).
_FILTER_DEFAULTS = {
    "brightness": 100,
    "contrast": 100,
    "saturation": 100,
    "sepia": 0,
    "hue": 0,
    "grayscale": 0,
    "invert": 0,
}

# Error-diffusion matrices: (dx, dy, weight).
_DITHER = {
    "floyd-steinberg": [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)],
    "jnn": [
        (1, 0, 7 / 48), (2, 0, 5 / 48), (-2, 1, 3 / 48), (-1, 1, 5 / 48),
        (0, 1, 7 / 48), (1, 1, 5 / 48), (2, 1, 3 / 48), (-2, 2, 1 / 48),
        (-1, 2, 3 / 48), (0, 2, 5 / 48), (1, 2, 3 / 48), (2, 2, 1 / 48),
    ],
    "stucki": [
        (1, 0, 8 / 42), (2, 0, 4 / 42), (-2, 1, 2 / 42), (-1, 1, 4 / 42),
        (0, 1, 8 / 42), (1, 1, 4 / 42), (2, 1, 2 / 42), (-2, 2, 1 / 42),
        (-1, 2, 2 / 42), (0, 2, 4 / 42), (1, 2, 2 / 42), (2, 2, 1 / 42),
    ],
    "atkinson": [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8), (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)],
}


@dataclass
class Frame:
    """One ASCII frame: a grid of (char, rgb-or-None) cells."""
    rows: list[list[tuple[str, Optional[tuple[int, int, int]]]]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join("".join(ch for ch, _ in row) for row in self.rows)

    def to_json(self, color_mode: str) -> dict:
        out: dict = {"text": self.text}
        if color_mode == "color":
            out["fg"] = [[list(rgb) if rgb else None for _, rgb in row] for row in self.rows]
        return out


def _clamp(v: float) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(round(v))


def _apply_filter_chain(pixels: list[int], filters: dict) -> None:
    """Apply the CSS filter chain in place to a flat [r,g,b,...] list."""
    b = filters.get("brightness", 100) / 100.0
    c = filters.get("contrast", 100) / 100.0
    s = filters.get("saturation", 100) / 100.0
    sep = filters.get("sepia", 0) / 100.0
    hue = filters.get("hue", 0)
    g = filters.get("grayscale", 0) / 100.0
    inv = filters.get("invert", 0) / 100.0

    theta = math.radians(hue)
    cos, sin = math.cos(theta), math.sin(theta)
    # CSS hue-rotate matrix.
    hr = (
        (0.213 + cos * 0.787 - sin * 0.213, 0.715 - cos * 0.715 - sin * 0.715, 0.072 - cos * 0.072 + sin * 0.928),
        (0.213 - cos * 0.213 + sin * 0.143, 0.715 + cos * 0.285 + sin * 0.140, 0.072 - cos * 0.072 - sin * 0.283),
        (0.213 - cos * 0.213 - sin * 0.787, 0.715 - cos * 0.715 + sin * 0.715, 0.072 + cos * 0.928 + sin * 0.072),
    )

    for i in range(0, len(pixels), 3):
        r, g_, bl = pixels[i], pixels[i + 1], pixels[i + 2]
        # brightness
        r, g_, bl = r * b, g_ * b, bl * b
        # contrast
        r, g_, bl = (r - 128) * c + 128, (g_ - 128) * c + 128, (bl - 128) * c + 128
        # saturate (CSS luminance weights)
        luma = 0.2126 * r + 0.7152 * g_ + 0.0722 * bl
        r, g_, bl = luma + (r - luma) * s, luma + (g_ - luma) * s, luma + (bl - luma) * s
        # sepia
        if sep:
            sr = 0.393 * r + 0.769 * g_ + 0.189 * bl
            sg = 0.349 * r + 0.686 * g_ + 0.168 * bl
            sb = 0.272 * r + 0.534 * g_ + 0.131 * bl
            r, g_, bl = sr * sep + r * (1 - sep), sg * sep + g_ * (1 - sep), sb * sep + bl * (1 - sep)
        # hue-rotate
        if hue:
            nr = hr[0][0] * r + hr[0][1] * g_ + hr[0][2] * bl
            ng = hr[1][0] * r + hr[1][1] * g_ + hr[1][2] * bl
            nb = hr[2][0] * r + hr[2][1] * g_ + hr[2][2] * bl
            r, g_, bl = nr, ng, nb
        # grayscale
        if g:
            gray = 0.2126 * r + 0.7152 * g_ + 0.0722 * bl
            r, g_, bl = gray * g + r * (1 - g), gray * g + g_ * (1 - g), gray * g + bl * (1 - g)
        # invert
        if inv:
            r, g_, bl = r * (1 - inv) + (255 - r) * inv, g_ * (1 - inv) + (255 - g_) * inv, bl * (1 - inv) + (255 - bl) * inv
        pixels[i], pixels[i + 1], pixels[i + 2] = _clamp(r), _clamp(g_), _clamp(bl)


def _sobel_edge(pixels: list[int], w: int, h: int, intensity: float, invert_edges: bool) -> None:
    gx = (-1, 0, 1, -2, 0, 2, -1, 0, 1)
    gy = (-1, -2, -1, 0, 0, 0, 1, 2, 1)
    src = list(pixels)

    def lum(x: int, y: int) -> float:
        p = (y * w + x) * 3
        return 0.30 * src[p] + 0.59 * src[p + 1] + 0.11 * src[p + 2]

    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                v = 255
            else:
                sx = sy = 0.0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        k = (dy + 1) * 3 + (dx + 1)
                        l = lum(x + dx, y + dy)
                        sx += l * gx[k]
                        sy += l * gy[k]
                mag = math.sqrt(sx * sx + sy * sy) * intensity
                v = int(mag) & 0xFFFF
                v = 255 - v if invert_edges else v
            p = (y * w + x) * 3
            pixels[p] = pixels[p + 1] = pixels[p + 2] = _clamp(v)


def _sharpen(pixels: list[int], w: int, h: int, sharpness: float) -> None:
    src = list(pixels)
    kernel = (-1, -1, -1, -1, sharpness, -1, -1, -1, -1)
    for y in range(h):
        for x in range(w):
            acc = [0.0, 0.0, 0.0]
            for dy in range(3):
                for dx in range(3):
                    nx, ny = x + dx - 1, y + dy - 1
                    if 0 <= nx < w and 0 <= ny < h:
                        k = kernel[dy * 3 + dx]
                        p = (ny * w + nx) * 3
                        acc[0] += src[p] * k
                        acc[1] += src[p + 1] * k
                        acc[2] += src[p + 2] * k
            p = (y * w + x) * 3
            pixels[p], pixels[p + 1], pixels[p + 2] = _clamp(acc[0]), _clamp(acc[1]), _clamp(acc[2])


def _threshold(pixels: list[int], offset: int) -> None:
    for i in range(0, len(pixels), 3):
        l = 0.30 * pixels[i] + 0.59 * pixels[i + 1] + 0.11 * pixels[i + 2]
        v = 0 if l < offset else 255
        pixels[i] = pixels[i + 1] = pixels[i + 2] = v


def _luminance_grid(pixels: list[int], w: int, h: int) -> list[list[float]]:
    grid = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            p = (y * w + x) * 3
            grid[y][x] = 0.30 * pixels[p] + 0.59 * pixels[p + 1] + 0.11 * pixels[p + 2]
    return grid


def _dither(grid: list[list[float]], w: int, h: int, matrix) -> list[list[float]]:
    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            v = grid[y][x]
            q = round(v / 255 * 14) / 14 * 255
            out[y][x] = q
            err = v - q
            for dx, dy, weight in matrix:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    grid[ny][nx] += err * weight
    return out


def _target_height(img_w: int, img_h: int, width: int) -> int:
    aspect = img_w / img_h if img_h else 1.0
    return max(1, int(math.floor(0.55 * math.floor(width / aspect))))


def image_to_ascii(
    img,
    *,
    width: int = 252,
    ramp: str = DEFAULT_RAMP,
    color_mode: str = "mono",
    space_density: int = 1,
    filters: Optional[dict] = None,
    sharpen: bool = False,
    sharpness: float = 9.0,
    edge: bool = False,
    edge_intensity: float = 1.0,
    invert_edges: bool = True,
    threshold: Optional[int] = None,
    dither: Optional[str] = None,
) -> Frame:
    """Convert a single PIL image to an ASCII Frame."""
    from PIL import Image  # lazy import so module loads without Pillow

    ramp_name = ramp if ramp in CHARSETS else DEFAULT_RAMP
    chars = CHARSETS[ramp_name] + " " * max(0, space_density)

    src = img.convert("RGBA")
    sw, sh = src.size
    th = _target_height(sw, sh, width)
    small = src.resize((width, th), Image.BILINEAR).convert("RGBA")

    px = list(small.getdata())  # [(r,g,b,a), ...]
    flat = [0] * (width * th * 3)
    alpha = [0] * (width * th)
    for i, (r, g, b, a) in enumerate(px):
        flat[i * 3] = r
        flat[i * 3 + 1] = g
        flat[i * 3 + 2] = b
        alpha[i] = a

    flt = dict(_FILTER_DEFAULTS)
    if filters:
        flt.update(filters)
    _apply_filter_chain(flat, flt)

    if edge:
        _sobel_edge(flat, width, th, edge_intensity, invert_edges)
    if sharpen:
        _sharpen(flat, width, th, sharpness)
    if threshold is not None:
        _threshold(flat, threshold)

    grid = _luminance_grid(flat, width, th)
    if dither and dither in _DITHER:
        grid = _dither(grid, width, th, _DITHER[dither])

    use_color = color_mode == "color"
    rows: list[list[tuple[str, Optional[tuple[int, int, int]]]]] = []
    for y in range(th):
        row: list[tuple[str, Optional[tuple[int, int, int]]]] = []
        for x in range(width):
            if alpha[y * width + x] < 16:
                row.append((" ", None))
                continue
            lum = grid[y][x]
            idx = int(lum * (len(chars) - 1) / 255)
            idx = min(idx, len(chars) - 1)
            p = (y * width + x) * 3
            rgb = (flat[p], flat[p + 1], flat[p + 2]) if use_color else None
            row.append((chars[idx], rgb))
        rows.append(row)
    return Frame(rows=rows)


def load_input_frames(source: Path, *, max_frames: int = 60) -> tuple[list, list[int], int, int]:
    """Return (PIL images, per-frame durations ms, img_w, img_h) from a file or dir."""
    from PIL import Image

    if source.is_dir():
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
        files = sorted(p for p in source.iterdir() if p.suffix.lower() in exts)
        if not files:
            raise ValueError(f"No images found in {source}")
        files = files[:max_frames]
        imgs = [Image.open(p).convert("RGBA") for p in files]
        durations = [0] * len(imgs)
        return imgs, durations, imgs[0].size[0], imgs[0].size[1]

    img = Image.open(source)
    if getattr(img, "is_animated", False):
        frames, durations = [], []
        n_frames = getattr(img, "n_frames", 0) or 0
        for i in range(n_frames):
            if i >= max_frames:
                break
            img.seek(i)
            frames.append(img.convert("RGBA"))
            d = img.info.get("duration", 0)
            durations.append(int(d) if d else 0)
        return frames, durations, img.size[0], img.size[1]

    return [img.convert("RGBA")], [0], img.size[0], img.size[1]


def build_launchscreen(
    source: Path,
    *,
    width: int = 252,
    ramp: str = DEFAULT_RAMP,
    color_mode: str = "mono",
    mono_color: str = DEFAULT_MONO_COLOR,
    space_density: int = 1,
    filters: Optional[dict] = None,
    sharpen: bool = False,
    sharpness: float = 9.0,
    edge: bool = False,
    edge_intensity: float = 1.0,
    invert_edges: bool = True,
    threshold: Optional[int] = None,
    dither: Optional[str] = None,
    max_frames: int = 60,
    still_duration_ms: int = 3000,
    animation_duration_ms: int = 6000,
    frame_delay_ms: int = 80,
) -> dict:
    """Build the serializable launchscreen spec from a still image, GIF, or frame dir."""
    imgs, durations, iw, ih = load_input_frames(source, max_frames=max_frames)
    frames = [
        image_to_ascii(
            im,
            width=width,
            ramp=ramp,
            color_mode=color_mode,
            space_density=space_density,
            filters=filters,
            sharpen=sharpen,
            sharpness=sharpness,
            edge=edge,
            edge_intensity=edge_intensity,
            invert_edges=invert_edges,
            threshold=threshold,
            dither=dither,
        )
        for im in imgs
    ]
    kind = "animation" if len(frames) > 1 else "still"
    # Prefer the GIF's own per-frame durations when present.
    eff_delay = frame_delay_ms
    if kind == "animation" and durations and all(durations):
        eff_delay = max(1, int(sum(durations) / len(durations)))

    if mono_color not in MONO_COLORS:
        mono_color = DEFAULT_MONO_COLOR
    ansi, hexc = MONO_COLORS[mono_color]

    return {
        "kind": kind,
        "color_mode": color_mode,
        "mono_color": mono_color,
        "mono_color_ansi": ansi,
        "mono_color_hex": hexc,
        "ramp": ramp if ramp in CHARSETS else DEFAULT_RAMP,
        "width": width,
        "height": _target_height(iw, ih, width),
        "duration_ms": animation_duration_ms if kind == "animation" else still_duration_ms,
        "frame_delay_ms": eff_delay,
        "source": str(source),
        "frames": [f.to_json(color_mode) for f in frames],
    }


# --------------------------------------------------------------------------- #
# Rendering helpers (shared by CLI launcher and plugin)
# --------------------------------------------------------------------------- #
def fit_frame(frame: dict, max_w: int, max_h: int) -> dict:
    """Fit one serialized frame to a terminal box, preserving the colour grid.

    Truncates rows to ``max_w`` columns and ``max_h`` rows on the plain text
    (before colourising), and slices the parallel ``fg`` grid the same way, so
    a 252-column launchscreen can be shown without wrapping on a narrow
    terminal. Operates on the serialized form, so it works for both the CLI
    hook and the standalone launcher.
    """
    rows = (frame.get("text") or "").split("\n")[:max_h]
    rows = [r[:max_w] for r in rows]
    out: dict = {"text": "\n".join(rows)}
    fg = frame.get("fg")
    if fg:
        out["fg"] = [[cell for cell in row[:max_w]] for row in fg[:max_h]]
    return out


def frame_to_ansi(frame: dict, mono_ansi: int, color_mode: str) -> str:
    """Render one serialized frame as an ANSI string."""
    if color_mode == "color" and frame.get("fg"):
        out: list[str] = []
        rows = frame["text"].split("\n")
        fg = frame["fg"]
        for y, line in enumerate(rows):
            for x, ch in enumerate(line):
                c = fg[y][x] if y < len(fg) and x < len(fg[y]) else None
                if c:
                    out.append(f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m{ch}")
                else:
                    out.append(ch)
            out.append("\n")
        return "".join(out).rstrip("\n")
    return f"\x1b[{mono_ansi}m{frame['text']}\x1b[0m"


def spec_from_json(data: dict) -> dict:
    return data


def data_dir() -> Path:
    """Where launchscreen.json and generated frames live (profile-independent)."""
    env = os.environ.get("ASCII_LAUNCHSCREEN_DATA")
    if env:
        return Path(env).expanduser()
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "plugin-data" / "ascii-launchscreen"


def load_spec(path: Optional[Path] = None) -> Optional[dict]:
    p = path or data_dir() / "launchscreen.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_spec(spec: dict, path: Optional[Path] = None, *, write_frames: bool = False) -> Path:
    d = path or data_dir()
    d.mkdir(parents=True, exist_ok=True)
    out = d / "launchscreen.json"
    out.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    if write_frames:
        fdir = d / "frames"
        fdir.mkdir(exist_ok=True)
        for i, fr in enumerate(spec["frames"]):
            (fdir / f"{i}.txt").write_text(fr["text"], encoding="utf-8")
    return out
