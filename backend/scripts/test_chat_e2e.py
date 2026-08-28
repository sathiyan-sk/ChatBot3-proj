"""End-to-end chat test: full QA pipeline against the live DB + OpenRouter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.dependencies import get_question_answering_pipeline  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.infrastructure.db.session import create_session_factory  # noqa: E402
from app.knowledge_engine.shared.models import (  # noqa: E402
    QuestionAnsweringPipelineRequest,
)


def main() -> None:
    settings = get_settings()
    session_factory = create_session_factory(settings.database.url)
    session = session_factory()

    try:
        pipeline = get_question_answering_pipeline(
            request=type("R", (), {"app": type("A", (), {"state": type("S", (), {"settings": settings})()})()})(),
            session=session,
        )

        result = pipeline.run(
            QuestionAnsweringPipelineRequest(
                application_id="49025ce3-c3dd-4fc5-80ee-9aa10fbaf9b4",
                knowledge_base_id="",
                query_text="What is Sathiyan's experience?",
                conversation_id="",
                messages=[],
                top_k=4,
            )
        )
        print("ANSWER:", result.answer_text[:200])
        print("CITATIONS:", len(result.citations))
        print("CHAT_E2E_OK")
    finally:
        session.close()


if __name__ == "__main__":
    main()