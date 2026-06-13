"""Runtime observability context shared across graph nodes and tools."""

from contextvars import ContextVar

chat_trace_id: ContextVar[str | None] = ContextVar("chat_trace_id", default=None)
