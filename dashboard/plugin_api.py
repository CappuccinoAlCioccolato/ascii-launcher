"""Backend routes for the ascii-launchscreen desktop half.

Serves GET /api/plugins/ascii-launchscreen/launchscreen — the generated
launchscreen spec with live overrides applied from the plugin settings form
(plugins.entries.ascii-launchscreen.settings). Runs inside the gateway process.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

# name -> (ANSI SGR code, hex). Mirrors engine.MONO_COLORS.
_MONO = {
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


def _spec_path() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
        return Path(plugin_data_dir("ascii-launchscreen")) / "launchscreen.json"
    except Exception:  # noqa: BLE001
        home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
        return Path(home) / "plugin-data" / "ascii-launchscreen" / "launchscreen.json"


def _settings() -> dict:
    try:
        from hermes_cli.config import load_config_readonly
        cfg = load_config_readonly() or {}
    except Exception:  # noqa: BLE001
        return {}
    entries = (cfg.get("plugins") or {}).get("entries") or {}
    return (entries.get("ascii-launchscreen") or {}).get("settings") or {}


@router.get("/launchscreen")
async def launchscreen():
    p = _spec_path()
    if not p.exists():
        return {"available": False}
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"available": False}

    s = _settings()

    # Live overrides from Settings -> Plugins -> ascii-launchscreen.
    if spec.get("kind") == "still" and s.get("still_duration_s") is not None:
        spec["duration_ms"] = int(float(s["still_duration_s"]) * 1000)
    if spec.get("kind") == "animation" and s.get("animation_duration_s") is not None:
        spec["duration_ms"] = int(float(s["animation_duration_s"]) * 1000)
    if s.get("frame_delay_ms") is not None:
        spec["frame_delay_ms"] = int(s["frame_delay_ms"])
    if s.get("color_mode") in ("mono", "color"):
        spec["color_mode"] = s["color_mode"]
    mc = s.get("mono_color")
    if mc in _MONO:
        spec["mono_color"] = mc
        spec["mono_color_ansi"], spec["mono_color_hex"] = _MONO[mc]

    spec["available"] = True
    return spec
