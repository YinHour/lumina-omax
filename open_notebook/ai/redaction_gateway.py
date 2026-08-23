"""
Egress redaction gateway (出网脱敏透明网关).

Trust model
-----------
Data at rest (SurrealDB records, uploaded files) is trusted and keeps its
original form. The gateway only intercepts the boundary where prompts leave
the deployment for external LLM providers:

- outbound (egress): sensitive commercial identifiers are replaced with
  stable aliases before the request reaches the provider;
- inbound (ingress): aliases in model responses are restored back to the
  original terms before anything is stored or streamed to the user.

The alias dictionary is the global ``redaction_rule`` table. Admin-curated
entries are exact-match; phone numbers, well names and product codes are
additionally detected by built-in regex patterns, and first-seen terms are
assigned a stable alias that is persisted automatically (never reassigned).

Failure semantics
-----------------
- Egress redaction is fail-closed: when the gateway is enabled, an
  unexpected error aborts the LLM call instead of leaking silently.
- Inbound restore degrades gracefully: on error the alias text passes
  through, which is confusing but never a leak.
"""

import itertools
import re
from dataclasses import dataclass, field
from string import ascii_uppercase
from time import monotonic
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.messages import BaseMessage
from loguru import logger

from open_notebook.domain.redaction import (
    CATEGORY_PHONE,
    CATEGORY_PRODUCT,
    CATEGORY_WELL,
    RedactionRule,
)

PHONE_MASK = "888888"

# 11-digit mainland Chinese mobile numbers, not embedded in longer numbers.
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

# Well identifiers like 宁218-1井 / 威204H2井: 1-4 CJK chars, digits, optional
# branch/horizontal suffix, terminated by 井.
WELL_RE = re.compile(r"[\u4e00-\u9fa5]{1,4}\d{1,4}(?:-\d{1,4})?(?:[A-Z]\d{0,3})?井")

# Product codes like FS-13: 2-6 uppercase letters, dash, 1-4 digits. Single
# letter prefixes (A-1 table row labels) are deliberately excluded.
PRODUCT_RE = re.compile(r"(?<![A-Za-z0-9-])[A-Z]{2,6}-\d{1,4}(?![0-9])")

AUTO_PATTERNS: Dict[str, re.Pattern] = {
    CATEGORY_WELL: WELL_RE,
    CATEGORY_PRODUCT: PRODUCT_RE,
}

AUTO_ALIAS_BASES: Dict[str, str] = {
    CATEGORY_WELL: "实验井",
    CATEGORY_PRODUCT: "产品",
}


def _normalize_well_term(term: str) -> str:
    """Trim a regex-captured well term to its last CJK prefix character.

    The greedy well regex may swallow preceding verbs (在/于/转…), e.g.
    ``在威204H2井``. Well names in the rules doc convention are a single
    CJK char + number (宁218-1井, 威204H2井), so trimming to the last prefix
    character yields a deterministic, dictionary-compatible term regardless
    of what precedes the well name in the sentence.
    """
    match = re.match(r"^([\u4e00-\u9fa5]+)(\d.*)$", term)
    if match and len(match.group(1)) > 1:
        return match.group(1)[-1] + match.group(2)
    return term


@dataclass(frozen=True)
class RuleData:
    """Immutable view of a dictionary entry used by the engine."""

    original: str
    alias: str
    category: str
    source: str = "manual"

    @property
    def restore(self) -> bool:
        # Phone numbers use a shared fixed mask and are intentionally not
        # reversible: answers legitimately show 888888.
        return self.category != CATEGORY_PHONE


@dataclass
class RedactionResult:
    """Outcome of a single redact() pass."""

    text: str
    replacements: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # (category, term) pairs detected by regex that have no alias yet.
    unknown: List[Tuple[str, str]] = field(default_factory=list)


def _simultaneous_replacer(
    pairs: Sequence[Tuple[str, str]],
) -> Callable[[str], Tuple[str, Dict[str, int]]]:
    """Build a single-pass replacer over find->replace pairs.

    All matches are replaced simultaneously in one regex pass, so
    replacements never cascade into each other. Longer originals are listed
    first in the alternation and therefore win at the same position.
    """
    valid = [(f, r) for f, r in pairs if f]
    if not valid:
        return lambda text: (text, {})
    ordered = sorted(valid, key=lambda p: len(p[0]), reverse=True)
    pattern = re.compile("|".join(re.escape(f) for f, _ in ordered))
    mapping = dict(valid)

    def _replace(text: str) -> Tuple[str, Dict[str, int]]:
        if not text:
            return text, {}
        stats: Dict[str, int] = {}

        def _sub(match: "re.Match[str]") -> str:
            found = match.group(0)
            stats[found] = stats.get(found, 0) + 1
            return mapping[found]

        return pattern.sub(_sub, text), stats

    return _replace


