#!/usr/bin/env python3
"""Create an episode from a render spec and wait for the render worker."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ROXY_API_URL") or "http://localhost:8000",
    )
    parser.add_argument("--spec", default="specs/demo_placeholder.json")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    spec = json.loads((ROOT / args.spec).read_text(encoding="utf-8"))
    spec_path = Path(args.spec)

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        series = client.post(
            "/api/v1/series",
            json={
                "name": f"M1.2 Demo {stamp}",
                "section_labels": spec["section_labels"],
                "character_pack_id": "placeholder",
                "watermark": spec.get("watermark", ""),
            },
        )
        series.raise_for_status()

        episode = client.post(
            "/api/v1/episodes",
            json={
                "series_id": series.json()["id"],
                "title": spec["title"],
                "topic": spec_path.name,
                "target_duration_s": 60,
            },
        )
        episode.raise_for_status()
        episode_id = episode.json()["id"]

        response = client.put(
            f"/api/v1/episodes/{episode_id}/render-spec", json=spec
        )
        response.raise_for_status()

        response = client.post(f"/api/v1/episodes/{episode_id}/actions/render")
        response.raise_for_status()
        print(f"queued episode={episode_id} node={response.json()['operation_id']}")

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            current = client.get(f"/api/v1/episodes/{episode_id}")
            current.raise_for_status()
            body = current.json()
            print(
                f"status={body['status']} health={body['health']} "
                f"node={body['current_node']}"
            )
            if body["status"] == "READY":
                print(f"output={body['output_path']}")
                return
            if body["status"] == "CANCELLED":
                raise SystemExit("episode cancelled")
            time.sleep(2)
        raise SystemExit("timed out waiting for render")


if __name__ == "__main__":
    main()
