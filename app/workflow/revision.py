from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.voice.service import start_voice
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    Review,
    ScriptLine,
)
from app.workflow.state_machine import transition_episode


class RevisionRequestError(Exception):
    pass


class RevisionConflict(RevisionRequestError):
    pass


async def revise_line(
    session: AsyncSession,
    episode_id: str,
    line_id: str,
    text: str,
) -> tuple[Episode, ScriptLine, NodeRun]:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if episode.status in {EpisodeStatus.PUBLISHED, EpisodeStatus.CANCELLED}:
        raise RevisionConflict(
            f"episode status {episode.status.value} cannot be revised"
        )
    if episode.status not in {EpisodeStatus.READY, EpisodeStatus.QC}:
        raise RevisionConflict(
            f"episode status {episode.status.value} must be edited via script API"
        )

    line = await session.get(ScriptLine, line_id)
    if line is None or line.episode_id != episode_id:
        raise LookupError(f"script line not found: {line_id}")
    text = text.strip()
    if not text:
        raise RevisionRequestError("text must not be blank")
    if len(text) > 200:
        raise RevisionRequestError("text is too long")

    line.text = text
    line.char_count = len(text)
    line.version += 1

    await session.execute(delete(Review).where(Review.episode_id == episode_id))
    episode.qc_meta = None
    episode.health = "OK"
    episode.current_node = None

    await transition_episode(session, episode_id, EpisodeStatus.VOICING)
    await session.flush()
    episode, node = await start_voice(session, episode_id)
    return episode, line, node
