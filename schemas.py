"""Tool schemas for the ascii-launchscreen plugin."""

ASCII_GENERATE = {
    "name": "ascii_generate",
    "description": (
        "Convert an image, animated GIF, or folder of frame images into ASCII art "
        "and install it as the Hermes launchscreen (CLI intro and desktop overlay). "
        "Pure local conversion — no network. Use this when the user wants to create, "
        "regenerate, or change their launchscreen. Returns the launchscreen spec "
        "summary (kind, frame count, dimensions, colour mode, timing)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Path to a PNG/JPG image, an animated GIF, or a directory of frame images.",
            },
            "width": {
                "type": "integer",
                "description": "Characters per row (default 80).",
            },
            "ramp": {
                "type": "string",
                "enum": [
                    "codepage437", "minimalist", "normal", "normal2",
                    "alphabetic", "alphanumeric", "numerical", "extended",
                    "math", "arrow", "grayscale",
                ],
                "description": "Character set (default codepage437 = block shades █▓▒░).",
            },
            "color_mode": {
                "type": "string",
                "enum": ["mono", "color"],
                "description": "Monochrome or original image colours (default mono).",
            },
            "mono_color": {
                "type": "string",
                "description": "Monochrome colour name (blue, red, green, yellow, magenta, cyan, white, black, gray) or hex.",
            },
            "still_duration_ms": {
                "type": "integer",
                "description": "How long a still image shows, in ms (default 5000 = 5 s).",
            },
            "animation_duration_ms": {
                "type": "integer",
                "description": "How long an animation plays, in ms (default 8000 = 8 s).",
            },
            "frame_delay_ms": {
                "type": "integer",
                "description": "Milliseconds each animation frame is shown (default 80).",
            },
            "brightness": {"type": "integer", "description": "Brightness % (default 100)."},
            "contrast": {"type": "integer", "description": "Contrast % (default 100)."},
            "invert": {"type": "integer", "description": "Invert % (default 0)."},
        },
        "required": ["source"],
    },
}

ASCII_PLAY = {
    "name": "ascii_play",
    "description": (
        "Render the current launchscreen to text (ANSI) so it can be shown or "
        "inspected. Useful to preview the generated art without launching."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "frame": {
                "type": "integer",
                "description": "Frame index to render (default 0).",
            },
        },
    },
}
