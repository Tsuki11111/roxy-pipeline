from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Episode, EpisodeStatus

TRANSITIONS: dict[EpisodeStatus, frozenset[EpisodeStatus]] = {
    EpisodeStatus.DRAFT: frozenset(
        {EpisodeStatus.TOPIC_CONFIRMED, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.TOPIC_CONFIRMED: frozenset(
        {EpisodeStatus.SCRIPTING, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.SCRIPTING: frozenset(
        {EpisodeStatus.SCRIPT_REVIEW, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.SCRIPT_REVIEW: frozenset(
        {EpisodeStatus.STORYBOARDING, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.STORYBOARDING: frozenset(
        {EpisodeStatus.VOICING, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.VOICING: frozenset(
        {EpisodeStatus.ALIGNING, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.ALIGNING: frozenset(
        {EpisodeStatus.RENDERING, EpisodeStatus.CANCELLED}
    ),
    EpisodeStatus.RENDERING: frozenset(
        {
            EpisodeStatus.QC,
            EpisodeStatus.READY,
            EpisodeStatus.CANCELLED,
        }
    ),
    EpisodeStatus.QC: frozenset(
        {
            EpisodeStatus.READY,
            EpisodeStatus.SCRIPT_REVIEW,
            EpisodeStatus.VOICING,
            EpisodeStatus.RENDERING,
            EpisodeStatus.CANCELLED,
        }
    ),
    EpisodeStatus.READY: frozenset(
        {
            EpisodeStatus.PUBLISHED,
            EpisodeStatus.VOICING,
            EpisodeStatus.CANCELLED,
        }
    ),
    EpisodeStatus.PUBLISHED: frozenset(),
    EpisodeStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    {EpisodeStatus.PUBLISHED, EpisodeStatus.CANCELLED}
)


class InvalidTransition(Exception):
    def __init__(self, current: EpisodeStatus, target: EpisodeStatus):
        self.current = current
        self.target = target
        super().__init__(f"cannot transition {current.value} -> {target.value}")


async def transition_episode(
    session: AsyncSession,
    episode_id: str,
    target: EpisodeStatus,
) -> Episode:
    episode = await session.get(Episode, episode_id, with_for_update=True)
    if episode is None:
        raise LookupError(f"episode not found: {episode_id}")
    if target not in TRANSITIONS.get(episode.status, frozenset()):
        raise InvalidTransition(episode.status, target)
    episode.status = target
    if target in TERMINAL_STATUSES:
        episode.current_node = None
    return episode
