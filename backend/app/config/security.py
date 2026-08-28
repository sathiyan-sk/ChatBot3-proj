from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SecuritySettings:
    admin_username: str
    admin_password: str
    api_key_header_name: str
    request_id_header_name: str


def load_security_settings() -> SecuritySettings:
    return SecuritySettings(
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "change-this-password"),
        api_key_header_name=os.getenv("API_KEY_HEADER_NAME", "X-API-Key"),
        request_id_header_name=os.getenv("REQUEST_ID_HEADER_NAME", "X-Request-ID"),
    )


def validate_security_settings(settings: SecuritySettings) -> None:
    if not settings.admin_username.strip():
        raise ValueError("ADMIN_USERNAME must not be empty.")

    if not settings.admin_password.strip():
        raise ValueError("ADMIN_PASSWORD must not be empty.")

    if len(settings.admin_password) < 8:
        raise ValueError("ADMIN_PASSWORD must be at least 8 characters long.")

    if not settings.api_key_header_name.strip():
        raise ValueError("API_KEY_HEADER_NAME must not be empty.")

    if not settings.request_id_header_name.strip():
        raise ValueError("REQUEST_ID_HEADER_NAME must not be empty.")