def _bijective_letters() -> str:
    """Yield A, B, ..., Z, AA, AB, ..."""
    n = 1
    while True:
        for combo in itertools.product(ascii_uppercase, repeat=n):
            yield "".join(combo)
        n += 1


def next_alias(base: str, taken: set) -> str:
    """Return the first ``base + suffix`` not already in ``taken``."""
    for suffix in _bijective_letters():
        candidate = f"{base}{suffix}"
        if candidate not in taken:
            return candidate
    raise RuntimeError("unreachable")


class RedactionEngine:
    """Pure synchronous redact/restore engine over a rule set."""

    def __init__(self, rules: Sequence[RuleData]):
        enabled_rules = [r for r in rules if r.original and r.alias]
        self.source_rules: List[RuleData] = enabled_rules
        self._originals = {r.original for r in enabled_rules}
        self._aliases = {r.alias for r in enabled_rules}
        self._alias_by_original = {r.original: r.alias for r in enabled_rules}
        self._replace = _simultaneous_replacer(
            [(r.original, r.alias) for r in enabled_rules]
        )
        self._restore = _simultaneous_replacer(
            [(r.alias, r.original) for r in enabled_rules if r.restore]
        )
        restore_aliases = [r.alias for r in enabled_rules if r.restore]
        self._max_alias_len = max((len(a) for a in restore_aliases), default=0)
        self._alias_prefixes = {
            a[:i] for a in restore_aliases for i in range(1, len(a))
        }
        self._restore_active = bool(restore_aliases)

    def redact(self, text: str) -> RedactionResult:
        """Replace known dictionary terms, mask phones, collect unknowns."""
        if not text:
            return RedactionResult(text=text)
        out, dict_stats = self._replace(text)

        phone_stats: Dict[str, int] = {}

        def _phone_sub(match: "re.Match[str]") -> str:
            found = match.group(0)
            phone_stats[found] = phone_stats.get(found, 0) + 1
            return PHONE_MASK

        out = PHONE_RE.sub(_phone_sub, out)

        replacements: Dict[str, Dict[str, Any]] = {}
        for original, count in dict_stats.items():
            replacements[original] = {
                "alias": self._alias_by_original.get(original, original),
                "count": count,
            }
        for original, count in phone_stats.items():
            replacements[original] = {"alias": PHONE_MASK, "count": count}

        unknown: List[Tuple[str, str]] = []
        seen_terms = set()
        for category, pattern in AUTO_PATTERNS.items():
            for match in pattern.finditer(out):
                term = match.group(0)
                if category == CATEGORY_WELL:
                    term = _normalize_well_term(term)
                if not term:
                    continue
                if term in self._originals or term in self._aliases:
                    continue
                if term in seen_terms:
                    continue
                seen_terms.add(term)
                unknown.append((category, term))

        return RedactionResult(text=out, replacements=replacements, unknown=unknown)

    def replacer_for(
        self, rules: Sequence[RuleData]
    ) -> Callable[[str], Tuple[str, Dict[str, int]]]:
        """Build a single-pass replacer for extra (newly assigned) rules."""
        return _simultaneous_replacer([(r.original, r.alias) for r in rules])

    def restore(self, text: str) -> str:
        """Replace aliases back to original terms (single pass, no cascade)."""
        if not text or not self._restore_active:
            return text
        out, _ = self._restore(text)
        return out

    def make_stream_restorer(self) -> "StreamRestorer":
        return StreamRestorer(self)


