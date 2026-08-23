"""Tests for open_notebook.ai.redaction_wrapper."""

from typing import Any, AsyncIterator, List, Optional

import pytest
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

import open_notebook.ai.redaction_wrapper as wrapper_module
from open_notebook.ai.redaction_gateway import EgressOutcome, RedactionEngine, RuleData
from open_notebook.ai.redaction_wrapper import maybe_make_redaction_aware

RECEIVED: List[List[BaseMessage]] = []


class FakeChatModel(BaseChatModel):
    """Echoes the messages it receives; emits a canned alias response."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        RECEIVED.append([m.model_copy(deep=True) for m in messages])
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="工程师A完成了实验"))]
        )

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Any:
        RECEIVED.append([m.model_copy(deep=True) for m in messages])
        for text in ["结论：工程师", "A完成", "了实验。"]:
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        RECEIVED.append([m.model_copy(deep=True) for m in messages])
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="工程师A完成了实验"))]
        )

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        RECEIVED.append([m.model_copy(deep=True) for m in messages])
        for text in ["结论：工程师", "A完成", "了实验。"]:
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))


class FakeService:
    """Minimal stand-in for RedactionService (dictionary redaction only)."""

    def __init__(self, rules, enabled=True):
        self.enabled = enabled
        self.engine = RedactionEngine(rules)
        self.seen: List[List[BaseMessage]] = []

    async def redact_messages(self, messages):
        self.seen.append([m.model_copy(deep=True) for m in messages])
        if not self.enabled:
            return EgressOutcome(
                messages=list(messages), engine=RedactionEngine([]), redacted=False
            )
        copies = [m.model_copy(deep=True) for m in messages]
        for m in copies:
            wrapper_module._redact_with_engine(m, self.engine)
        return EgressOutcome(
            messages=copies, engine=self.engine, redacted=True
        )

    def get_cached_engine(self):
        return self.engine if self.enabled else None


@pytest.fixture(autouse=True)
def reset_received():
    RECEIVED.clear()


@pytest.fixture
def fake_service(monkeypatch):
    service = FakeService([RuleData("张三", "工程师A", "person")])
    monkeypatch.setattr(wrapper_module, "redaction_service", service)
    return service


def make_model():
    return maybe_make_redaction_aware(FakeChatModel())


# ---------------------------------------------------------------------------
# class swap mechanics
# ---------------------------------------------------------------------------
class TestClassSwap:
    def test_wraps_and_keeps_subclass_relation(self):
        model = make_model()
        assert isinstance(model, FakeChatModel)
        assert getattr(type(model), "_redaction_aware", False)

    def test_idempotent(self):
        model = make_model()
        cls_after_first = type(model)
        maybe_make_redaction_aware(model)
        assert type(model) is cls_after_first

    def test_non_chat_model_passthrough(self):
        assert maybe_make_redaction_aware(object()) is not None
        assert maybe_make_redaction_aware("nope") == "nope"

    def test_class_cached_per_base(self):
        m1 = make_model()
        m2 = make_model()
        assert type(m1) is type(m2)


# ---------------------------------------------------------------------------
# non-streaming async
# ---------------------------------------------------------------------------
class TestAsyncGenerate:
    @pytest.mark.asyncio
    async def test_input_redacted_and_output_restored(self, fake_service):
        model = make_model()
        result = await model.ainvoke([HumanMessage(content="张三做了什么")])
        # provider saw the alias
        assert RECEIVED[0][0].content == "工程师A做了什么"
        # user sees the original name restored
        assert result.content == "张三完成了实验"

    @pytest.mark.asyncio
    async def test_caller_messages_not_mutated(self, fake_service):
        model = make_model()
        message = HumanMessage(content="张三做了什么")
        await model.ainvoke([message])
        assert message.content == "张三做了什么"

    @pytest.mark.asyncio
    async def test_disabled_passthrough(self, monkeypatch):
        service = FakeService([], enabled=False)
        monkeypatch.setattr(wrapper_module, "redaction_service", service)
        model = make_model()
        result = await model.ainvoke([HumanMessage(content="张三做了什么")])
        assert RECEIVED[0][0].content == "张三做了什么"  # unredacted egress
        assert result.content == "工程师A完成了实验"  # no restore

    @pytest.mark.asyncio
    async def test_bind_delegation_still_redacts(self, fake_service):
        model = make_model()
        bound = model.bind(stop=None)
        result = await bound.ainvoke([HumanMessage(content="张三做了什么")])
        assert RECEIVED[0][0].content == "工程师A做了什么"
        assert result.content == "张三完成了实验"


# ---------------------------------------------------------------------------
# streaming async
# ---------------------------------------------------------------------------
class TestAsyncStream:
    @pytest.mark.asyncio
    async def test_split_alias_restored_across_chunks(self, fake_service):
        model = make_model()
        text = ""
        async for chunk in model.astream([HumanMessage(content="张三呢")]):
            text += chunk.text()
        assert text == "结论：张三完成了实验。"

    @pytest.mark.asyncio
    async def test_stream_input_redacted(self, fake_service):
        model = make_model()
        async for _ in model.astream([HumanMessage(content="张三呢")]):
            pass
        assert RECEIVED[0][0].content == "工程师A呢"

    @pytest.mark.asyncio
    async def test_disabled_stream_passthrough(self, monkeypatch):
        service = FakeService([], enabled=False)
        monkeypatch.setattr(wrapper_module, "redaction_service", service)
        model = make_model()
        text = ""
        async for chunk in model.astream([HumanMessage(content="张三呢")]):
            text += chunk.text()
        assert text == "结论：工程师A完成了实验。"

    @pytest.mark.asyncio
    async def test_tail_flushed_when_alias_split_at_end(self, fake_service):
        model = make_model()

        class TailModel(FakeChatModel):
            async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
                RECEIVED.append([m.model_copy(deep=True) for m in messages])
                for text in ["回复：工程", "师"]:
                    yield ChatGenerationChunk(message=AIMessageChunk(content=text))

        tail_model = maybe_make_redaction_aware(TailModel())
        text = ""
        async for chunk in tail_model.astream([HumanMessage(content="hi")]):
            text += chunk.text()
        # 师 alone is only a prefix, never completed -> literal passthrough
        assert text == "回复：工程师"

    @pytest.mark.asyncio
    async def test_tool_call_chunks_preserved(self, fake_service):
        model = make_model()

        class ToolModel(FakeChatModel):
            async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
                RECEIVED.append([m.model_copy(deep=True) for m in messages])
                yield ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {
                                "name": "search",
                                "args": '{"query": "工程师A实验"}',
                                "id": "call_1",
                                "index": 0,
                            }
                        ],
                    )
                )
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content="工程师A处理中")
                )

        tool_model = maybe_make_redaction_aware(ToolModel())
        chunks = [
            chunk
            async for chunk in tool_model.astream([HumanMessage(content="hi")])
        ]
        # astream yields message chunks (AIMessageChunk), not generations
        assert chunks[0].tool_call_chunks[0]["args"] == '{"query": "工程师A实验"}'
        assert chunks[1].text() == "张三处理中"


# ---------------------------------------------------------------------------
# defensive sync path
# ---------------------------------------------------------------------------
class TestSyncPath:
    def test_sync_generate_redacts_and_restores(self, fake_service):
        model = make_model()
        result = model.invoke([HumanMessage(content="张三做了什么")])
        assert RECEIVED[0][0].content == "工程师A做了什么"
        assert result.content == "张三完成了实验"

    def test_sync_stream_restores(self, fake_service):
        model = make_model()
        text = ""
        for chunk in model.stream([HumanMessage(content="张三呢")]):
            text += chunk.text()
        assert text == "结论：张三完成了实验。"
