from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ApplicationError
from app.api.admin.leads import _csv_cell
from app.modules.leads.application.services import LeadManagementService
from app.modules.leads.domain.entities import ConversationFeedback, Lead
from app.modules.leads.domain.policies import (
    LEAD_CONSENT_TEXT_VERSION,
    has_contact_intent,
)
from app.modules.question_answering.application.commands import AskChatQuestionCommand
from app.modules.question_answering.application.services import ChatApplicationService


class _MemoryLeadRepository:
    def __init__(self):
        self.leads = {}
        self.feedback = {}
        self.create_count = 0

    def conversation_belongs_to_application(self, *, conversation_id, application_id):
        return application_id == APP_ID and conversation_id == CONVERSATION_ID

    def get_by_idempotency_key(self, *, application_id, idempotency_key):
        return self.leads.get((application_id, idempotency_key))

    def create(self, **values):
        self.create_count += 1
        now = datetime.now(timezone.utc)
        lead = Lead(
            id=str(uuid4()),
            application_id=str(values["application_id"]),
            conversation_id=str(values["conversation_id"]),
            idempotency_key=values["idempotency_key"],
            name=values["name"],
            email=values["email"],
            phone=values["phone"],
            message=values["message"],
            status=values["status"],
            internal_note=None,
            consent_given=values["consent_given"],
            consent_text_version=values["consent_text_version"],
            consent_text=values["consent_text"],
            consented_at=values["consented_at"],
            created_at=now,
            updated_at=now,
        )
        self.leads[(lead.application_id, lead.idempotency_key)] = lead
        return lead

    def has_lead_for_conversation(self, *, application_id, conversation_id):
        return any(
            lead.application_id == application_id
            and lead.conversation_id == conversation_id
            for lead in self.leads.values()
        )

    def get_feedback(self, *, conversation_id):
        return self.feedback.get(conversation_id)

    def save_feedback(self, *, application_id, conversation_id, rating):
        current = self.feedback.get(conversation_id)
        if current:
            return current
        now = datetime.now(timezone.utc)
        feedback = ConversationFeedback(
            id=str(uuid4()),
            application_id=application_id,
            conversation_id=conversation_id,
            rating=rating,
            created_at=now,
            updated_at=now,
        )
        self.feedback[conversation_id] = feedback
        return feedback

    def update_for_application(self, *, application_id, lead_id, status, internal_note):
        for key, lead in self.leads.items():
            if lead.application_id == application_id and lead.id == lead_id:
                updated = replace(
                    lead,
                    status=status,
                    internal_note=internal_note,
                )
                self.leads[key] = updated
                return updated
        return None

    def delete_for_application(self, *, application_id, lead_id):
        for key, lead in self.leads.items():
            if lead.application_id == application_id and lead.id == lead_id:
                del self.leads[key]
                return True
        return False


APP_ID = str(uuid4())
CONVERSATION_ID = str(uuid4())
IDEMPOTENCY_KEY = str(uuid4())


def _submit(service, **overrides):
    values = {
        "application_id": APP_ID,
        "conversation_id": CONVERSATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "name": " Ada Lovelace ",
        "email": " ADA@example.com ",
        "phone": None,
        "message": " Please call me about plans. ",
        "consent": True,
        "consent_text_version": LEAD_CONSENT_TEXT_VERSION,
    }
    values.update(overrides)
    return service.submit(**values)


def test_lead_submission_normalizes_and_retries_idempotently():
    repository = _MemoryLeadRepository()
    service = LeadManagementService(repository)

    first = _submit(service)
    repeated = _submit(service)

    assert first.id == repeated.id
    assert first.name == "Ada Lovelace"
    assert first.email == "ada@example.com"
    assert first.message == "Please call me about plans."
    assert first.consent_given
    assert repository.create_count == 1


def test_lead_submission_rejects_reused_key_with_different_details():
    service = LeadManagementService(_MemoryLeadRepository())
    _submit(service)

    with pytest.raises(ApplicationError) as error:
        _submit(service, name="Different customer")

    assert error.value.code == "lead_idempotency_conflict"


