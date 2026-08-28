"""Diagnose widget 403 + chat 502 issues seen in the running app."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config.settings import get_settings  # noqa: E402


def main() -> None:
    engine = create_engine(get_settings().database.url)
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "select tablename from pg_tables "
                "where schemaname = 'public' order by tablename"
            )
        ).scalars().all()
        print("TABLES:", tables)

        if "applications" in tables:
            apps = conn.execute(
                text(
                    "select id, name, slug, is_active, allowed_origins "
                    "from applications"
                )
            ).mappings().all()
            print("APPLICATIONS:")
            for row in apps:
                print("  ", dict(row))

        if "widgets" in tables:
            widgets = conn.execute(
                text(
                    "select id, application_id, public_key, is_enabled "
                    "from widgets"
                )
            ).mappings().all()
            print("WIDGETS:")
            for w in widgets:
                print("  ", dict(w))

        if "api_keys" in tables:
            keys = conn.execute(
                text(
                    "select id, application_id, key_prefix, is_active "
                    "from api_keys"
                )
            ).mappings().all()
            print("API_KEYS:")
            for k in keys:
                print("  ", dict(k))

        if "documents" in tables:
            docs = conn.execute(
                text(
                    "select id, title, status, source_type "
                    "from documents order by created_at desc limit 10"
                )
            ).mappings().all()
            print("DOCUMENTS:")
            for d in docs:
                print("  ", dict(d))

    engine.dispose()


if __name__ == "__main__":
    main()