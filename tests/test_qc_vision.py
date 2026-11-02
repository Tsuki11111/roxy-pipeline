"""质检视觉问题的严重级别测试。"""

from __future__ import annotations

from app.qc.vision import check_frames


class FakeVisionLLM:
    async def chat_vision_json(self, *args, **kwargs):
        return {
            "issues": [
                {
                    "frame_index": 1,
                    "type": "text_occlusion",
                    "severity": "warning",
                    "detail": "角色盖住了卡片文字",
                }
            ]
        }


async def test_card_occlusion_is_blocking_error(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake")
    issues = await check_frames(
        [
            {
                "path": str(frame),
                "seq": 1,
                "section": "问题",
                "time_ms": 0,
                "narration": "测试",
                "card_type": "pure_text",
                "has_character": True,
            }
        ],
        FakeVisionLLM(),
        blocking=False,
    )
    assert len(issues) == 1
    assert issues[0]["level"] == "ERROR"
    assert issues[0]["check_item"] == "vision.text_occlusion"