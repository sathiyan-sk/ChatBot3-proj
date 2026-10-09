from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ContextManager, Generator, Literal, Protocol

from app.infrastructure.observability.logging import get_request_id
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider

logger = logging.getLogger(__name__)
TraceRunType = Literal[
    "tool",
    "chain",
    "llm",
    "retriever",
    "embedding",
    "prompt",
    "parser",
]


@dataclass(slots=True, frozen=True)
class TraceContext:
    request_id: str
    _run: Any | None = field(default=None, repr=False, compare=False)

    def end(self, *, outputs: dict[str, Any]) -> None:
        if self._run is not None:
            self._run.end(outputs=outputs)


class TraceObserver(Protocol):
    def trace(
        self,
        *,
        name: str,
        run_type: TraceRunType = "chain",
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> ContextManager[TraceContext]: ...

    def flush(self) -> None: ...


class NoOpTraceObserver:
    @contextmanager
    def trace(
        self,
        *,
        name: str,
        run_type: TraceRunType = "chain",
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Generator[TraceContext, None, None]:
        _ = (name, run_type, inputs, metadata)
        yield TraceContext(request_id=request_id or "")

    def flush(self) -> None:
        return None


class LangSmithTraceObserver:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        project: str | None,
        endpoint: str | None = None,
    ) -> None:
        self.enabled = enabled and bool(api_key) and bool(project)
        self.project = project
        self._client: Any | None = None
        if self.enabled:
            from langsmith import Client

            self._client = Client(api_key=api_key, api_url=endpoint)

    @classmethod
    def from_settings(cls, settings: object) -> LangSmithTraceObserver:
        return cls(
            enabled=bool(getattr(settings, "langsmith_tracing", False)),
            api_key=getattr(settings, "langsmith_api_key", None),
            project=getattr(settings, "langsmith_project", None),
            endpoint=getattr(settings, "langsmith_endpoint", None),
        )

    @contextmanager
    def trace(
        self,
        *,
        name: str,
        run_type: TraceRunType = "chain",
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Generator[TraceContext, None, None]:
        if not self.enabled or self._client is None:
            yield TraceContext(request_id=request_id or "")
            return

        from langsmith import trace as langsmith_trace
        from langsmith import tracing_context

        trace_metadata = dict(metadata or {})
        if request_id:
            trace_metadata.setdefault("request_id", request_id)

        with tracing_context(
            enabled=True,
            client=self._client,
            project_name=self.project,
        ):
            with langsmith_trace(
                name=name,
                run_type=run_type,
                inputs=inputs or {},
                metadata=trace_metadata,
                project_name=self.project,
                client=self._client,
                tags=["qa-pipeline"] if run_type == "chain" else ["llm-provider"],
            ) as run:
                yield TraceContext(request_id=request_id or "", _run=run)

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush(timeout=5)
            except Exception:
                logger.exception("Failed to flush pending LangSmith traces")


class TracedLlmProvider(LlmProvider):
    """Observe provider calls without coupling provider contracts to LangSmith."""

    def __init__(
        self,
        *,
        provider: LlmProvider,
        trace_observer: TraceObserver,
    ) -> None:
        self._provider = provider
        self._trace_observer = trace_observer

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> LlmGenerationResult:
        request_id = get_request_id()
        if request_id == "-":
            request_id = None

        with self._trace_observer.trace(
            name="llm.generate",
            run_type="llm",
            inputs={
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
            },
            metadata={"provider": type(self._provider).__name__},
            request_id=request_id,
        ) as trace_context:
            result = self._provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            trace_context.end(
                outputs={
                    "answer": result.text,
                    "model": result.model,
                    "usage": {
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "total_tokens": result.total_tokens,
                    },
                    "latency_ms": result.latency_ms,
                    "provider_duration_ms": result.provider_duration_ms,
                }
            )
            return result


def create_trace_observer(settings: object) -> TraceObserver:
    if not getattr(settings, "langsmith_tracing", False):
        return NoOpTraceObserver()
    return LangSmithTraceObserver.from_settings(settings)
