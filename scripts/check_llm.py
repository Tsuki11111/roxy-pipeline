#!/usr/bin/env python3
"""Check DeepSeek and Volcengine Ark credentials without printing secrets.

Usage:
    python scripts/check_llm.py            # only check .env is filled
    python scripts/check_llm.py --live     # call the APIs (small cost)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(f"missing {path}; copy .env.example to .env first")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, mask(secret))
    return text


def request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout: int = 30,
) -> tuple[int | None, dict]:
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload
    except Exception as exc:  # noqa: BLE001 - report network errors plainly
        return None, {"error": str(exc)}


def check_presence(env: dict[str, str], require_ark: bool = False) -> list[str]:
    required = ["DEEPSEEK_API_KEY"]
    if require_ark:
        required += ["ARK_API_KEY", "ARK_MODEL_STRONG"]
    optional = [
        "ARK_API_KEY",
        "ARK_MODEL_STRONG",
        "ARK_MODEL_VISION",
    ]
    problems = [key for key in required if not env.get(key)]
    print("== configured ==")
    for key in required + [k for k in optional if k not in required]:
        print(f"{key:20s} {mask(env.get(key, ''))}")
    warnings = [key for key in optional if not env.get(key)]
    if warnings:
        print(f"warn: optional values not set: {', '.join(warnings)}")
    return problems


def check_deepseek(env: dict[str, str], secrets: list[str]) -> bool:
    key = env.get("DEEPSEEK_API_KEY", "")
    base = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = env.get("DEEPSEEK_MODEL", "deepseek-flash")
    if not key:
        print("[deepseek] SKIP: DEEPSEEK_API_KEY is empty")
        return False

    status, payload = request_json(
        f"{base}/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    body = redact(json.dumps(payload, ensure_ascii=False), secrets)
    if status == 200:
        models = [
            item.get("id", "")
            for item in payload.get("data", [])
            if isinstance(item, dict)
        ]
        print(f"[deepseek] PASS: /models returned {len(models)} model(s)")
        print(f"[deepseek] models: {', '.join(models) or '(empty)'}")
        if model in models:
            print(f"[deepseek] target model present: {model}")
            return True
        print(f"[deepseek] WARN: target model '{model}' not in /models output")
        return False
    print(f"[deepseek] FAIL: HTTP {status}: {body[:400]}")
    return False


def check_ark(
    env: dict[str, str],
    secrets: list[str],
    model_override: str | None = None,
    required: bool = False,
) -> bool | None:
    key = env.get("ARK_API_KEY", "")
    base = env.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    model = model_override or env.get("ARK_MODEL_STRONG", "")
    if not key:
        print("[ark] SKIP: ARK_API_KEY is empty")
        return None
    if not model:
        status, payload = request_json(
            f"{base}/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        if status == 200:
            models = [
                item.get("id", "")
                for item in payload.get("data", [])
                if isinstance(item, dict)
            ]
            print(f"[ark] /models returned {len(models)} model(s): {', '.join(models)}")
        else:
            body = redact(json.dumps(payload, ensure_ascii=False), secrets)
            print(f"[ark] SKIP: ARK_MODEL_STRONG empty; /models HTTP {status}: {body[:300]}")
        return None

    status, payload = request_json(
        f"{base}/chat/completions",
        method="POST",
        headers={"Authorization": f"Bearer {key}"},
        body={
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        },
    )
    body = redact(json.dumps(payload, ensure_ascii=False), secrets)
    if status == 200:
        print(f"[ark] PASS: strong model '{model}' responded")
        vision = env.get("ARK_MODEL_VISION", "")
        if vision:
            print(f"[ark] vision model configured: {vision} (not exercised by this ping)")
        return True
    print(f"[ark] {'FAIL' if required else 'WARN'}: HTTP {status}: {body[:400]}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="call the APIs")
    parser.add_argument("--env", default=str(ROOT / ".env"), help="path to .env")
    parser.add_argument("--ark-model", help="override ARK_MODEL_STRONG for this check")
    parser.add_argument("--skip-deepseek", action="store_true", help="skip DeepSeek check")
    parser.add_argument("--require-ark", action="store_true", help="treat Ark as required")
    args = parser.parse_args()

    env = load_env(Path(args.env))
    secrets = [env.get("DEEPSEEK_API_KEY", ""), env.get("ARK_API_KEY", "")]
    missing = check_presence(env, args.require_ark)
    if missing:
        print(f"missing values: {', '.join(missing)}")
        return 1
    if not args.live:
        print("presence check only; rerun with --live to call the APIs")
        return 0

    ok_deepseek = True if args.skip_deepseek else check_deepseek(env, secrets)
    ok_ark = check_ark(env, secrets, args.ark_model, required=args.require_ark)
    ok = ok_deepseek and (ok_ark is not False or not args.require_ark)
    suffix = " (ark optional)" if ok_ark is None else ""
    print("RESULT:", "PASS" if ok else "FAIL", suffix)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
