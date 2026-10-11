from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.document_model import DocumentModel
from app.infrastructure.db.models.storage_upload_intent_model import (
    StorageUploadIntentModel,
)

logger = logging.getLogger(__name__)


def cleanup_stale_storage_upload_intents(
    session_factory,
    storage_provider: object,
    *,
    stale_after_minutes: int = 30,
    batch_size: int = 20,
) -> int:
    session: Session = session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=max(1, stale_after_minutes)
        )
        intents = session.execute(
            select(StorageUploadIntentModel)
            .where(StorageUploadIntentModel.created_at <= cutoff)
            .order_by(StorageUploadIntentModel.created_at.asc())
            .limit(max(1, batch_size))
            .with_for_update(skip_locked=True)
        ).scalars().all()

        delete_object = getattr(storage_provider, "delete", None)
        if not callable(delete_object):
            raise RuntimeError(
                "Storage provider does not support orphan cleanup."
            )

        cleaned_count = 0
        for intent in intents:
            document_exists = session.execute(
                select(DocumentModel.id)
                .where(DocumentModel.storage_path == intent.storage_path)
                .limit(1)
            ).scalar_one_or_none()
            if document_exists is None:
                delete_object(intent.storage_path)
            session.delete(intent)
            cleaned_count += 1

        session.commit()
        if cleaned_count:
            logger.info(
                "Reconciled stale storage upload intents",
                extra={"cleaned_intent_count": cleaned_count},
            )
        return cleaned_count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
