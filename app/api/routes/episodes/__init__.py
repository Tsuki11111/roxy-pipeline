from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.episodes import (
    crud,
    lifecycle,
    media,
    render,
    script,
    storyboard,
)

router = APIRouter()
router.include_router(crud.router)
router.include_router(script.router)
router.include_router(storyboard.router)
router.include_router(media.router)
router.include_router(render.router)
router.include_router(lifecycle.router)
