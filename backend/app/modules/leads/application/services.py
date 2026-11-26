from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import ApplicationError
from app.modules.leads.domain.entities import (
    ConversationFeedback,
    ConversationFeedbackEntry,
    FeedbackAnalytics,
    Lead,
    LeadOperationalOverview,
)
from app.modules.leads.domain.policies import (
    LEAD_CONSENT_TEXT,
    LEAD_CONSENT_TEXT_VERSION,
    normalize_lead_contact,
)
from app.modules.leads.domain.repository_interfaces import LeadRepositoryInterface

LEAD_STATUSES = frozenset({"new", "contacted", "closed"})


@dataclass(slots=True)
class LeadManagementService:
    repository: LeadRepositoryInterface

    def submit(
        self,
        *,
        application_id: str,
        conversation_id: str,
        idempotency_key: str,
        name: str,
        email: str | None,
        phone: str | None,
        message: str | None,
        consent: bool,
        consent_text_version: str,
    ) -> Lead:
        try:
            application_id = str(UUID(application_id))
            conversation_id = str(UUID(conversation_id))
            idempotency_key = str(UUID(idempotency_key))
        except ValueError as exc:
            raise ApplicationError(
                message="Application, conversation, or submission identifier is invalid.",
                code="lead_identifier_invalid",
                status_code=422,
            ) from exc

        if not consent or consent_text_version != LEAD_CONSENT_TEXT_VERSION:
            raise ApplicationError(
                message="Explicit consent is required to submit an enquiry.",
                code="lead_consent_required",
                status_code=422,
            )
        if not self.repository.conversation_belongs_to_application(
            conversation_id=conversation_id,
            application_id=application_id,
        ):
            raise ApplicationError(
                message="Conversation was not found for this application.",
                code="conversation_not_found",
                status_code=404,
            )

        normalized = normalize_lead_contact(
            name=name,
            email=email,
            phone=phone,
            message=message,
        )
        values = {
            "application_id": UUID(application_id),
            "conversation_id": UUID(conversation_id),
            "idempotency_key": idempotency_key,
            "name": normalized[0],
            "email": normalized[1],
            "phone": normalized[2],
            "message": normalized[3],
            "status": "new",
            "consent_given": True,
            "consent_text_version": LEAD_CONSENT_TEXT_VERSION,
            "consent_text": LEAD_CONSENT_TEXT,
            "consented_at": datetime.now(timezone.utc),
        }

        existing = self.repository.get_by_idempotency_key(
            application_id=application_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if not self._matches_submission(existing, values):
                raise ApplicationError(
                    message="Submission identifier was already used for different enquiry details.",
                    code="lead_idempotency_conflict",
                    status_code=409,
                )
            return existing

        created = self.repository.create(**values)
        if not self._matches_submission(created, values):
            raise ApplicationError(
                message="Submission identifier was already used for different enquiry details.",
                code="lead_idempotency_conflict",
                status_code=409,
            )
        return created

    def submit_feedback(
        self,
        *,
        application_id: str,
        conversation_id: str,
        rating: int,
    ) -> ConversationFeedback:
        try:
            application_id = str(UUID(application_id))
            conversation_id = str(UUID(conversation_id))
        except ValueError as exc:
            raise ApplicationError(
                message="Application or conversation identifier is invalid.",
                code="feedback_identifier_invalid",
                status_code=422,
            ) from exc
        if not 1 <= rating <= 5:
            raise ApplicationError(
                message="Rating must be between 1 and 5.",
                code="feedback_rating_invalid",
                status_code=422,
            )
        if not self.repository.conversation_belongs_to_application(
            conversation_id=conversation_id,
            application_id=application_id,
        ):
            raise ApplicationError(
                message="Conversation was not found for this application.",
                code="conversation_not_found",
                status_code=404,
            )
        if not self.repository.has_lead_for_conversation(
            application_id=application_id,
            conversation_id=conversation_id,
        ):
            raise ApplicationError(
                message="A rating is available after submitting an enquiry.",
                code="feedback_requires_lead",
                status_code=409,
            )
        return self.repository.save_feedback(
            application_id=application_id,
            conversation_id=conversation_id,
            rating=rating,
        )

    def feedback_analytics(
        self,
        *,
        application_id: str,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        rating: int | None = None,
    ) -> FeedbackAnalytics:
        application_id, created_from, created_to = self._validate_feedback_query(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
            rating=rating,
            limit=1,
            offset=0,
        )
        return self.repository.feedback_analytics_for_application(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
            rating=rating,
        )

    def list_feedback(
        self,
        *,
        application_id: str,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        rating: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationFeedbackEntry]:
        application_id, created_from, created_to = self._validate_feedback_query(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
            rating=rating,
            limit=limit,
            offset=offset,
        )
        return self.repository.list_feedback_for_application(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
            rating=rating,
            limit=limit,
            offset=offset,
        )

    def list_leads(
        self,
        *,
        application_id: str,
        status: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        self._validate_admin_query(status, created_from, created_to, limit, offset)
        application_id = self._normalize_uuid(application_id, "application")
        return self.repository.list_for_application(
            application_id=application_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )

    def lead_operational_overview(
        self,
        *,
        application_id: str,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> LeadOperationalOverview:
        self._validate_admin_query(None, created_from, created_to, 1, 0)
        application_id = self._normalize_uuid(application_id, "application")
        return self.repository.operational_overview_for_application(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
        )

    def export_leads(
        self,
        *,
        application_id: str,
        status: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Lead]:
        self._validate_admin_query(status, created_from, created_to, 1, 0)
        application_id = self._normalize_uuid(application_id, "application")
        return self.repository.list_for_export(
            application_id=application_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
        )

    def update_lead(
        self,
        *,
        application_id: str,
        lead_id: str,
        status: str,
        internal_note: str | None,
    ) -> Lead:
        application_id = self._normalize_uuid(application_id, "application")
        lead_id = self._normalize_uuid(lead_id, "lead")
        if status not in LEAD_STATUSES:
            raise ApplicationError(
                message="Lead status must be new, contacted, or closed.",
                code="lead_status_invalid",
                status_code=422,
            )
        normalized_note = internal_note.strip() if internal_note else None
        if normalized_note and len(normalized_note) > 5000:
            raise ApplicationError(
                message="Internal note must be at most 5000 characters.",
                code="lead_note_too_long",
                status_code=422,
            )
        updated = self.repository.update_for_application(
            application_id=application_id,
            lead_id=lead_id,
            status=status,
            internal_note=normalized_note or None,
        )
        if updated is None:
            raise ApplicationError(
                message="Lead not found for this application.",
                code="lead_not_found",
                status_code=404,
            )
        return updated

    def delete_lead(self, *, application_id: str, lead_id: str) -> None:
        application_id = self._normalize_uuid(application_id, "application")
        lead_id = self._normalize_uuid(lead_id, "lead")
        if not self.repository.delete_for_application(
            application_id=application_id,
            lead_id=lead_id,
        ):
            raise ApplicationError(
                message="Lead not found for this application.",
                code="lead_not_found",
                status_code=404,
            )

    @staticmethod
    def _validate_admin_query(
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        offset: int,
    ) -> None:
        if status and status not in LEAD_STATUSES:
            raise ApplicationError(
                message="Lead status filter is invalid.",
                code="lead_status_invalid",
                status_code=422,
            )
        if created_from and created_to and created_from >= created_to:
            raise ApplicationError(
                message="Date range start must be before end.",
                code="lead_date_range_invalid",
                status_code=422,
            )
        if not 1 <= limit <= 500 or offset < 0:
            raise ApplicationError(
                message="Lead page size or offset is invalid.",
                code="lead_pagination_invalid",
                status_code=422,
            )

    @staticmethod
    def _normalize_uuid(value: str, label: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise ApplicationError(
                message=f"{label.capitalize()} identifier is invalid.",
                code=f"{label}_identifier_invalid",
                status_code=422,
            ) from exc

    @staticmethod
    def _validate_feedback_query(
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
        rating: int | None,
        limit: int,
        offset: int,
    ) -> tuple[str, datetime | None, datetime | None]:
        normalized_application_id = LeadManagementService._normalize_uuid(
            application_id,
            "application",
        )
        normalized_from = LeadManagementService._normalize_datetime(created_from)
        normalized_to = LeadManagementService._normalize_datetime(created_to)
        if normalized_from and normalized_to and normalized_from >= normalized_to:
            raise ApplicationError(
                message="Date range start must be before end.",
                code="feedback_date_range_invalid",
                status_code=422,
            )
        if rating is not None and not 1 <= rating <= 5:
            raise ApplicationError(
                message="Rating filter must be between 1 and 5.",
                code="feedback_rating_invalid",
                status_code=422,
            )
        if not 1 <= limit <= 500 or offset < 0:
            raise ApplicationError(
                message="Feedback page size or offset is invalid.",
                code="feedback_pagination_invalid",
                status_code=422,
            )
        return normalized_application_id, normalized_from, normalized_to

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _matches_submission(lead: Lead, values: dict[str, object]) -> bool:
        return all(
            getattr(lead, name) == value
            for name, value in (
                ("application_id", str(values["application_id"])),
                ("conversation_id", str(values["conversation_id"])),
                ("name", values["name"]),
                ("email", values["email"]),
                ("phone", values["phone"]),
                ("message", values["message"]),
            )
        )
