from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssetKind = Literal["background", "prop", "icon", "cover"]


class AssetPlan(BaseModel):
    type: AssetKind
    name: str = Field(min_length=1, max_length=200)
    reuse_key: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=2000)
    size: str = "1024x1024"
    reason: str = ""
