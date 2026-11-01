from __future__ import annotations

from app.agents.remotion.service import _check_continuity, _shot_payload
from app.agents.storyboard.continuity import canonicalize_continuity
from app.render.models import EpisodeSpec, ShotLineSpec, ShotSpec
from app.render.timeline import build_timeline


def test_canonicalize_shares_scene_and_background():
    shots = [
        {"continuity_group": "g1", "bg": "desk", "scene": {}},
        {
            "continuity_group": "g1",
            "bg": "paper",
            "scene": {
                "setting": "草原",
                "entities": [{"id": "cow", "name": "牛", "appearance": "棕色"}],
            },
        },
        {"continuity_group": "g2", "bg": "paper", "scene": {}},
    ]
    scene = canonicalize_continuity(shots)
    assert scene["g1"]["setting"] == "草原"
    assert all(shot["bg"] == "desk" for shot in shots[:2])
    assert shots[0]["scene"] == shots[1]["scene"]
    assert shots[2]["scene"] == {}


def test_shot_payload_carries_continuity_context():
    spec = EpisodeSpec(
        title="测试",
        section_labels=["问题"],
        background="bg.png",
        floor="floor.png",
        shots=[
            ShotSpec(
                shot_id="s1",
                seq=1,
                section="问题",
                narration="牛在草原上",
                duration_ms=3000,
                lines=[
                    ShotLineSpec(
                        line_id="l1", seq=1, text="牛在草原上", duration_ms=3000
                    )
                ],
                continuity_group="g1",
                scene={
                    "setting": "草原",
                    "entities": [{"id": "cow", "name": "牛", "appearance": "棕色"}],
                },
            )
        ],
    )
    item = build_timeline(spec).shots[0]
    payload = _shot_payload(
        item, spec=spec, mapped={}, checksums={}, previous_tail=""
    )
    assert payload["continuity"]["group"] == "g1"
    assert payload["continuity"]["scene"]["entities"][0]["id"] == "cow"


def test_continuity_check_requires_entity_markers():
    payload = {
        "continuity": {
            "scene": {
                "entities": [
                    {"id": "cow", "name": "牛"},
                    {"id": "grass", "name": "草原"},
                ]
            }
        }
    }
    ok = '<svg><g data-entity="cow" /><rect data-entity="grass" /></svg>'
    assert _check_continuity(ok, payload) is None
    issue = _check_continuity('<svg><g data-entity="cow" /></svg>', payload)
    assert issue is not None
    assert "grass" in issue