from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.voice.align_service import start_align
from app.voice.service import start_voice
from app.models.core import Episode, EpisodeStatus
from app.qc.service import start_qc
from app.render.service import start_render


class ResumeConflict(Exception):
    pass


async def resume_episode(
    session: AsyncSession,
    episode_id: str,
) -> tuple[Episode, object]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status == EpisodeStatus.VOICING:
        return await start_voice(
            session, episode_id, retry=episode.health == "FAILED"
        )
    if episode.status == EpisodeStatus.ALIGNING:
        return await start_align(
            session, episode_id, retry=episode.health == "FAILED"
        )
    if episode.status == EpisodeStatus.QC:
        return await start_qc(
            session, episode_id, retry=episode.health == "FAILED"
        )
    if episode.status == EpisodeStatus.RENDERING:
        return await start_render(session, episode_id)
    raise ResumeConflict(
        f"episode status {episode.status.value} has no generic resume; "
        "use the stage-specific retry endpoint"
    )
