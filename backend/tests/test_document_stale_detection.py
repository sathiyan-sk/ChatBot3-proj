from datetime import datetime, timedelta, timezone

from app.api.admin.documents import _is_ingestion_stale


def test_processing_document_is_stale_after_configured_timeout():
    now = datetime.now(timezone.utc)
    updated_at = now - timedelta(minutes=31)

    assert _is_ingestion_stale(
        updated_at,
        now=now,
        stale_after_minutes=30,
    )


def test_recent_processing_document_is_not_stale():
    now = datetime.now(timezone.utc)
    updated_at = now - timedelta(minutes=29)

    assert not _is_ingestion_stale(
        updated_at,
        now=now,
        stale_after_minutes=30,
    )