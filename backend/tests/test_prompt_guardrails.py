from app.knowledge_engine.generation.prompt_builder import PromptBuilder


def test_system_prompt_prohibits_leaking_internal_context_language():
    system_prompt = PromptBuilder().build_system_prompt()
    lowered = system_prompt.lower()

    assert "the context i have access to" in lowered
    assert "retrieved context" in lowered
    assert "hidden retrieval" in lowered
    assert "company context" in lowered


def test_user_prompt_instructs_not_to_reveal_system_processes():
    user_prompt = PromptBuilder().build_user_prompt(
        query_text="What is the price of a universal answer?",
        conversation_messages=None,
        retrieved_chunks=[],
    )
    lowered = user_prompt.lower()

    assert "hidden retrieval" in lowered or "internal retrieval" in lowered
    assert "do not mention" in lowered
    assert "company context" in lowered
