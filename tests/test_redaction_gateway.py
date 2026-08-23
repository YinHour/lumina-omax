"""Tests for open_notebook.ai.redaction_gateway."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from open_notebook.ai.redaction_gateway import (
    PHONE_MASK,
    RedactionEngine,
    RedactionService,
    RuleData,
    StreamRestorer,
    next_alias,
)
from open_notebook.domain.redaction import RedactionRule


def make_seed_rules():
    return [
        RuleData("成都欧美克石油科技股份有限公司", "某油田化学企业", "company"),
        RuleData("欧美克", "某企业", "company"),
        RuleData("成都市双流区", "成都某工业园区", "address"),
        RuleData("张三", "工程师A", "person"),
        RuleData("宁218-1井", "实验井A", "well"),
        RuleData("FS-13", "减阻剂A", "product"),
    ]


# ---------------------------------------------------------------------------
# RedactionEngine.redact
# ---------------------------------------------------------------------------
class TestEngineRedact:
    def test_dictionary_replacement(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("由张三负责的实验")
        assert result.text == "由工程师A负责的实验"
        assert result.replacements["张三"]["count"] == 1

    def test_longest_match_first(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("成都欧美克石油科技股份有限公司出品")
        assert result.text == "某油田化学企业出品"
        assert "欧美克" not in result.replacements

    def test_shorter_term_still_matched_when_standalone(self):
        engine = RedactionEngine(make_seed_rules())
        assert engine.redact("欧美克的技术").text == "某企业的技术"

    def test_phone_masked_with_fixed_value(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("联系电话18617778888，备用18617779999")
        assert result.text == f"联系电话{PHONE_MASK}，备用{PHONE_MASK}"
        assert result.replacements["18617778888"]["alias"] == PHONE_MASK

    def test_phone_not_matched_inside_longer_digits(self):
        engine = RedactionEngine([])
        assert engine.redact("编号9186177788887").text == "编号9186177788887"

    def test_known_well_replaced_and_not_re_detected(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("在宁218-1井施工")
        assert result.text == "在实验井A施工"
        assert result.unknown == []

    def test_unknown_well_collected(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("转向威204H2井作业")
        assert result.text == "转向威204H2井作业"
        assert ("well", "威204H2井") in result.unknown

    def test_well_term_normalized_to_single_char_prefix(self):
        # Greedy CJK capture (在威204H2井 / 长宁218-1井) is trimmed to the
        # dictionary convention: single CJK char + number.
        engine = RedactionEngine([])
        result = engine.redact("位于长宁218-1井井场")
        assert ("well", "宁218-1井") in result.unknown

    def test_unknown_product_collected(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("加入GH-20后粘度下降")
        assert ("product", "GH-20") in result.unknown

    def test_single_letter_code_not_detected(self):
        engine = RedactionEngine([])
        result = engine.redact("A-1行数据异常")
        assert result.unknown == []

    def test_alias_terms_not_re_detected(self):
        # An alias that itself matches the product regex must not be
        # re-assigned as a new unknown term.
        rules = [RuleData("某代号", "XX-11", "custom")]
        engine = RedactionEngine(rules)
        result = engine.redact("某代号")
        assert result.text == "XX-11"
        assert result.unknown == []

    def test_multiple_occurrences_counted(self):
        engine = RedactionEngine(make_seed_rules())
        result = engine.redact("张三说；张三又说了")
        assert result.text == "工程师A说；工程师A又说了"
        assert result.replacements["张三"]["count"] == 2

    def test_empty_engine_passthrough(self):
        engine = RedactionEngine([])
        result = engine.redact("普通文本18617778888")
        assert result.text == f"普通文本{PHONE_MASK}"
        assert result.unknown == []

    def test_empty_text(self):
        engine = RedactionEngine(make_seed_rules())
        assert engine.redact("").text == ""


# ---------------------------------------------------------------------------
# RedactionEngine.restore + round trips
# ---------------------------------------------------------------------------
class TestEngineRestore:
    def test_round_trip_dictionary(self):
        engine = RedactionEngine(make_seed_rules())
        original = "成都欧美克石油科技股份有限公司的张三在宁218-1井使用FS-13"
        redacted = engine.redact(original).text
        assert "欧美克" not in redacted
        assert "张三" not in redacted
        assert engine.restore(redacted) == original

    def test_phone_not_restored(self):
        engine = RedactionEngine(make_seed_rules())
        redacted = engine.redact("电话18617778888").text
        assert engine.restore(redacted) == f"电话{PHONE_MASK}"

    def test_restore_no_cascade(self):
        # Rule B's original contains Rule A's alias; single-pass restore must
        # not chain replacements.
        rules = [
            RuleData("甲", "工程师A", "person"),
            RuleData("乙", "备注工程师A乙", "custom"),
        ]
        engine = RedactionEngine(rules)
        text = "工程师A与备注工程师A乙"
        # redact: both aliases present -> restore returns originals
        assert engine.restore(text) == "甲与乙"

    def test_restore_longest_alias_wins(self):
        rules = [
            RuleData("张三", "工程师A", "person"),
            RuleData("李四", "工程师AB", "person"),
        ]
        engine = RedactionEngine(rules)
        assert engine.restore("工程师AB负责") == "李四负责"
        assert engine.restore("工程师A负责") == "张三负责"

    def test_restore_empty_engine(self):
        engine = RedactionEngine([])
        assert engine.restore("工程师A") == "工程师A"


# ---------------------------------------------------------------------------
# next_alias
# ---------------------------------------------------------------------------
class TestNextAlias:
    def test_first_is_a(self):
        assert next_alias("实验井", set()) == "实验井A"

    def test_skips_taken(self):
        assert next_alias("实验井", {"实验井A", "实验井B"}) == "实验井C"

    def test_wraps_to_double_letters(self):
        taken = {f"产品{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
        assert next_alias("产品", taken) == "产品AA"


# ---------------------------------------------------------------------------
# StreamRestorer
# ---------------------------------------------------------------------------
class TestStreamRestorer:
    def _engine(self):
        return RedactionEngine(make_seed_rules())

    def test_complete_alias_single_chunk(self):
        restorer = self._engine().make_stream_restorer()
        out = restorer.push("由工程师A负责") + restorer.flush()
        assert out == "由张三负责"

    def test_alias_split_across_chunks(self):
        restorer = self._engine().make_stream_restorer()
        out = (
            restorer.push("由工程")
            + restorer.push("师A负责")
            + restorer.flush()
        )
        assert out == "由张三负责"

    def test_partial_alias_never_completed_flushes_literal(self):
        # 工程师 alone is never a complete alias -> literal passthrough.
        restorer = self._engine().make_stream_restorer()
        out = restorer.push("这位工程师") + restorer.flush()
        assert out == "这位工程师"

    def test_multiple_aliases_in_stream(self):
        restorer = self._engine().make_stream_restorer()
        out = (
            restorer.push("工程师A与实验井A")
            + restorer.push("均使用减阻剂A")
            + restorer.flush()
        )
        assert out == "张三与宁218-1井均使用FS-13"

    def test_split_at_every_boundary(self):
        text = "工程师A在实验井A使用减阻剂A效果良好"
        engine = self._engine()
        for split in range(1, len(text)):
            restorer = engine.make_stream_restorer()
            out = (
                restorer.push(text[:split])
                + restorer.push(text[split:])
                + restorer.flush()
            )
            assert out == "张三在宁218-1井使用FS-13效果良好", f"split={split}"

    def test_char_by_char_stream(self):
        text = "工程师A与威204H2井"
        rules = make_seed_rules() + [RuleData("威204H2井", "实验井B", "well")]
        restorer = RedactionEngine(rules).make_stream_restorer()
        out = ""
        for ch in text:
            out += restorer.push(ch)
        out += restorer.flush()
        assert out == "张三与威204H2井"  # 实验井B not seeded in base engine

    def test_empty_engine_passthrough(self):
        restorer = RedactionEngine([]).make_stream_restorer()
        out = restorer.push("任意内容") + restorer.flush()
        assert out == "任意内容"

    def test_phone_alias_never_held_or_restored(self):
        restorer = self._engine().make_stream_restorer()
        out = restorer.push("电话888888") + restorer.flush()
        assert out == "电话888888"


# ---------------------------------------------------------------------------
# RedactionService (mocked DB)
# ---------------------------------------------------------------------------
def make_row(original, alias, category, source="manual", enabled=True):
    return RedactionRule(
        original=original, alias=alias, category=category, source=source, enabled=enabled
    )


class TestRedactionService:
    @pytest.fixture
    def service(self):
        return RedactionService()

    @pytest.mark.asyncio
    async def test_disabled_passthrough(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=False)
        )
        messages = [HumanMessage(content="张三的电话18617778888")]
        outcome = await service.redact_messages(messages)
        assert outcome.redacted is False
        assert outcome.messages[0].content == "张三的电话18617778888"

    @pytest.mark.asyncio
    async def test_enabled_redacts_and_keeps_caller_intact(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            RedactionRule,
            "get_all",
            AsyncMock(return_value=[make_row("张三", "工程师A", "person")]),
        )
        original = HumanMessage(content="张三负责该实验")
        outcome = await service.redact_messages([original])
        assert outcome.redacted is True
        assert original.content == "张三负责该实验"  # caller object untouched
        assert outcome.messages[0].content == "工程师A负责该实验"
        assert outcome.engine.restore("工程师A负责") == "张三负责"

    @pytest.mark.asyncio
    async def test_unknown_well_auto_assigned_and_merged(
        self, service, monkeypatch
    ):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        rows = [
            make_row("宁218-1井", "实验井A", "well"),
            make_row("威204H2井", "实验井B", "well"),
        ]
        monkeypatch.setattr(RedactionRule, "get_all", AsyncMock(return_value=rows))
        saved = []

        async def fake_save(self=None):
            saved.append(self)
            return None

        monkeypatch.setattr(RedactionRule, "save", fake_save)
        outcome = await service.redact_messages(
            [HumanMessage(content="在兴305-2井测试")]
        )
        assert outcome.messages[0].content == "在实验井C测试"
        assert len(saved) == 1
        assert saved[0].original == "兴305-2井"
        assert saved[0].alias == "实验井C"
        assert saved[0].source == "auto"
        # merged engine can restore the new alias
        assert outcome.engine.restore("在实验井C测试") == "在兴305-2井测试"

    @pytest.mark.asyncio
    async def test_disabled_rule_term_not_masked(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        rows = [make_row("宁218-1井", "实验井A", "well", enabled=False)]
        monkeypatch.setattr(RedactionRule, "get_all", AsyncMock(return_value=rows))
        outcome = await service.redact_messages(
            [HumanMessage(content="在宁218-1井测试")]
        )
        assert outcome.messages[0].content == "在宁218-1井测试"

    @pytest.mark.asyncio
    async def test_auto_rule_race_reuses_winner(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        seed_rows = [make_row("宁218-1井", "实验井A", "well")]
        race_rows = [
            make_row("宁218-1井", "实验井A", "well"),
            make_row("威204H2井", "实验井B", "well", source="auto"),
        ]
        calls = {"n": 0}

        async def fake_get_all():
            calls["n"] += 1
            return seed_rows if calls["n"] == 1 else race_rows

        monkeypatch.setattr(RedactionRule, "get_all", fake_get_all)

        async def failing_save(self=None):
            raise RuntimeError("unique index violation")

        monkeypatch.setattr(RedactionRule, "save", failing_save)
        outcome = await service.redact_messages(
            [HumanMessage(content="在威204H2井测试")]
        )
        assert outcome.messages[0].content == "在实验井B测试"
        assert outcome.engine.restore("实验井B") == "威204H2井"

    @pytest.mark.asyncio
    async def test_restore_text(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            RedactionRule,
            "get_all",
            AsyncMock(return_value=[make_row("张三", "工程师A", "person")]),
        )
        assert await service.restore_text("工程师A负责") == "张三负责"
        assert await service.restore_text("普通文本") == "普通文本"

    @pytest.mark.asyncio
    async def test_multimodal_text_blocks_redacted(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            RedactionRule,
            "get_all",
            AsyncMock(return_value=[make_row("张三", "工程师A", "person")]),
        )
        message = HumanMessage(
            content=[
                {"type": "text", "text": "张三的记录"},
                {"type": "image_url", "image_url": {"url": "http://x/img.png"}},
            ]
        )
        outcome = await service.redact_messages([message])
        assert outcome.messages[0].content[0]["text"] == "工程师A的记录"
        assert (
            outcome.messages[0].content[1]["image_url"]["url"]
            == "http://x/img.png"
        )

    @pytest.mark.asyncio
    async def test_restore_text_degrades_on_error(self, service, monkeypatch):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )

        async def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(RedactionRule, "get_all", boom)
        assert await service.restore_text("工程师A") == "工程师A"

    @pytest.mark.asyncio
    async def test_system_and_history_messages_redacted(
        self, service, monkeypatch
    ):
        monkeypatch.setattr(
            service, "_settings_enabled", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            RedactionRule,
            "get_all",
            AsyncMock(return_value=[make_row("张三", "工程师A", "person")]),
        )
        messages = [
            SystemMessage(content="背景：张三的历史数据"),
            HumanMessage(content="张三做了什么"),
            AIMessage(content="张三完成了实验"),
        ]
        outcome = await service.redact_messages(messages)
        assert outcome.messages[0].content == "背景：工程师A的历史数据"
        assert outcome.messages[1].content == "工程师A做了什么"
        assert outcome.messages[2].content == "工程师A完成了实验"
