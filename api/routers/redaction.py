"""Admin CRUD for the egress-redaction dictionary (出网脱敏词典).

The dictionary maps sensitive original terms to stable aliases used by the
redact-on-egress / restore-on-ingress gateway. Viewing requires admin: the
records themselves contain the sensitive originals the gateway protects.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.models import (
    RedactionRuleCreate,
    RedactionRuleResponse,
    RedactionRuleUpdate,
)
from api.routers.auth import require_admin
from open_notebook.ai.redaction_gateway import invalidate_redaction_cache
from open_notebook.domain.redaction import CATEGORIES, RedactionRule

router = APIRouter()


def _to_response(rule: RedactionRule) -> RedactionRuleResponse:
    return RedactionRuleResponse(
        id=str(rule.id),
        original=rule.original,
        alias=rule.alias,
        category=rule.category,
        enabled=rule.enabled,
        source=rule.source,
        note=rule.note,
    )


async def _find_rule(rule_id: str) -> RedactionRule:
    full_id = rule_id if rule_id.startswith("redaction_rule:") else f"redaction_rule:{rule_id}"
    rule = await RedactionRule.get(full_id)
    if rule is None or not isinstance(rule, RedactionRule):
        raise HTTPException(status_code=404, detail="Redaction rule not found")
    return rule


@router.get("/redaction/rules", response_model=list[RedactionRuleResponse])
async def list_rules(admin_user: dict = Depends(require_admin)):
    """List all dictionary entries (admin only)."""
    try:
        rules = await RedactionRule.get_all()
        return [_to_response(rule) for rule in rules]
    except Exception as e:
        logger.error(f"Error listing redaction rules: {e}")
        raise HTTPException(status_code=500, detail="Error listing redaction rules")


@router.post("/redaction/rules", response_model=RedactionRuleResponse)
async def create_rule(
    payload: RedactionRuleCreate, admin_user: dict = Depends(require_admin)
):
    """Add a dictionary entry (admin only)."""
    try:
        existing = await RedactionRule.get_all()
        for row in existing:
            if row.original == payload.original.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"Rule for '{payload.original}' already exists",
                )
            if row.alias == payload.alias.strip():
                logger.warning(
                    "Redaction alias '{}' is already used by '{}'",
                    payload.alias,
                    row.original,
                )
        rule = RedactionRule(
            original=payload.original.strip(),
            alias=payload.alias.strip(),
            category=payload.category,
            source="manual",
            enabled=True,
            note=payload.note,
        )
        await rule.save()
        invalidate_redaction_cache()
        return _to_response(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating redaction rule: {e}")
        raise HTTPException(status_code=500, detail="Error creating redaction rule")


@router.put("/redaction/rules/{rule_id}", response_model=RedactionRuleResponse)
async def update_rule(
    rule_id: str,
    payload: RedactionRuleUpdate,
    admin_user: dict = Depends(require_admin),
):
    """Update a dictionary entry (admin only; original term is immutable)."""
    try:
        rule = await _find_rule(rule_id)
        if payload.alias is not None:
            rule.alias = payload.alias.strip()
        if payload.category is not None:
            if payload.category not in CATEGORIES:
                raise HTTPException(status_code=400, detail="Invalid category")
            rule.category = payload.category
        if payload.enabled is not None:
            rule.enabled = payload.enabled
        if payload.note is not None:
            rule.note = payload.note
        await rule.save()
        invalidate_redaction_cache()
        return _to_response(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating redaction rule: {e}")
        raise HTTPException(status_code=500, detail="Error updating redaction rule")


@router.delete("/redaction/rules/{rule_id}")
async def delete_rule(rule_id: str, admin_user: dict = Depends(require_admin)):
    """Delete a dictionary entry (admin only)."""
    try:
        rule = await _find_rule(rule_id)
        await rule.delete()
        invalidate_redaction_cache()
        return {"deleted": True, "id": str(rule.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting redaction rule: {e}")
        raise HTTPException(status_code=500, detail="Error deleting redaction rule")
