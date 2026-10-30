from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.render.models import EpisodeSpec
from app.render.timeline import build_timeline, split_subtitle


def make_spec(shots: list[dict], **kwargs) -> EpisodeSpec:
    return EpisodeSpec(
        title="test",
        fps=25,
        width=1920,
        height=1080,
        section_labels=["问题", "概念", "解决"],
        background="tmp/seedream_assets/bg_paper_light_01_1920x1080.png",
        floor="tmp/seedream_assets/bg_wood_floor_02_1920x1080.png",
        shots=shots,
        **kwargs,
    )


def shot(seq: int, section: str, narration: str, duration_ms: int = 4000) -> dict:
    return {
        "shot_id": f"s{seq:03d}",
        "seq": seq,
        "section": section,
        "narration": narration,
        "duration_ms": duration_ms,
    }


def test_timeline_frames_and_chunks() -> None:
    spec = make_spec(
        [
            shot(1, "问题", "第一步，先让 AI 自己看懂失败日志。"),
            shot(2, "问题", "结果它先连不上数据库。"),
            shot(3, "解决", "正确的做法，是先隔离环境。"),
        ]
    )
    timeline = build_timeline(spec)
    assert timeline.total_ms == 12000
    assert timeline.total_frames == 300
    assert [item.frame_count for item in timeline.shots] == [100, 100, 100]
    assert timeline.shots[0].start_ms == 0
    assert timeline.shots[-1].end_ms == 12000

    for item in timeline.shots:
        assert item.chunks, "every shot should have subtitle chunks"
        assert item.chunks[0].start_ms == item.start_ms
        assert item.chunks[-1].end_ms == item.end_ms
        for chunk in item.chunks:
            assert 1 <= len(chunk.text) <= 20
            assert chunk.start_ms < chunk.end_ms


def test_sentence_alignment_uses_single_chunk() -> None:
    spec = make_spec(
        [shot(1, "问题", "这是一整句字幕。", duration_ms=2000)],
        alignment_level="sentence",
    )
    timeline = build_timeline(spec)
    chunks = timeline.shots[0].chunks
    assert len(chunks) == 1
    assert chunks[0].text == "这是一整句字幕。"
    assert chunks[0].start_ms == 0
    assert chunks[0].end_ms == 2000


def test_char_timings_drive_subtitle_chunks() -> None:
    text = "你好世界。"
    spec = make_spec(
        [
            {
                **shot(1, "问题", text, duration_ms=2000),
                "char_timings": [
                    {"text": "你", "start_ms": 0, "end_ms": 400},
                    {"text": "好", "start_ms": 400, "end_ms": 800},
                    {"text": "世", "start_ms": 900, "end_ms": 1200},
                    {"text": "界", "start_ms": 1200, "end_ms": 1500},
                    {"text": "。", "start_ms": 1500, "end_ms": 1500},
                ],
            }
        ]
    )
    timeline = build_timeline(spec)
    chunk = timeline.shots[0].chunks[0]
    assert chunk.start_ms == 0
    assert chunk.end_ms == 1500


def test_subtitle_split_respects_limit() -> None:
    text = "第一步，先让AI自己看懂失败日志。然后它开始自己改测试，结果把数据库连错了。"
    chunks = split_subtitle(text, max_chars=16)
    assert chunks
    assert all(len(chunk) <= 16 for chunk in chunks)
    assert "".join(chunks) == text


def test_seq_must_be_contiguous() -> None:
    with pytest.raises(ValidationError):
        make_spec([shot(2, "问题", "x")])


def test_unknown_section_rejected() -> None:
    with pytest.raises(ValidationError):
        make_spec([shot(1, "不存在", "x")])
