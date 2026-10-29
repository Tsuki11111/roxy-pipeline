from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

CARD_TYPES = ("chat_bubble", "terminal", "browser", "icon", "pure_text")
POSITIONS = ("left", "right", "center", "none")
TRANSITIONS = ("cut", "fade", "slide_in")
MOTIONS = ("none", "idle_breathe", "card_pop", "subtle_pan")

MIN_DURATION_MS = 1500
MAX_DURATION_MS = 6000
CHARS_PER_SECOND = 5.5

DEFAULT_BACKGROUND_KEY = "paper"
BACKGROUNDS = {
    "paper": "character_packs/placeholder/background.png",
    "paper_dark": "character_packs/placeholder/background.png",
    "desk": "character_packs/placeholder/background.png",
}
DEFAULT_FLOOR = "character_packs/placeholder/floor.png"

DEFAULT_CARD_STYLES = {
    "chat_bubble": "ai_reply",
    "terminal": "info",
    "browser": "page",
    "icon": "",
    "pure_text": "conclusion",
}


def clamp_duration_ms(value: int) -> int:
    return max(MIN_DURATION_MS, min(MAX_DURATION_MS, int(value)))


def estimate_duration_ms(text: str) -> int:
    return clamp_duration_ms(round(len(text.strip()) / CHARS_PER_SECOND * 1000))


def load_character_assets(pack: str | None = None) -> list[dict]:
    candidates: list[tuple[str, Path]]
    if pack:
        candidates = [(pack, PROJECT_ROOT / "character_packs" / pack / "manifest.json")]
    else:
        candidates = [
            ("roxy", PROJECT_ROOT / "character_packs" / "roxy" / "manifest.json"),
            (
                "placeholder",
                PROJECT_ROOT / "character_packs" / "placeholder" / "manifest.json",
            ),
        ]
    for pack_name, manifest_path in candidates:
        if not manifest_path.exists():
            continue
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assets: list[dict] = []
        for asset in data.get("assets", []):
            if asset.get("scene_asset") or asset.get("pose") == "bust":
                continue
            file_name = asset.get("file")
            if not file_name:
                continue
            assets.append(
                {
                    "id": asset.get("id", Path(file_name).stem),
                    "path": f"character_packs/{pack_name}/{file_name}",
                    "expression": asset.get("expression", ""),
                    "pose": asset.get("pose", ""),
                }
            )
        if assets:
            return assets
    return [
        {
            "id": "placeholder_character",
            "path": "character_packs/placeholder/character.png",
            "expression": "neutral",
            "pose": "standing",
        }
    ]


def default_character_image(assets: list[dict]) -> str | None:
    return assets[0]["path"] if assets else None


def catalog_text(assets: list[dict]) -> str:
    return "\n".join(
        f"- {asset['path']} | expression={asset['expression']} | pose={asset['pose']}"
        for asset in assets
    )


def background_path(key: str) -> str:
    return BACKGROUNDS.get(key, BACKGROUNDS[DEFAULT_BACKGROUND_KEY])
