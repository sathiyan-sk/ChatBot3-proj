from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ApplicationError
from fastapi import HTTPException
from app.api.admin.conversations import create_application_sandbox_message
from app.api.client.chat import create_chat_message
from app.api.client.chat import create_customer_preview_message
from app.api.client.widget import start_widget_session
from app.api.dependencies import require_admin
from app.api.router import api_router
from app.api.schemas.chat import ChatHistoryMessageRequest
from app.api.admin.leads import _csv_cell
from app.modules.leads.application.services import LeadManagementService
from app.modules.leads.domain.entities import (
    ConversationFeedback,
    ConversationFeedbackEntry,
    FeedbackAnalytics,
    FeedbackRatingCount,
    Lead,
)
from app.modules.leads.domain.policies import (
    LEAD_CONSENT_TEXT_VERSION,
    has_contact_intent,
)
from app.modules.question_answering.application.commands import AskChatQuestionCommand
from app.modules.question_answering.application.services import ChatApplicationService
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
)


class _MemoryLeadRepository:
    def __init__(self):
        self.leads = {}
        self.feedback = {}
        self.conversation_titles = {}
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

    def feedback_analytics_for_application(
        self, *, application_id, created_from, created_to, rating
    ):
        matching = self._matching_feedback(
            application_id, created_from, created_to, rating
        )
        count = len(matching)
        distribution = {
            star: sum(item.rating == star for item in matching) for star in range(1, 6)
        }
        return FeedbackAnalytics(
            response_count=count,
            average_rating=(
                sum(item.rating for item in matching) / count if count else 0.0
            ),
            five_star_responses=distribution[5],
            positive_rating_percentage=(
                sum(item.rating >= 4 for item in matching) * 100.0 / count
                if count
                else 0.0
            ),
            distribution=tuple(
                FeedbackRatingCount(rating=star, count=distribution[star])
                for star in range(1, 6)
            ),
        )

    def list_feedback_for_application(
        self, *, application_id, created_from, created_to, rating, limit, offset
    ):
        matching = sorted(
            self._matching_feedback(application_id, created_from, created_to, rating),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
        return [
            ConversationFeedbackEntry(
                feedback=item,
                conversation_title=self.conversation_titles.get(item.conversation_id),
            )
            for item in matching[offset : offset + limit]
        ]

    def _matching_feedback(self, application_id, created_from, created_to, rating):
        return [
            item
            for item in self.feedback.values()
            if item.application_id == application_id
            and (created_from is None or item.created_at >= created_from)
            and (created_to is None or item.created_at < created_to)
            and (rating is None or item.rating == rating)
        ]

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


def _record_feedback(repository, *, application_id, rating, created_at):
    conversation_id = str(uuid4())
    feedback = ConversationFeedback(
        id=str(uuid4()),
        application_id=application_id,
        conversation_id=conversation_id,
        rating=rating,
        created_at=created_at,
        updated_at=created_at,
    )
    repository.feedback[conversation_id] = feedback
    repository.conversation_titles[conversation_id] = "Assistant conversation"
    return feedback


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


def test_feedback_analytics_are_application_scoped_and_handle_no_responses():
    repository = _MemoryLeadRepository()
    service = LeadManagementService(repository)
    now = datetime.now(timezone.utc)
    other_application_id = str(uuid4())
    _record_feedback(repository, application_id=APP_ID, rating=5, created_at=now)
    _record_feedback(
        repository,
        application_id=APP_ID,
        rating=3,
        created_at=now - timedelta(days=1),
    )
    _record_feedback(
        repository,
        application_id=other_application_id,
        rating=1,
        created_at=now,
    )

    analytics = service.feedback_analytics(application_id=APP_ID)
    assert analytics.response_count == 2
    assert analytics.average_rating == 4.0
    assert analytics.five_star_responses == 1
    assert analytics.positive_rating_percentage == 50.0
    assert [item.count for item in analytics.distribution] == [0, 0, 1, 0, 1]

    empty = service.feedback_analytics(application_id=str(uuid4()))
    assert empty.response_count == 0
    assert empty.average_rating == 0.0
    assert empty.positive_rating_percentage == 0.0
    assert [item.count for item in empty.distribution] == [0, 0, 0, 0, 0]


def test_feedback_date_and_rating_filters_match_analytics_and_paginated_list():
    repository = _MemoryLeadRepository()
    service = LeadManagementService(repository)
    now = datetime.now(timezone.utc)
    _record_feedback(repository, application_id=APP_ID, rating=4, created_at=now)
    _record_feedback(
        repository,
        application_id=APP_ID,
        rating=4,
        created_at=now - timedelta(hours=1),
    )
    _record_feedback(
        repository,
        application_id=APP_ID,
        rating=5,
        created_at=now - timedelta(days=2),
    )

    filters = {
        "application_id": APP_ID,
        "created_from": now - timedelta(days=1),
        "rating": 4,
    }
    analytics = service.feedback_analytics(**filters)
    first_page = service.list_feedback(**filters, limit=1, offset=0)
    second_page = service.list_feedback(**filters, limit=1, offset=1)

    assert analytics.response_count == 2
    assert analytics.average_rating == 4.0
    assert len(first_page) == len(second_page) == 1
    assert first_page[0].feedback.id != second_page[0].feedback.id
    assert first_page[0].conversation_title == "Assistant conversation"


def test_feedback_query_rejects_invalid_date_range_and_rating():
    service = LeadManagementService(_MemoryLeadRepository())
    now = datetime.now(timezone.utc)

    with pytest.raises(ApplicationError) as date_error:
        service.list_feedback(
            application_id=APP_ID,
            created_from=now,
            created_to=now - timedelta(seconds=1),
        )
    assert date_error.value.code == "feedback_date_range_invalid"

    with pytest.raises(ApplicationError) as rating_error:
        service.feedback_analytics(application_id=APP_ID, rating=6)
    assert rating_error.value.code == "feedback_rating_invalid"


def test_feedback_read_routes_are_admin_authenticated_and_read_only():
    routes = [
        route
        for route in api_router.routes
        if route.path.startswith("/api/admin/feedback/")
    ]

    assert {route.path for route in routes} == {
        "/api/admin/feedback/application/{application_id}/analytics",
        "/api/admin/feedback/application/{application_id}",
    }
    for route in routes:
        assert route.methods == {"GET"}
        assert require_admin in {
            dependency.call for dependency in route.dependant.dependencies
        }


def test_chat_request_rejects_application_id_mismatched_with_api_key():
    context = SimpleNamespace(application_id=APP_ID)

    class _UnusedService:
        def ask(self, _command):
            pytest.fail("mismatched application/key must fail before RAG")

    with pytest.raises(HTTPException) as error:
        create_chat_message(
            SimpleNamespace(
                application_id=str(uuid4()),
                conversation_identity="sandbox-test",
                message="Test",
                conversation_title="Sandbox",
                top_k=4,
            ),
            SimpleNamespace(state=SimpleNamespace(request_id=None)),
            context,
            _UnusedService(),
        )

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "chat_application_key_mismatch"


def test_customer_preview_without_key_uses_platform_generation():
    class _PlatformProvider:
        def generate(self, **_kwargs):
            return SimpleNamespace(
                text="Platform-default response",
            )

    response = create_customer_preview_message(
        request=SimpleNamespace(
            conversation_identity="customer-preview",
            conversation_title="Customer Preview",
            message="Hello",
            top_k=5,
        ),
        http_request=SimpleNamespace(state=SimpleNamespace(request_id=None)),
        application_context=None,
        service=SimpleNamespace(),
        platform_llm_provider=_PlatformProvider(),
    )

    assert response.application_id is None
    assert response.answer == "Platform-default response"
    assert response.citations == []
    assert response.actions == []


def test_keyed_customer_preview_does_not_persist_conversation():
    history = [
        SimpleNamespace(role="user", content="Earlier question"),
        SimpleNamespace(role="assistant", content="Earlier answer"),
    ]
    captured = {}

    class _Service:
        def ask(self, command):
            captured["command"] = command
            return SimpleNamespace(
                conversation_id="",
                answer_text="Preview answer",
                citations=[],
                actions=[],
            )

    response = create_customer_preview_message(
        request=SimpleNamespace(
            conversation_identity="customer-preview",
            conversation_title="Customer Preview",
            message="Follow-up",
            top_k=5,
            conversation_messages=[
                ChatHistoryMessageRequest(
                    role=item.role,
                    content=item.content,
                )
                for item in history
            ],
        ),
        http_request=SimpleNamespace(state=SimpleNamespace(request_id=None)),
        application_context=SimpleNamespace(application_id=APP_ID),
        service=_Service(),
        platform_llm_provider=SimpleNamespace(),
    )

    command = captured["command"]
    assert command.persist_conversation is False
    assert command.conversation_messages == [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]
    assert response.conversation_id == ""
    assert response.answer == "Preview answer"


def test_nonpersistent_application_preview_passes_in_memory_history_to_rag():
    captured = {}

    class _Pipeline:
        def run(self, request):
            captured["pipeline_request"] = request
            return SimpleNamespace(answer_text="RAG preview answer", citations=[])

    service = ChatApplicationService(
        knowledge_base_repository=SimpleNamespace(
            get_by_application_id=lambda _application_id: SimpleNamespace(id="kb-id")
        ),
        document_repository=SimpleNamespace(
            list_by_knowledge_base_id=lambda **_kwargs: [
                SimpleNamespace(ready_version=1, status="ready")
            ]
        ),
        settings_repository=SimpleNamespace(
            get_by_application_id=lambda _application_id: SimpleNamespace(
                inactivity_timeout_minutes=30,
                max_context_messages=8,
                llm_temperature="0.2",
                prompt_system_template=None,
            )
        ),
        conversation_service=SimpleNamespace(
            resolve_conversation=lambda _command: pytest.fail(
                "global customer preview must not persist a conversation"
            )
        ),
        question_answering_pipeline_factory=lambda _settings: _Pipeline(),
    )

    result = service.ask(
        AskChatQuestionCommand(
            application_id=APP_ID,
            conversation_identity="customer-preview",
            message_text="Follow-up",
            persist_conversation=False,
            conversation_messages=[
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
            ],
        )
    )

    assert result.conversation_id == ""
    assert result.answer_text == "RAG preview answer"
    assert captured["pipeline_request"].messages == [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Follow-up"},
    ]


def test_application_sandbox_route_preserves_one_conversation_until_closed():
    captured = {}

    class _Service:
        def ask(self, command):
            captured["command"] = command
            return SimpleNamespace(
                conversation_id=CONVERSATION_ID,
                answer_text="Sandbox answer",
                citations=[],
                actions=[],
            )

    response = create_application_sandbox_message(
        application_id=APP_ID,
        request=SimpleNamespace(
            application_id=APP_ID,
            message="Test question",
            top_k=4,
        ),
        http_request=SimpleNamespace(state=SimpleNamespace(request_id=None)),
        application_context=SimpleNamespace(application_id=APP_ID),
        service=_Service(),
    )

    assert captured["command"].conversation_identity == f"sandbox-{APP_ID}"
    assert captured["command"].preserve_conversation is True
    assert response.conversation_id == CONVERSATION_ID


def test_application_sandbox_route_rejects_a_mismatched_api_key():
    class _Service:
        def ask(self, _command):
            pytest.fail("mismatched application/key must fail before RAG")

    with pytest.raises(HTTPException) as error:
        create_application_sandbox_message(
            application_id=APP_ID,
            request=SimpleNamespace(
                application_id=APP_ID,
                message="Test question",
                top_k=4,
            ),
            http_request=SimpleNamespace(state=SimpleNamespace(request_id=None)),
            application_context=SimpleNamespace(application_id=str(uuid4())),
            service=_Service(),
        )

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "chat_application_key_mismatch"


def test_application_sandbox_route_is_admin_authenticated():
    route = next(
        route
        for route in api_router.routes
        if route.path
        == "/api/admin/conversations/application/{application_id}/sandbox/messages"
    )

    assert route.methods == {"POST"}
    assert require_admin in {
        dependency.call for dependency in route.dependant.dependencies
    }


def test_widget_session_uses_application_timeout_and_restores_active_history():
    conversation = SimpleNamespace(id=CONVERSATION_ID)
    message = SimpleNamespace(
        role="assistant",
        content="Restored answer",
        created_at=datetime.now(timezone.utc),
    )
    captured = {}

    class _ConversationService:
        def cleanup_expired_conversations(self, **kwargs):
            captured["cleanup"] = kwargs

        def resolve_conversation(self, command):
            captured["resolve"] = command
            return conversation

        def get_conversation_detail(self, query):
            captured["detail"] = query
            return SimpleNamespace(messages=[message])

    class _SettingsRepository:
        def get_by_application_id(self, application_id):
            captured["settings_application_id"] = application_id
            return SimpleNamespace(inactivity_timeout_minutes=9)

    result = start_widget_session(
        payload=SimpleNamespace(conversation_identity="visitor-123"),
        request=SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=SimpleNamespace(chat_history_retention_days=30)
                )
            )
        ),
        response=SimpleNamespace(headers={}),
        application_id=APP_ID,
        conversation_service=_ConversationService(),
        settings_service=SimpleNamespace(
            settings_repository=_SettingsRepository()
        ),
    )

    assert captured["settings_application_id"] == APP_ID
    assert captured["resolve"].inactivity_timeout_minutes == 9
    assert captured["cleanup"]["application_id"] == APP_ID
    assert captured["detail"].conversation_id == CONVERSATION_ID
    assert [item.content for item in result.messages] == ["Restored answer"]


