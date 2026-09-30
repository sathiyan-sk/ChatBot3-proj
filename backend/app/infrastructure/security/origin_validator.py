from __future__ import annotations

from urllib.parse import urlsplit


class OriginValidator:
    """Validates widget request origins against an application's allow-list.

    Local development origins (localhost / 127.0.0.1) and the file:// "null"
    origin are always permitted. This mirrors the CORS middleware in
    app/main.py, which deliberately whitelists them so the embeddable widget
    can be tested from local pages and from a local HTML file on disk.
    Remote origins must appear in the application's allowed_origins list.
    """

    _LOCAL_HOSTS = {"localhost", "127.0.0.1"}
    _NULL_ORIGIN = "null"

    def is_allowed(
        self,
        origin: str | None,
        allowed_origins: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> bool:
        value = (origin or "").strip()
        if not value:
            return False

        normalized_origin = self._normalize(value)

        # file:// pages send "Origin: null" - intentionally supported for
        # local widget testing (see CORS config in app/main.py).
        if normalized_origin == self._NULL_ORIGIN:
            return True

        # Local development servers are always trusted, but only for exact
        # loopback hosts (not lookalike domains such as localhost.example).
        if self._is_local_origin(normalized_origin):
            return True

        allowed = [
            self._normalize(item)
            for item in (allowed_origins or [])
            if item and item.strip()
        ]

        if not allowed:
            return True

        return normalized_origin in allowed

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().rstrip("/").lower()

    @classmethod
    def _is_local_origin(cls, origin: str) -> bool:
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError:
            return False

        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in cls._LOCAL_HOSTS
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and (port is None or 0 < port <= 65535)
        )