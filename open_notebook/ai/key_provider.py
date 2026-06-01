"""
API Key Provider - Database-first with environment fallback.

This module provides a unified interface for retrieving API keys and provider
configuration. It reads from Credential records (individual per-provider
credentials) and falls back to environment variables for backward compatibility.

Usage:
    from open_notebook.ai.key_provider import provision_provider_keys

    # Call before model provisioning to set env vars from DB
    await provision_provider_keys("openai")
"""

import os
from typing import Optional

from loguru import logger

from open_notebook.domain.credential import Credential

# =============================================================================
# Provider Configuration Mapping
# =============================================================================
# Maps provider names to their environment variable names.
# This is the single source of truth for provider-to-env-var mapping.

PROVIDER_CONFIG = {
    # Simple providers (just API key)
    "openai": {
        "env_var": "OPENAI_API_KEY",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
    },
    "google": {
        "env_var": "GOOGLE_API_KEY",
    },
    "groq": {
        "env_var": "GROQ_API_KEY",
    },
    "mistral": {
        "env_var": "MISTRAL_API_KEY",
    },
    "deepseek": {
        "env_var": "DEEPSEEK_API_KEY",
    },
    "xai": {
        "env_var": "XAI_API_KEY",
    },
    "openrouter": {
        "env_var": "OPENROUTER_API_KEY",
    },
    "voyage": {
        "env_var": "VOYAGE_API_KEY",
    },
    "elevenlabs": {
        "env_var": "ELEVENLABS_API_KEY",
    },
    # URL-based providers
    "ollama": {
        "env_var": "OLLAMA_API_BASE",
    },
    "dashscope": {
        "env_var": "DASHSCOPE_API_KEY",
    },
    "minimax": {
        "env_var": "MINIMAX_API_KEY",
    },
}


async def _get_default_credential(provider: str) -> Optional[Credential]:
    """Get the first credential for a provider from the database."""
    try:
        credentials = await Credential.get_by_provider(provider)
        if credentials:
            return credentials[0]
    except Exception as e:
        logger.debug(f"Could not load credential from database for {provider}: {e}")
    return None


async def get_api_key(provider: str) -> Optional[str]:
    """
    Get API key for a provider. Checks database first, then env var.

    Args:
        provider: Provider name (openai, anthropic, etc.)

    Returns:
        API key string or None if not configured
    """
    cred = await _get_default_credential(provider)
    if cred and cred.api_key:
        logger.debug(f"Using {provider} API key from Credential")
        return cred.api_key.get_secret_value()

    # Fall back to environment variable
    config_info = PROVIDER_CONFIG.get(provider.lower())
    if config_info:
        env_value = os.environ.get(config_info["env_var"])
        if env_value:
            logger.debug(f"Using {provider} API key from environment variable")
        return env_value

    return None


async def _provision_simple_provider(provider: str) -> bool:
    return True

async def _provision_vertex() -> bool:
    return True

async def _provision_azure() -> bool:
    return True

async def _provision_openai_compatible() -> bool:
    return True

async def provision_provider_keys(provider: str) -> bool:
    """
    Deprecated: No longer modifies os.environ to prevent concurrency pollution.
    """
    return True

async def provision_all_keys() -> dict[str, bool]:
    """Deprecated: No longer modifies os.environ."""
    return {}