def test_lead_submission_requires_consent_and_contact_method():
    service = LeadManagementService(_MemoryLeadRepository())

    with pytest.raises(ApplicationError) as consent_error:
        _submit(service, consent=False)
    assert consent_error.value.code == "lead_consent_required"

    with pytest.raises(ApplicationError) as contact_error:
        _submit(service, email=None)
    assert contact_error.value.code == "lead_contact_required"

    with pytest.raises(ApplicationError) as email_error:
        _submit(service, email="not-an-email")
    assert email_error.value.code == "lead_email_invalid"


def test_lead_submission_rejects_conversation_from_another_application():
    service = LeadManagementService(_MemoryLeadRepository())

    with pytest.raises(ApplicationError) as error:
        _submit(service, application_id=str(uuid4()))

    assert error.value.code == "conversation_not_found"


def test_admin_lead_mutations_are_scoped_to_application():
    repository = _MemoryLeadRepository()
    service = LeadManagementService(repository)
    lead = _submit(service)

    with pytest.raises(ApplicationError) as update_error:
        service.update_lead(
            application_id=str(uuid4()),
            lead_id=lead.id,
            status="contacted",
            internal_note="Followed up",
        )
    assert update_error.value.code == "lead_not_found"

    with pytest.raises(ApplicationError) as delete_error:
        service.delete_lead(
            application_id=str(uuid4()),
            lead_id=lead.id,
        )
    assert delete_error.value.code == "lead_not_found"
    assert (
        service.update_lead(
            application_id=APP_ID,
            lead_id=lead.id,
            status="contacted",
            internal_note="Followed up",
        ).status
        == "contacted"
    )


def test_conversation_feedback_is_one_rating_per_conversation():
    repository = _MemoryLeadRepository()
    service = LeadManagementService(repository)
    _submit(service)

    first = service.submit_feedback(
        application_id=APP_ID,
        conversation_id=CONVERSATION_ID,
        rating=5,
    )
    repeated = service.submit_feedback(
        application_id=APP_ID,
        conversation_id=CONVERSATION_ID,
        rating=2,
    )

    assert first.id == repeated.id
    assert repeated.rating == 5


@pytest.mark.parametrize(
    "message",
    [
        "Can someone contact me about pricing?",
        "I would like to speak with your sales team.",
        "Please call me.",
    ],
)
def test_contact_intent_rules_detect_explicit_contact_requests(message):
    assert has_contact_intent(message)


def test_contact_intent_rules_do_not_trigger_on_negated_contact_request():
    assert not has_contact_intent("Please do not contact me.")


@pytest.mark.parametrize(
    "value",
    ['=HYPERLINK("https://example.invalid")', "  =1+1", "\t@SUM(A1:A2)"],
)
def test_csv_cells_neutralize_spreadsheet_formulas(value):
    assert _csv_cell(value).startswith("'")


def test_contact_intent_returns_structured_action_without_calling_rag():
    conversation = SimpleNamespace(id=CONVERSATION_ID)
    messages = []

    class _ConversationService:
        def resolve_conversation(self, _command):
            return conversation

        def append_message(self, command):
            message = SimpleNamespace(id=str(uuid4()))
            messages.append((command, message))
            return message

    class _SettingsRepository:
        def get_by_application_id(self, _application_id):
            return None

    service = ChatApplicationService(
        knowledge_base_repository=SimpleNamespace(
            get_by_application_id=lambda _application_id: pytest.fail(
                "contact flow must not query the knowledge base"
            )
        ),
        document_repository=SimpleNamespace(),
        settings_repository=_SettingsRepository(),
        conversation_service=_ConversationService(),
        question_answering_pipeline_factory=lambda _settings: pytest.fail(
            "contact flow must not call the RAG pipeline"
        ),
    )

    result = service.ask(
        AskChatQuestionCommand(
            application_id=APP_ID,
            conversation_identity="visitor-123",
            message_text="Can someone contact me about pricing?",
        )
    )

    assert result.conversation_id == CONVERSATION_ID
    assert result.citations == []
    assert result.actions[0].type == "contact_enquiry"
    assert [item[0].role for item in messages] == ["user", "assistant"]
