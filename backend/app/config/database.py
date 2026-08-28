from __future__ import annotations

from sqlalchemy.engine import URL, make_url

from app.config.settings import DatabaseSettings


def build_database_url(settings: DatabaseSettings) -> str:
    url: URL = make_url(settings.url)
    return str(url)


def is_sqlite_database(settings: DatabaseSettings) -> bool:
    url: URL = make_url(settings.url)
    return url.get_backend_name().startswith("sqlite")
