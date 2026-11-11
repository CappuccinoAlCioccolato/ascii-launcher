"""Tool handlers for the ascii-launchscreen plugin."""
from __future__ import annotations

import json
from pathlib import Path

from . import engine


def _plugin_data_dir() -> Path:
    """Prefer the sanctioned plugin data dir; fall back to the engine's path."""
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        return Path(plugin_data_dir("ascii-launchscreen"))
    except Exception:  # noqa: BLE001
        return engine.data_dir()


def ascii_generate(args: dict, **kwargs) -> str:
    try:
        source = (args.get("source") or "").strip()
        if not source:
            return json.dumps({"error": "No source provided"})
        src = Path(source).expanduser()
        if not src.exists():
            return json.dumps({"error": f"Source not found: {src}"})

        def cfg(key, default):
            v = args.get(key)
            return default if v is None else v

        spec = engine.build_launchscreen(
            src,
            width=int(cfg("width", 80)),
            ramp=cfg("ramp", "codepage437"),
            color_mode=cfg("color_mode", "mono"),
            mono_color=cfg("mono_color", "blue"),
            filters={
                "brightness": int(cfg("brightness", 100)),
                "contrast": int(cfg("contrast", 100)),
                "invert": int(cfg("invert", 0)),
            },
            still_duration_ms=int(cfg("still_duration_ms", 5000)),
            animation_duration_ms=int(cfg("animation_duration_ms", 8000)),
            frame_delay_ms=int(cfg("frame_delay_ms", 80)),
        )
        out = engine.save_spec(spec, _plugin_data_dir(), write_frames=True)
        return json.dumps({
            "ok": True,
            "kind": spec["kind"],
            "frames": len(spec["frames"]),
            "width": spec["width"],
            "height": spec["height"],
            "color_mode": spec["color_mode"],
            "mono_color": spec["mono_color"],
            "duration_ms": spec["duration_ms"],
            "frame_delay_ms": spec["frame_delay_ms"],
            "spec_path": str(out),
        })
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)})


def ascii_play(args: dict, **kwargs) -> str:
    try:
        spec = engine.load_spec(_plugin_data_dir() / "launchscreen.json")
        if not spec:
            return json.dumps({"error": "No launchscreen generated yet — run ascii_generate first."})
        frames = spec.get("frames") or []
        idx = int(args.get("frame") or 0)
        if idx >= len(frames):
            idx = 0
        ansi = engine.frame_to_ansi(frames[idx], spec.get("mono_color_ansi", 34), spec.get("color_mode", "mono"))
        return json.dumps({
            "ok": True,
            "frame": idx,
            "total_frames": len(frames),
            "art": ansi,
        })
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)})
