from __future__ import annotations


class OriginValidator:
    """Validates widget request origins against an application's allow-list.

    Local development origins (localhost / 127.0.0.1) and the file:// "null"
    origin are always permitted. This mirrors the CORS middleware in
    app/main.py, which deliberately whitelists them so the embeddable widget
    can be tested from local pages and from a local HTML file on disk.
    Remote origins must appear in the application's allowed_origins list.
    """

    _ALWAYS_ALLOWED_PREFIXES = (
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
    )
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

        # Local development servers are always trusted.
        for prefix in self._ALWAYS_ALLOWED_PREFIXES:
            if normalized_origin.startswith(prefix):
                return True

        allowed = [
            self._normalize(item)
            for item in (allowed_origins or [])
            if item and item.strip()
        ]

        if not allowed:
            return False

        return normalized_origin in allowed

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().rstrip("/").lower()