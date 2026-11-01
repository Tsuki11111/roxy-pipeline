from __future__ import annotations


def canonicalize_continuity(shots: list[dict]) -> dict[str, dict]:
    """Make every continuity group share the first non-empty scene and bg."""
    group_scene: dict[str, dict] = {}
    group_bg: dict[str, str] = {}
    for shot in shots:
        group_id = str(shot.get("continuity_group") or "")
        if not group_id:
            continue
        scene = shot.get("scene")
        if (
            group_id not in group_scene
            and isinstance(scene, dict)
            and scene.get("setting")
            and scene.get("entities")
        ):
            group_scene[group_id] = scene
        group_bg.setdefault(group_id, str(shot.get("bg") or "paper"))
    for shot in shots:
        group_id = str(shot.get("continuity_group") or "")
        if not group_id:
            continue
        shot["bg"] = group_bg[group_id]
        if group_id in group_scene:
            shot["scene"] = group_scene[group_id]
    return group_scene


def scene_entity_ids(scene: dict | None) -> list[str]:
    if not isinstance(scene, dict):
        return []
    entities = scene.get("entities")
    if not isinstance(entities, list):
        return []
    ids: list[str] = []
    for entity in entities:
        if isinstance(entity, dict) and entity.get("id"):
            ids.append(str(entity["id"]))
    return list(dict.fromkeys(ids))