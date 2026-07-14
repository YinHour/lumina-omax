from typing import Literal, Optional

ContextWindowSource = Literal["configured", "builtin"]

_BUILTIN_CONTEXT_WINDOWS: dict[tuple[str, str], int] = {
    ("deepseek", "deepseek-v4-pro"): 1_000_000,
}


def get_effective_context_window(
    provider: str,
    model_name: str,
    configured_tokens: Optional[int],
) -> tuple[Optional[int], Optional[ContextWindowSource]]:
    if configured_tokens is not None:
        return configured_tokens, "configured"

    builtin = _BUILTIN_CONTEXT_WINDOWS.get(
        (provider.strip().lower(), model_name.strip().lower())
    )
    if builtin is not None:
        return builtin, "builtin"

    return None, None
