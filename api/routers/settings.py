from fastapi import APIRouter, HTTPException
from loguru import logger

from api.models import SettingsResponse, SettingsUpdate
from open_notebook.domain.content_settings import ContentSettings
from open_notebook.exceptions import InvalidInputError

router = APIRouter()

# Masked sentinel returned by GET /settings for non-empty secret fields. The raw
# value is never sent to the browser (parity with the credentials router, which
# never returns api_key). The frontend must omit a field when its value still
# equals this sentinel so PUT does not overwrite the stored secret with it.
MASKED_SECRET = "*" * 20


def _mask_secret(value: str | None) -> str:
    """Return the masked sentinel when a secret is configured, empty otherwise."""
    return MASKED_SECRET if value else ""


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get all application settings."""
    try:
        settings: ContentSettings = await ContentSettings.get_instance()  # type: ignore[assignment]

        return SettingsResponse(
            default_content_processing_engine_doc=settings.default_content_processing_engine_doc,
            default_content_processing_engine_url=settings.default_content_processing_engine_url,
            default_embedding_option=settings.default_embedding_option,
            auto_delete_files=settings.auto_delete_files,
            source_batch_limit=settings.source_batch_limit,
            youtube_preferred_languages=settings.youtube_preferred_languages,
            # Secrets are masked; never echo raw keys back to the browser.
            tavily_api_key=_mask_secret(settings.tavily_api_key),
            tavily_include_domains=settings.tavily_include_domains,
            firecrawl_api_key=_mask_secret(settings.firecrawl_api_key),
            redaction_enabled=bool(settings.redaction_enabled),
        )
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error fetching settings"
        )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdate):
    """Update application settings."""
    try:
        settings: ContentSettings = await ContentSettings.get_instance()  # type: ignore[assignment]

        # Update only provided fields
        if settings_update.default_content_processing_engine_doc is not None:
            # Cast to proper literal type
            from typing import Literal, cast

            settings.default_content_processing_engine_doc = cast(
                Literal["auto", "docling", "mineru", "simple"],
                settings_update.default_content_processing_engine_doc,
            )
        if settings_update.default_content_processing_engine_url is not None:
            from typing import Literal, cast

            settings.default_content_processing_engine_url = cast(
                Literal["auto", "firecrawl", "jina", "simple"],
                settings_update.default_content_processing_engine_url,
            )
        if settings_update.default_embedding_option is not None:
            from typing import Literal, cast

            settings.default_embedding_option = cast(
                Literal["ask", "always", "never"],
                settings_update.default_embedding_option,
            )
        if settings_update.auto_delete_files is not None:
            from typing import Literal, cast

            settings.auto_delete_files = cast(
                Literal["yes", "no"], settings_update.auto_delete_files
            )
        if settings_update.source_batch_limit is not None:
            settings.source_batch_limit = settings_update.source_batch_limit
        if settings_update.youtube_preferred_languages is not None:
            settings.youtube_preferred_languages = (
                settings_update.youtube_preferred_languages
            )
        if settings_update.tavily_api_key is not None and settings_update.tavily_api_key != MASKED_SECRET:
            settings.tavily_api_key = settings_update.tavily_api_key
        if settings_update.tavily_include_domains is not None:
            settings.tavily_include_domains = settings_update.tavily_include_domains
        if settings_update.firecrawl_api_key is not None and settings_update.firecrawl_api_key != MASKED_SECRET:
            settings.firecrawl_api_key = settings_update.firecrawl_api_key
        if settings_update.redaction_enabled is not None:
            settings.redaction_enabled = settings_update.redaction_enabled
            from open_notebook.ai.redaction_gateway import invalidate_redaction_cache

            invalidate_redaction_cache()

        await settings.update()

        return SettingsResponse(
            default_content_processing_engine_doc=settings.default_content_processing_engine_doc,
            default_content_processing_engine_url=settings.default_content_processing_engine_url,
            default_embedding_option=settings.default_embedding_option,
            auto_delete_files=settings.auto_delete_files,
            source_batch_limit=settings.source_batch_limit,
            youtube_preferred_languages=settings.youtube_preferred_languages,
            tavily_api_key=_mask_secret(settings.tavily_api_key),
            tavily_include_domains=settings.tavily_include_domains,
            firecrawl_api_key=_mask_secret(settings.firecrawl_api_key),
            redaction_enabled=bool(settings.redaction_enabled),
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error updating settings"
        )