def test_conversation_retention_uses_each_applications_configured_days():
    first_application_id = str(uuid4())
    second_application_id = str(uuid4())
    retention_rows = [
        (first_application_id, 2),
        (second_application_id, None),
    ]

    class _Session:
        def __init__(self):
            self.call_count = 0
            self.delete_statements = []

        def execute(self, statement):
            self.call_count += 1
            if self.call_count == 1:
                return SimpleNamespace(all=lambda: retention_rows)
            self.delete_statements.append(statement)
            return SimpleNamespace(rowcount=1)

    session = _Session()
    deleted_count = SqlAlchemyConversationRepository(
        session
    ).delete_expired_conversations(
        default_retention_days=10,
    )

    assert deleted_count == 2
    assert len(session.delete_statements) == 2
    cutoffs = [
        next(
            value
            for value in statement.compile().params.values()
            if isinstance(value, datetime)
        )
        for statement in session.delete_statements
    ]
    assert abs(abs((cutoffs[1] - cutoffs[0]).total_seconds()) - 8 * 86400) < 2


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
    resolved_commands = []

    class _ConversationService:
        def resolve_conversation(self, command):
            resolved_commands.append(command)
            return conversation

        def append_message(self, command):
            message = SimpleNamespace(id=str(uuid4()))
            messages.append((command, message))
            return message

    class _SettingsRepository:
        def get_by_application_id(self, _application_id):
            return SimpleNamespace(inactivity_timeout_minutes=9)

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
            preserve_conversation=True,
        )
    )

    assert result.conversation_id == CONVERSATION_ID
    assert resolved_commands[0].inactivity_timeout_minutes is None
    assert result.citations == []
    assert result.actions[0].type == "contact_enquiry"
    assert [item[0].role for item in messages] == ["user", "assistant"]
