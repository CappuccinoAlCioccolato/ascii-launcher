---
name: ascii-launchscreen
description: "Use when generating, configuring, or previewing the Hermes ASCII launchscreen (PNG/GIF -> ASCII, CLI intro and desktop overlay)."
---

# ASCII Launchscreen

Turn a PNG, an animated GIF, or a folder of frame images into an ASCII
launchscreen that plays when Hermes starts — as a CLI intro before the prompt,
and as a full-window overlay in the desktop app. Conversion is entirely local
(no API, no network): a reverse-engineered port of the asciiart.eu
image-to-ascii algorithm running on Pillow.

## How it works

The converter maps each image pixel to a character:

- Image is scaled to `width` characters per row; height follows the terminal
  cell aspect (0.55x correction), so proportions stay correct.
- Luminance = 0.30*R + 0.59*G + 0.11*B, mapped linearly onto a character ramp
  (darkest char first). Default ramp is `codepage437` (block shades `█▓▒░ `).
- `color_mode: mono` renders in one colour; `color_mode: color` keeps each
  cell's original colour (ANSI true-colour in the CLI, coloured spans on
  desktop).

## Generating a launchscreen

Via the tool (in-session):

```
ascii_generate source="logo.png" width=80 color_mode="color" ramp="codepage437"
```

Via the CLI (outside a session):

```
hermes ascii-launchscreen gen logo.png --width 80 --color
python ascii_convert.py intro.gif --width 100 --color   # no Hermes needed
```

Input may be a still image, an animated GIF (one frame per GIF frame), or a
directory of images (sorted by filename, one frame each).

## Playing and launching

- `hermes ascii-launchscreen play` — preview the current launchscreen.
- `hermes ascii-launchscreen launch` — play it, then start `hermes`.
- `python cli_launcher.py` — standalone launcher (play + `hermes`, or
  `--play-only` to preview).
- In-session: `/ascii` describes it; `/ascii show 0` prints frame 0.

## Timing

- Still image: shows for `still_duration_s` (default 3 s).
- Animation: plays for `animation_duration_s` (default 6 s), one frame every
  `frame_delay_ms` (default 80 ms).
- All three are configurable in Settings → Plugins → ascii-launchscreen
  (desktop), in `plugin.yaml` `config_schema`, or per-generation via tool
  args / CLI flags.

## Desktop

The desktop app loads the overlay automatically (the desktop half is enabled
by default). It shows the generated art for the configured duration, then
dismisses; click it to skip. If no launchscreen has been generated yet it
falls back to an embedded HERMES banner.

## Files

- `engine.py` — the converter (pure Pillow, reusable standalone).
- `ascii_convert.py` — standalone CLI converter.
- `cli_launcher.py` — standalone CLI intro + launcher.
- `desktop/plugin.js` — desktop overlay.
- `dashboard/plugin_api.py` — serves the spec to the desktop with live settings.

## Character ramps

`codepage437` (`█▓▒░`), `minimalist` (`#+-.`), `normal` (`@%#*+=-:.`),
`normal2`, `alphabetic`, `alphanumeric`, `numerical`, `extended`, `math`,
`arrow`, `grayscale` (the classic 70-char ramp). Pass any as `--ramp`.
