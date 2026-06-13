"""Notebook guide and suggested-question generation helpers."""

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from api.models import NotebookGuideResponse
from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import (
    ensure_record_id,
    repo_create,
    repo_query,
    repo_update,
)
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.text_utils import extract_text_content

MAX_GUIDE_SOURCE_CHARS = 4000
MAX_FOLLOWUP_CONTEXT_CHARS = 6000


async def get_processed_notebook_sources(notebook_id: str) -> list[dict[str, Any]]:
    """Return processed sources linked to a notebook."""
    records = await repo_query(
        """
        SELECT in as source
        FROM reference
        WHERE out = $notebook_id
        FETCH source
        """,
        {"notebook_id": ensure_record_id(notebook_id)},
    )
    sources: list[dict[str, Any]] = []
    for record in records or []:
        source = record.get("source")
        if isinstance(source, list):
            source = source[0] if source else None
        if not isinstance(source, dict):
            continue
        full_text = source.get("full_text")
        if isinstance(full_text, str) and full_text.strip():
            sources.append(source)
    return sources


def build_source_fingerprint(sources: list[dict[str, Any]]) -> str:
    """Build a stable fingerprint for guide cache invalidation."""
    parts = []
    for source in sorted(sources, key=lambda item: str(item.get("id", ""))):
        parts.append(f"{source.get('id')}|{source.get('updated')}|{len(source.get('full_text') or '')}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def parse_guide_json(raw_text: str) -> tuple[Optional[str], list[str]]:
    """Parse model JSON output into summary and exactly up to three questions."""
    if not raw_text:
        return None, []

    cleaned = clean_thinking_content(extract_text_content(raw_text)).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse notebook guide JSON")
        return None, []

    summary = data.get("summary")
    questions = data.get("questions", [])
    if not isinstance(summary, str) or not summary.strip():
        summary = None
    if not isinstance(questions, list):
        questions = []

    normalized_questions = [
        question.strip()
        for question in questions
        if isinstance(question, str) and question.strip()
    ][:3]
    return summary.strip() if summary else None, normalized_questions


def _build_guide_prompt(sources: list[dict[str, Any]], language: str) -> str:
    source_blocks = []
    per_source_budget = max(800, MAX_GUIDE_SOURCE_CHARS // max(len(sources), 1))
    for index, source in enumerate(sources, start=1):
        title = source.get("title") or f"Source {index}"
        full_text = str(source.get("full_text") or "")[:per_source_budget]
        source_blocks.append(f"### Source {index}: {title}\n{full_text}")

    output_language = "简体中文" if language.lower().startswith("zh") else "English"
    return f"""
You are helping create a NotebookLM-style guide for a research notebook.
Return strict JSON only, with keys "summary" and "questions".
Write in {output_language}.

Requirements:
- summary: concise, source-aware, 120-220 Chinese characters if writing Chinese
- questions: exactly 3 actionable next-step questions
- questions must help the user continue research, compare mechanisms, inspect risks, or plan validation
- do not include citations, markdown, comments, or extra keys

Sources:
{chr(10).join(source_blocks)}
""".strip()


async def _invoke_json_model(prompt: str, model_override: Optional[str] = None) -> str:
    model = await provision_langchain_model(
        prompt,
        model_override,
        "chat",
        max_tokens=768,
        temperature=0,
        streaming=False,
    )
    if model is None:
        return ""
    response = await model.ainvoke(
        [
            SystemMessage(content="Return strict JSON only."),
            HumanMessage(content=prompt),
        ]
    )
    return extract_text_content(getattr(response, "content", response))


async def _get_cached_guide(notebook_id: str, language: str) -> Optional[dict[str, Any]]:
    records = await repo_query(
        """
        SELECT *
        FROM notebook_guide
        WHERE notebook_id = $notebook_id AND language = $language
        LIMIT 1
        """,
        {"notebook_id": notebook_id, "language": language},
    )
    return records[0] if records else None


async def generate_notebook_guide(
    notebook_id: str,
    language: str = "zh-CN",
    force: bool = False,
) -> NotebookGuideResponse:
    """Generate or return a cached notebook guide."""
    sources = await get_processed_notebook_sources(notebook_id)
    if not sources:
        return NotebookGuideResponse(
            notebook_id=notebook_id,
            source_count=0,
            generated_at=None,
            summary=None,
            questions=[],
            status="empty",
        )

    fingerprint = build_source_fingerprint(sources)
    cached = await _get_cached_guide(notebook_id, language)
    if (
        cached
        and not force
        and cached.get("source_fingerprint") == fingerprint
        and cached.get("summary")
        and len(cached.get("questions") or []) == 3
    ):
        return NotebookGuideResponse(
            notebook_id=notebook_id,
            source_count=int(cached.get("source_count") or len(sources)),
            generated_at=str(cached.get("updated") or cached.get("created") or ""),
            summary=cached.get("summary"),
            questions=list(cached.get("questions") or [])[:3],
            status="ready",
        )

    try:
        raw = await _invoke_json_model(_build_guide_prompt(sources, language))
        summary, questions = parse_guide_json(raw)
    except Exception as exc:
        logger.warning(f"Notebook guide generation failed for {notebook_id}: {exc}")
        return NotebookGuideResponse(
            notebook_id=notebook_id,
            source_count=len(sources),
            generated_at=None,
            summary=None,
            questions=[],
            status="error",
        )

    if not summary or len(questions) < 3:
        return NotebookGuideResponse(
            notebook_id=notebook_id,
            source_count=len(sources),
            generated_at=None,
            summary=None,
            questions=[],
            status="error",
        )

    data = {
        "notebook_id": notebook_id,
        "source_fingerprint": fingerprint,
        "source_count": len(sources),
        "summary": summary,
        "questions": questions[:3],
        "language": language,
    }
    if cached and cached.get("id"):
        await repo_update("notebook_guide", str(cached["id"]), data)
    else:
        await repo_create("notebook_guide", data)

    generated_at = datetime.now(timezone.utc).isoformat()
    return NotebookGuideResponse(
        notebook_id=notebook_id,
        source_count=len(sources),
        generated_at=generated_at,
        summary=summary,
        questions=questions[:3],
        status="ready",
    )


def _build_followup_prompt(answer: str, context: dict[str, Any], language: str) -> str:
    context_text = json.dumps(context, ensure_ascii=False, default=str)
    context_text = context_text[:MAX_FOLLOWUP_CONTEXT_CHARS]
    output_language = "简体中文" if language.lower().startswith("zh") else "English"
    return f"""
Based on the assistant answer and notebook context, suggest exactly 3 useful follow-up questions.
Return strict JSON only with key "questions".
Write in {output_language}.
The questions should be specific and actionable, not generic.

Assistant answer:
{answer[-4000:]}

Notebook context:
{context_text}
""".strip()


async def generate_followup_questions(
    answer: str,
    context: dict[str, Any],
    language: str = "zh-CN",
    model_override: Optional[str] = None,
) -> list[str]:
    """Generate three follow-up questions for a completed AI answer."""
    if not answer.strip():
        return []
    try:
        raw = await _invoke_json_model(
            _build_followup_prompt(answer, context, language),
            model_override=model_override,
        )
        _, questions = parse_guide_json(raw)
        return questions[:3] if len(questions) == 3 else []
    except Exception as exc:
        logger.warning(f"Follow-up question generation failed: {exc}")
        return []
