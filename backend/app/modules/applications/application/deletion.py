from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.infrastructure.db.models.application_model import ApplicationModel
from app.infrastructure.db.models.api_key_model import ApiKeyModel
from app.infrastructure.db.models.conversation_model import ConversationModel
from app.infrastructure.db.models.document_model import DocumentModel
from app.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from app.infrastructure.db.models.lead_model import (
    ConversationFeedbackModel,
    LeadModel,
)
from app.infrastructure.db.models.message_model import MessageModel
from app.infrastructure.db.models.settings_model import SettingsModel
from app.infrastructure.db.models.storage_upload_intent_model import (
    StorageUploadIntentModel,
)
from app.infrastructure.db.models.widget_model import WidgetModel
from app.infrastructure.providers.storage.supabase_storage_provider import (
    SupabaseStorageProvider,
)
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider

logger = logging.getLogger(__name__)


class ApplicationDeletionService:
    def __init__(
        self,
        *,
        session: Session,
        storage_provider: SupabaseStorageProvider,
        vector_provider: PgVectorProvider,
    ) -> None:
        self._session = session
        self._storage_provider = storage_provider
        self._vector_provider = vector_provider

    def get_deletion_summary(self, application_id: str) -> dict[str, int]:
        application = self._session.execute(
            select(ApplicationModel).where(
                ApplicationModel.id == application_id,
            )
        ).scalar_one_or_none()
        if application is None:
            raise ApplicationError(
                message="Application not found.",
                code="application_not_found",
                status_code=404,
            )
        if application.is_active:
            raise ApplicationError(
                message="Deactivate this application before reviewing deletion.",
                code="application_must_be_deactivated",
                status_code=409,
            )

        documents = self._session.execute(
            select(DocumentModel).where(
                DocumentModel.application_id == application.id,
            )
        ).scalars().all()
        processing_documents = sum(
            document.status == "processing"
            for document in documents
        )
        knowledge_base_ids = {
            str(knowledge_base_id)
            for knowledge_base_id in self._session.execute(
                select(KnowledgeBaseModel.id).where(
                    KnowledgeBaseModel.application_id == application.id,
                )
            ).scalars()
        }
        knowledge_base_ids.update(
            str(document.knowledge_base_id)
            for document in documents
        )

        upload_intent_filters = [
            StorageUploadIntentModel.application_id == application.id,
        ]
        for knowledge_base_id in knowledge_base_ids:
            upload_intent_filters.append(
                StorageUploadIntentModel.storage_path.like(
                    f"{knowledge_base_id}/%"
                )
            )
        upload_intents = self._session.execute(
            select(StorageUploadIntentModel).where(
                or_(*upload_intent_filters),
            )
        ).scalars().all()
        recent_upload_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=30,
        )
        recent_uploads = sum(
            intent.created_at >= recent_upload_cutoff
            for intent in upload_intents
        )
        for intent in upload_intents:
            try:
                knowledge_base_ids.add(
                    str(UUID(intent.storage_path.split("/", maxsplit=1)[0]))
                )
            except ValueError as exc:
                raise ApplicationError(
                    message="An upload record has an invalid storage path.",
                    code="application_storage_path_invalid",
                    status_code=409,
                ) from exc

        def count_for_application(model) -> int:
            return self._session.execute(
                select(func.count()).select_from(model).where(
                    model.application_id == application.id,
                )
            ).scalar_one()
        message_count = self._session.execute(
            select(func.count(MessageModel.id))
            .select_from(MessageModel)
            .join(
                ConversationModel,
                ConversationModel.id == MessageModel.conversation_id,
            )
            .where(ConversationModel.application_id == application.id)
        ).scalar_one()

        return {
            "knowledge_bases": int(count_for_application(KnowledgeBaseModel) or 0),
            "documents": int(count_for_application(DocumentModel) or 0),
            "processing_documents": processing_documents,
            "stored_files": sum(
                len(self._storage_provider.list_prefix(knowledge_base_id))
                for knowledge_base_id in knowledge_base_ids
            ),
            "indexed_chunks": sum(
                self._vector_provider.count_knowledge_base_chunks(
                    knowledge_base_id=knowledge_base_id,
                )
                for knowledge_base_id in knowledge_base_ids
            ),
            "conversations": int(count_for_application(ConversationModel) or 0),
            "messages": int(message_count or 0),
            "leads": int(count_for_application(LeadModel) or 0),
            "feedback": int(
                count_for_application(ConversationFeedbackModel) or 0
            ),
            "api_keys": int(count_for_application(ApiKeyModel) or 0),
            "widgets": int(count_for_application(WidgetModel) or 0),
            "settings": int(count_for_application(SettingsModel) or 0),
            "upload_intents": len(upload_intents),
            "recent_uploads": recent_uploads,
        }

    def delete_permanently(self, application_id: str) -> None:
        try:
            application = self._lock_application(application_id)
            if application is None:
                return
            if application.is_active:
                raise ApplicationError(
                    message=(
                        "Deactivate this application before deleting it "
                        "permanently."
                    ),
                    code="application_must_be_deactivated",
                    status_code=409,
                )

            documents = self._session.execute(
                select(DocumentModel)
                .where(DocumentModel.application_id == application.id)
                .order_by(DocumentModel.id)
                .with_for_update()
            ).scalars().all()
            if any(document.status == "processing" for document in documents):
                raise ApplicationError(
                    message=(
                        "This application has documents being processed. "
                        "Wait for ingestion to finish, then retry deletion."
                    ),
                    code="application_ingestion_in_progress",
                    status_code=409,
                )

            knowledge_base_ids = {
                str(knowledge_base_id)
                for knowledge_base_id in self._session.execute(
                    select(KnowledgeBaseModel.id).where(
                        KnowledgeBaseModel.application_id == application.id,
                    )
                ).scalars()
            }
            knowledge_base_ids.update(
                str(document.knowledge_base_id)
                for document in documents
            )

            intent_filters = [
                StorageUploadIntentModel.application_id == application.id,
            ]
            for knowledge_base_id in knowledge_base_ids:
                intent_filters.append(
                    StorageUploadIntentModel.storage_path.like(
                        f"{knowledge_base_id}/%"
                    )
                )
            upload_intents = self._session.execute(
                select(StorageUploadIntentModel)
                .where(or_(*intent_filters))
                .with_for_update()
            ).scalars().all()
            recent_upload_cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=30,
            )
            if any(
                intent.created_at >= recent_upload_cutoff
                for intent in upload_intents
            ):
                raise ApplicationError(
                    message=(
                        "A file upload is still being finalized. Wait a few "
                        "minutes, then retry application deletion."
                    ),
                    code="application_upload_in_progress",
                    status_code=409,
                )
            for intent in upload_intents:
                prefix = intent.storage_path.split("/", maxsplit=1)[0]
                try:
                    knowledge_base_ids.add(str(UUID(prefix)))
                except ValueError as exc:
                    raise ApplicationError(
                        message=(
                            "An upload record has an invalid storage path. "
                            "The application was kept so cleanup can be retried."
                        ),
                        code="application_storage_path_invalid",
                        status_code=409,
                    ) from exc

            for knowledge_base_id in sorted(knowledge_base_ids):
                self._vector_provider.delete_knowledge_base_chunks(
                    knowledge_base_id=knowledge_base_id,
                )
                self._storage_provider.delete_prefix(knowledge_base_id)

            for intent in upload_intents:
                self._session.delete(intent)

            self._session.execute(
                delete(ApplicationModel).where(
                    ApplicationModel.id == application.id,
                )
            )
            self._session.commit()
            logger.info(
                "Application and associated data permanently deleted",
                extra={"application_id": str(application.id)},
            )
        except ApplicationError:
            self._session.rollback()
            raise
        except Exception as exc:
            self._session.rollback()
            logger.exception(
                "Could not completely delete application",
                extra={"application_id": application_id},
            )
            raise ApplicationError(
                message=(
                    "Application deletion did not complete. The application "
                    "has been deactivated; retry deletion after resolving the "
                    "cleanup error."
                ),
                code="application_delete_failed",
                status_code=502,
            ) from exc

    def _lock_application(
        self,
        application_id: str,
    ) -> ApplicationModel | None:
        return self._session.execute(
            select(ApplicationModel)
            .where(ApplicationModel.id == application_id)
            .with_for_update()
        ).scalar_one_or_none()
