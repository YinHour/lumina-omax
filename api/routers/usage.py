from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.routers.auth import get_current_user_from_state
from open_notebook.database.repository import repo_query

router = APIRouter()


class UsageTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    calls: int
    failed_calls: int


class UsageSeriesPoint(UsageTotals):
    date: str


class UsageCredentialBreakdown(UsageTotals):
    credential_id: Optional[str]
    credential_name: str
    provider: str


class UsageUserBreakdown(UsageTotals):
    user_id: Optional[str]
    username: str


class UsageRecentItem(BaseModel):
    id: str
    user_id: Optional[str]
    username: str
    credential_id: Optional[str]
    credential_name: str
    provider: str
    model_name: str
    surface: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    token_source: str
    status: str
    duration_ms: int
    created: str


class UsageUserOption(BaseModel):
    id: str
    username: str
    display_name: str


class UsageDashboardResponse(BaseModel):
    scope: Literal["mine", "all"]
    days: int
    selected_user_id: Optional[str]
    totals: UsageTotals
    series: list[UsageSeriesPoint]
    by_credential: list[UsageCredentialBreakdown]
    by_user: list[UsageUserBreakdown]
    recent: list[UsageRecentItem]
    users: list[UsageUserOption]


def _empty_totals() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "calls": 0,
        "failed_calls": 0,
    }


def _add_row(totals: dict[str, int], row: dict) -> None:
    totals["input_tokens"] += int(row.get("input_tokens") or 0)
    totals["output_tokens"] += int(row.get("output_tokens") or 0)
    totals["total_tokens"] += int(row.get("total_tokens") or 0)
    totals["calls"] += 1
    if row.get("status") == "failed":
        totals["failed_calls"] += 1


def _row_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


@router.get("/usage", response_model=UsageDashboardResponse)
async def get_usage_dashboard(
    days: int = Query(30),
    scope: Literal["mine", "all"] = Query("mine"),
    user_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_from_state),
):
    if days not in {7, 30, 90}:
        raise HTTPException(status_code=422, detail="Days must be 7, 30, or 90")

    is_admin = current_user.get("role") == "admin"
    if scope == "all" and not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    if user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    selected_user_id = (
        user_id
        if scope == "all"
        else str(current_user.get("id"))
    )
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(
        today - timedelta(days=days - 1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    query = """
        SELECT id, user_id, username, credential_id, credential_name, provider,
               model_name, surface, input_tokens, output_tokens, total_tokens,
               token_source, status, duration_ms, created
        FROM ai_token_usage
        WHERE created >= $start
    """
    params: dict = {"start": start}
    if selected_user_id:
        query += " AND user_id = $user_id"
        params["user_id"] = selected_user_id
    query += " ORDER BY created DESC"
    rows = await repo_query(query, params)

    totals = _empty_totals()
    daily = {
        today - timedelta(days=offset): _empty_totals()
        for offset in range(days)
    }
    credential_totals: dict[tuple[Optional[str], str, str], dict[str, int]] = defaultdict(_empty_totals)
    user_totals: dict[tuple[Optional[str], str], dict[str, int]] = defaultdict(_empty_totals)

    for row in rows:
        _add_row(totals, row)
        row_day = _row_date(row.get("created"))
        if row_day in daily:
            _add_row(daily[row_day], row)
        credential_key = (
            str(row["credential_id"]) if row.get("credential_id") else None,
            str(row.get("credential_name") or "Environment"),
            str(row.get("provider") or "unknown"),
        )
        _add_row(credential_totals[credential_key], row)
        user_key = (
            str(row["user_id"]) if row.get("user_id") else None,
            str(row.get("username") or "system"),
        )
        _add_row(user_totals[user_key], row)

    series = [
        UsageSeriesPoint(date=day.isoformat(), **daily[day])
        for day in sorted(daily)
    ]
    by_credential = sorted(
        (
            UsageCredentialBreakdown(
                credential_id=key[0],
                credential_name=key[1],
                provider=key[2],
                **value,
            )
            for key, value in credential_totals.items()
        ),
        key=lambda item: item.total_tokens,
        reverse=True,
    )
    by_user = sorted(
        (
            UsageUserBreakdown(user_id=key[0], username=key[1], **value)
            for key, value in user_totals.items()
        ),
        key=lambda item: item.total_tokens,
        reverse=True,
    ) if is_admin and scope == "all" else []

    users = []
    if is_admin:
        user_rows = await repo_query(
            "SELECT id, username, display_name FROM user ORDER BY display_name ASC"
        )
        users = [
            UsageUserOption(
                id=str(row["id"]),
                username=str(row.get("username") or ""),
                display_name=str(row.get("display_name") or row.get("username") or ""),
            )
            for row in user_rows
        ]

    recent = [
        UsageRecentItem(
            id=str(row.get("id") or ""),
            user_id=str(row["user_id"]) if row.get("user_id") else None,
            username=str(row.get("username") or "system"),
            credential_id=(
                str(row["credential_id"]) if row.get("credential_id") else None
            ),
            credential_name=str(row.get("credential_name") or "Environment"),
            provider=str(row.get("provider") or "unknown"),
            model_name=str(row.get("model_name") or "unknown"),
            surface=str(row.get("surface") or "unknown"),
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            total_tokens=int(row.get("total_tokens") or 0),
            token_source=str(row.get("token_source") or "estimated"),
            status=str(row.get("status") or "success"),
            duration_ms=int(row.get("duration_ms") or 0),
            created=str(row.get("created") or ""),
        )
        for row in rows[:50]
    ]

    return UsageDashboardResponse(
        scope=scope,
        days=days,
        selected_user_id=selected_user_id,
        totals=UsageTotals(**totals),
        series=series,
        by_credential=by_credential,
        by_user=by_user,
        recent=recent,
        users=users,
    )
