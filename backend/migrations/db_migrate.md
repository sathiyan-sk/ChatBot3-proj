Build or update the database with Alembic

Set `DATABASE_URL` to the PostgreSQL connection string for the database you
intend to update. From the `backend` directory, run:

```powershell
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current
```

`upgrade head` applies only migrations that are not already recorded in
`alembic_version`. If the database is currently at
`0003_version_document_chunks`, it will apply, in order:

1. `0004_ingestion_leases` — adds failure codes, bounded retry
   scheduling, attempt counts, and worker lease expiry.
2. `0005_storage_upload_intents` — adds durable storage-upload intents for
   cleanup after interrupted uploads.

Afterward, `alembic current` should report
`0005_storage_upload_intents (head)`. Back up the database first, and verify
`DATABASE_URL` points to the intended deployment database before running the
upgrade. Do not manually modify `alembic_version`.
