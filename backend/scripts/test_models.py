"""Fetch live free models from OpenRouter and test the top ones."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config.settings import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings().openrouter
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    # 1. Fetch live model list
    resp = httpx.get(
        f"{settings.base_url.rstrip('/')}/models",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    models = resp.json()["data"]

    free_models = [
        m["id"]
        for m in models
        if m.get("id", "").endswith(":free")
    ]
    print(f"Found {len(free_models)} free models. Testing first 8:")
    for m in free_models[:8]:
        print("  -", m)

    # 2. Test the first few free models
    for model in free_models[:8]:
        try:
            r = httpx.post(
                f"{settings.base_url.rstrip('/')}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 10,
                },
                headers=headers,
                timeout=30,
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                print(f"OK    {model} -> {content[:50]!r}")
            else:
                print(f"FAIL  {model} -> {r.status_code} {r.text[:100]}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {model} -> {exc}")


if __name__ == "__main__":
    main()