class StreamRestorer:
    """Cross-chunk buffering restorer for token streams.

    SSE streams deliver tokens in arbitrary split points, so an alias such as
    工程师A can arrive as 工程师 + A. The restorer holds back any trailing
    suffix that is a proper prefix of a known alias and completes it when the
    next chunk arrives; flush() emits whatever is left at stream end.
    """

    def __init__(self, engine: RedactionEngine):
        self._engine = engine
        self._buffer = ""

    def push(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buffer += chunk
        if not self._engine._restore_active:
            out, self._buffer = self._buffer, ""
            return out
        hold = 0
        max_hold = min(self._engine._max_alias_len - 1, len(self._buffer))
        for hold_len in range(max_hold, 0, -1):
            if self._buffer[-hold_len:] in self._engine._alias_prefixes:
                hold = hold_len
                break
        emit = self._buffer[: len(self._buffer) - hold]
        self._buffer = self._buffer[len(self._buffer) - hold :]
        if not emit:
            return ""
        return self._engine.restore(emit)

    def flush(self) -> str:
        out = self._engine.restore(self._buffer)
        self._buffer = ""
        return out


@dataclass
class EgressOutcome:
    """Result of redacting a batch of messages for egress."""

    messages: List[BaseMessage]
    engine: RedactionEngine
    replacements: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    redacted: bool = False


def _apply_to_message_text(message: BaseMessage, fn: Callable[[str], str]) -> None:
    """Apply fn over the text parts of a message content, in place."""
    content = message.content
    if isinstance(content, str):
        message.content = fn(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = fn(str(block.get("text") or ""))


class RedactionService:
    """Async DB-backed facade for the egress redaction gateway."""

    STATE_TTL_SECONDS = 30.0

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {
            "engine": None,
            "rules": None,  # all RuleData rows (enabled + disabled)
            "ts": 0.0,
        }
        self._enabled_cache: Dict[str, Any] = {"value": None, "ts": 0.0}

    # ------------------------------------------------------------------
    # state / settings
    # ------------------------------------------------------------------
    async def _settings_enabled(self) -> bool:
        from open_notebook.domain.content_settings import ContentSettings

        ContentSettings.clear_instance()  # force reload from DB
        settings = await ContentSettings.get_instance()
        return bool(getattr(settings, "redaction_enabled", False))

    async def is_enabled(self) -> bool:
        now = monotonic()
        cached = self._enabled_cache
        if cached["value"] is not None and now - cached["ts"] < self.STATE_TTL_SECONDS:
            return bool(cached["value"])
        try:
            value = await self._settings_enabled()
        except Exception as e:
            # Toggle read failure: proceed unredacted but log loudly. In
            # practice the graph has already read the DB successfully by the
            # time a model is invoked, so this window is transient.
            logger.error("Redaction enabled-check failed, treating as disabled: {}", e)
            value = False
        self._enabled_cache = {"value": value, "ts": now}
        return value

    async def _load_state(self) -> Dict[str, Any]:
        now = monotonic()
        if (
            self._state["engine"] is not None
            and now - self._state["ts"] < self.STATE_TTL_SECONDS
        ):
            return self._state
        rows = await RedactionRule.get_all()
        rules = [
            RuleData(
                original=row.original,
                alias=row.alias,
                category=row.category,
                source=row.source,
            )
            for row in rows
        ]
        enabled_rules = [
            rule
            for rule, row in zip(rules, rows)
            if row.enabled and rule.original and rule.alias
        ]
        self._check_alias_collisions(enabled_rules)
        engine = RedactionEngine(enabled_rules)
        self._state = {"engine": engine, "rules": rules, "ts": now}
        return self._state

    @staticmethod
    def _check_alias_collisions(rules: Sequence[RuleData]) -> None:
        seen: Dict[str, str] = {}
        for rule in rules:
            if rule.alias in seen and seen[rule.alias] != rule.original:
                logger.warning(
                    "Redaction alias collision: '{}' maps to both '{}' and '{}'; "
                    "rename one entry in the dictionary",
                    rule.alias,
                    seen[rule.alias],
                    rule.original,
                )
            seen[rule.alias] = rule.original

    def invalidate_cache(self) -> None:
        self._state = {"engine": None, "rules": None, "ts": 0.0}
        self._enabled_cache = {"value": None, "ts": 0.0}

    def get_cached_engine(self) -> Optional[RedactionEngine]:
        engine = self._state.get("engine")
        if engine is not None and monotonic() - self._state.get("ts", 0.0) < self.STATE_TTL_SECONDS:
            return engine
        return None

    # ------------------------------------------------------------------
    # egress / ingress
    # ------------------------------------------------------------------
    async def redact_messages(
        self, messages: Sequence[BaseMessage]
    ) -> EgressOutcome:
        """Redact message contents for egress.

        Returns deep copies of the messages (callers' objects are never
        mutated), plus a merged engine snapshot that must be used to restore
        the model response (it includes aliases assigned during this call).
        Fail-closed: unexpected errors propagate and abort the LLM call.
        """
        if not await self.is_enabled():
            return EgressOutcome(
                messages=list(messages),
                engine=RedactionEngine([]),
                redacted=False,
            )

        state = await self._load_state()
        engine: RedactionEngine = state["engine"]
        all_rules: List[RuleData] = state["rules"]

        copies = [message.model_copy(deep=True) for message in messages]

        # Pass 1: dictionary terms + phone masks; collect regex unknowns.
        first_pass: List[RedactionResult] = []

        def _redact_one(text: str) -> str:
            result = engine.redact(text)
            first_pass.append(result)
            return result.text

        for message in copies:
            _apply_to_message_text(message, _redact_one)

        unknown: List[Tuple[str, str]] = []
        for result in first_pass:
            for pair in result.unknown:
                if pair not in unknown:
                    unknown.append(pair)

        # Resolve unknowns: skip terms that exist in any rule (disabled
        # entries mean the admin deliberately keeps them unmasked).
        existing_by_original = {rule.original: rule for rule in all_rules}
        taken_aliases = {rule.alias for rule in all_rules}
        new_rules: List[RuleData] = []
        for category, term in unknown:
            if term in existing_by_original:
                continue
            base = AUTO_ALIAS_BASES.get(category)
            if not base:
                continue
            alias = next_alias(base, taken_aliases)
            rule = RuleData(original=term, alias=alias, category=category, source="auto")
            persisted = await self._persist_auto_rule(rule)
            if persisted is None:
                continue
            new_rules.append(persisted)
            existing_by_original[persisted.original] = persisted
            taken_aliases.add(persisted.alias)

        # Pass 2: apply newly assigned aliases.
        new_rule_stats: Dict[str, int] = {}
        if new_rules:
            replacer = engine.replacer_for(new_rules)

            def _apply_new(text: str) -> str:
                out, stats = replacer(text)
                for original, count in stats.items():
                    new_rule_stats[original] = (
                        new_rule_stats.get(original, 0) + count
                    )
                return out

            for message in copies:
                _apply_to_message_text(message, _apply_new)

        merged_engine = RedactionEngine(list(engine.source_rules) + new_rules)

        replacements: Dict[str, Dict[str, Any]] = {}
        for result in first_pass:
            for original, info in result.replacements.items():
                if original in replacements:
                    replacements[original]["count"] += info["count"]
                else:
                    replacements[original] = dict(info)
        alias_by_new_original = {r.original: r.alias for r in new_rules}
        for original, count in new_rule_stats.items():
            replacements[original] = {
                "alias": alias_by_new_original.get(original, original),
                "count": count,
            }

        if replacements or new_rules:
            total = sum(info["count"] for info in replacements.values())
            logger.info(
                "Egress redaction: {} entities, {} replacements, {} new auto-aliases",
                len(replacements),
                total,
                len(new_rules),
            )
            logger.debug("Egress redaction detail: {}", replacements)

        return EgressOutcome(
            messages=copies,
            engine=merged_engine,
            replacements=replacements,
            redacted=True,
        )

    async def restore_text(self, text: str) -> str:
        """Restore aliases to originals for a plain string (embedding hook).

        Degrades gracefully: on error the text passes through unchanged.
        """
        if not text or not await self.is_enabled():
            return text
        try:
            state = await self._load_state()
            return state["engine"].restore(text)
        except Exception as e:
            logger.error("Redaction restore_text failed, passing through: {}", e)
            return text

    async def _persist_auto_rule(self, rule: RuleData) -> Optional[RuleData]:
        """Persist an auto-assigned rule; returns None if the term exists but
        is disabled (admin intent: keep unmasked)."""
        try:
            record = RedactionRule(
                original=rule.original,
                alias=rule.alias,
                category=rule.category,
                source="auto",
                enabled=True,
            )
            await record.save()
            self.invalidate_cache()
            return rule
        except Exception as e:
            # Possible unique-index race: another process persisted this
            # original first. Re-query and honour the winner.
            try:
                existing = await self._find_row_by_original(rule.original)
            except Exception:
                logger.error(
                    "Redaction auto-rule persist failed and re-query failed: {}", e
                )
                raise
            if existing is None:
                logger.error("Redaction auto-rule persist failed: {}", e)
                raise
            if not existing.enabled:
                return None
            return RuleData(
                original=existing.original,
                alias=existing.alias,
                category=existing.category,
                source=existing.source,
            )

    async def _find_row_by_original(self, original: str) -> Optional[RedactionRule]:
        rows = await RedactionRule.get_all()
        for row in rows:
            if row.original == original:
                return row
        return None


redaction_service = RedactionService()


def invalidate_redaction_cache() -> None:
    """Invalidate caches after dictionary edits (admin CRUD)."""
    redaction_service.invalidate_cache()
