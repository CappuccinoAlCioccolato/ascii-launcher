# ascii-launchscreen

A Hermes plugin that turns a PNG, an animated GIF, or a folder of frame images
into an ASCII launchscreen shown when Hermes starts — as a **CLI intro** before
the prompt and as a **full-window overlay** in the desktop app.

It is a local, reverse-engineered port of the
[asciiart.eu](https://www.asciiart.eu/image-to-ascii) image-to-ascii algorithm:
same character sets, same filter chain, same terminal-aspect correction — but
running entirely offline on Pillow. No API, no network, no telemetry.

## Features

- **Still images and animations** — a PNG/JPG becomes a single frame; a GIF or
  a folder of images becomes an animation (one frame per GIF frame / per file).
- **Monochrome or original colours** — `color_mode: mono` renders in one
  colour; `color_mode: color` keeps each cell's original pixel colour (ANSI
  true-colour in the CLI, coloured spans on desktop).
- **Full asciiart.eu ramp set** — `codepage437` (block shades `█▓▒░`),
  `minimalist`, `normal`, `grayscale`, `math`, `arrow`, `extended`, and more.
- **Filter chain** — brightness / contrast / saturation / sepia / hue-rotate /
  grayscale / invert, plus optional sharpen, Sobel edge detection, threshold,
  and four error-diffusion dithers (Floyd-Steinberg, JJN, Stucki, Atkinson).
- **Tunable timing** — still image shows 3 s by default, animation plays 6 s,
  one frame every 80 ms. All three are live-tweakable in
  Settings → Plugins → ascii-launchscreen (desktop) or per-generation.

## Install

```
hermes plugins install <repo-url> --enable
```

or, developing locally, link the checkout into your plugins dir:

```
ln -s ~/src/ascii-launchscreen ~/.hermes/plugins/ascii-launchscreen
```

The desktop half is enabled by default (shows the launchscreen on app start,
falling back to an embedded HERMES banner until you generate custom art).

## Quick start

```
# Generate from a still image
hermes ascii-launchscreen gen logo.png --width 80 --color

# Generate from an animated GIF / a folder of frames
hermes ascii-launchscreen gen intro.gif --width 100
hermes ascii-launchscreen gen frames/ --color

# Preview it
hermes ascii-launchscreen play

# Play it, then start hermes (the CLI launchscreen)
hermes ascii-launchscreen launch
```

No Hermes required for the converter itself:

```
python ascii_convert.py logo.png --color --width 100
python cli_launcher.py --play-only
```

## How the algorithm works (reverse-engineered)

From the minified source of asciiart.eu's image-to-ascii:

1. The image is drawn at `width` characters wide and
   `floor(0.55 * floor(width / aspect))` tall — the `0.55` is the terminal
   font-cell aspect correction (characters are ~2× taller than wide).
2. A CSS filter chain is applied in order: `brightness` → `contrast` →
   `saturate` → `sepia` → `hue-rotate` → `grayscale` → `invert`.
3. Per pixel, `luminance = 0.30*R + 0.59*G + 0.11*B` (alpha < 16 → space).
4. Character index = `floor(luminance * (len(ramp)-1) / 255)`, where
   `ramp = CHARSET[scale] + " " * space_density` (darkest character first).

Colour mode is an extension: the filtered RGB is retained per cell instead of
discarded.

## Tool & commands

- **Tool** `ascii_generate` — convert an image/GIF/folder into the launchscreen.
- **Tool** `ascii_play` — render a frame to ANSI text for preview.
- **CLI** `hermes ascii-launchscreen gen|play|launch|status`.
- **Slash** `/ascii` (and `/ascii show N`).

## Settings (Settings → Plugins → ascii-launchscreen)

`source`, `width`, `ramp`, `color_mode`, `mono_color`, `still_duration_s`,
`animation_duration_s`, `frame_delay_ms`, `space_density`, `brightness`,
`contrast`, `invert`.

## Disclosure

- **No network access.** The plugin never makes HTTP calls; all conversion is
  local Pillow.
- **File reads.** It reads only the source image/GIF/folder you point it at,
  and writes only to its own plugin data directory
  (`<HERMES_HOME>/plugin-data/ascii-launchscreen/`).
- **Shell commands.** The CLI intro runs `cls`/`clear` to clear the terminal
  before drawing frames. Nothing else.
- **No background processes, no credentials, no telemetry.**

## Dependencies

`Pillow>=9,<14` (declared in `pyproject.toml` and `plugin.yaml`).

## License

MIT — see `LICENSE`.
