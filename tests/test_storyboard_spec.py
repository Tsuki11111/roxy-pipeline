from __future__ import annotations

from app.models.core import Episode, ScriptLine, Series, Shot
from app.render.timeline import build_timeline
from app.storyboard.spec_builder import build_episode_spec, shot_cache_key

LABELS = ["问题", "解决", "结尾"]
CHARACTER = "character_packs/placeholder/character.png"


def make_rows():
    episode = Episode(id="ep-spec", series_id="ser-spec", title="测试一期")
    series = Series(id="ser-spec", name="测试系列", section_labels=LABELS)
    lines: list[ScriptLine] = []
    shots: list[Shot] = []
    seq = 1
    for label in LABELS:
        for index in range(2):
            line = ScriptLine(
                id=f"line-{seq}",
                episode_id=episode.id,
                seq=seq,
                speaker="narrator",
                section=label,
                text="这是一句测试台词内容",
                char_count=10,
            )
            lines.append(line)
            shots.append(
                Shot(
                    id=f"shot-{seq}",
                    episode_id=episode.id,
                    script_line_id=line.id,
                    seq=seq,
                    duration_ms=2000,
                    card_type="pure_text" if index == 1 else "chat_bubble",
                    card_payload={
                        "style": "conclusion" if index == 1 else "ai_reply",
                        "text": line.text,
                        "motion": "idle_breathe",
                    },
                    character_image=CHARACTER if index == 0 else None,
                    character_position="left" if index == 0 else "none",
                    bg="paper",
                    transition="cut",
                    template_version="v1",
                )
            )
            seq += 1
    return episode, series, lines, shots


def test_build_episode_spec_from_shots():
    episode, series, lines, shots = make_rows()
    spec = build_episode_spec(episode, series, lines, shots)
    assert len(spec.shots) == 6
    assert spec.shots[0].card.text == lines[0].text
    assert spec.shots[0].narration == lines[0].text
    assert spec.shots[0].character is not None
    assert spec.shots[1].character is None
    timeline = build_timeline(spec)
    assert timeline.total_ms == 12000
    assert timeline.shots[0].section_index == 0


def test_shot_cache_key_is_stable_and_sensitive():
    kwargs = dict(
        text="测试台词",
        card_type="chat_bubble",
        card_payload={"style": "ai_reply"},
        character_image=CHARACTER,
        template_version="v1",
    )
    first = shot_cache_key(**kwargs)
    assert first == shot_cache_key(**kwargs)
    assert first != shot_cache_key(**{**kwargs, "template_version": "v2"})
