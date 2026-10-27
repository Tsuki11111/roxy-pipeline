from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from .models import CardSpec

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_card(card: CardSpec | None) -> str:
    if card is None or not card.text.strip():
        return ""
    name = f"cards/{card.type}.html"
    try:
        template = _env().get_template(name)
    except TemplateNotFound:
        template = _env().get_template("cards/pure_text.html")
    return template.render(text=card.text, style=card.style)
