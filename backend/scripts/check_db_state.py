"""Check pgvector extension and current table state on the target DB."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config.settings import get_settings  # noqa: E402


def main() -> None:
    engine = create_engine(get_settings().database.url)
    with engine.connect() as conn:
        ext = conn.execute(
            text("select extname from pg_extension where extname = 'vector'")
        ).scalar()
        print("PGVECTOR_EXT:", ext or "NOT INSTALLED")

        tables = conn.execute(
            text(
                "select tablename from pg_tables "
                "where schemaname = 'public' order by tablename"
            )
        ).scalars().all()
        print("TABLES:", tables)

    engine.dispose()


if __name__ == "__main__":
    main()