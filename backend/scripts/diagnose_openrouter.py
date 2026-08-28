"""Test OpenRouter chat + embeddings with the configured key/models."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config.settings import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings().openrouter
    print("CHAT MODEL:", settings.model)
    print("EMBED MODEL:", settings.embedding_model)
    print("API KEY set:", bool(settings.api_key))

    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    # 1. Chat model test
    try:
        resp = httpx.post(
            f"{settings.base_url.rstrip('/')}/chat/completions",
            json={
                "model": settings.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 10,
            },
            headers=headers,
            timeout=30,
        )
        print("CHAT status:", resp.status_code)
        if resp.status_code != 200:
            print("CHAT error body:", resp.text[:300])
        else:
            print(
                "CHAT ok:",
                resp.json()["choices"][0]["message"]["content"][:80],
            )
    except Exception as exc:  # noqa: BLE001
        print("CHAT request failed:", exc)

    # 2. Embedding model test
    try:
        resp = httpx.post(
            f"{settings.base_url}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": "test",
                "dimensions": settings.embedding_dimensions,
            },
            headers=headers,
            timeout=30,
        )
        print("EMBED status:", resp.status_code)
        if resp.status_code != 200:
            print("EMBED error body:", resp.text[:300])
        else:
            data = resp.json()
            emb = data["data"][0]["embedding"]
            print("EMBED ok, dims:", len(emb))
    except Exception as exc:  # noqa: BLE001
        print("EMBED request failed:", exc)


if __name__ == "__main__":
    main()