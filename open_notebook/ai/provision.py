from dataclasses import dataclass
from typing import Optional

from esperanto import LanguageModel
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from open_notebook.ai.models import Model, model_manager
from open_notebook.ai.reasoning_chat import maybe_make_reasoning_aware
from open_notebook.ai.redaction_wrapper import maybe_make_redaction_aware
from open_notebook.ai.usage_audit import attach_usage_callback
from open_notebook.exceptions import ConfigurationError
from open_notebook.utils import token_count


@dataclass(frozen=True)
class ProvisionedModelInfo:
    model: BaseChatModel
    model_id: str
    model_name: str
    provider: str
    input_tokens: int
    context_window_tokens: Optional[int]
    context_window_source: Optional[str]


async def resolve_model_record(content, model_id, default_type) -> tuple[Model, int]:
    tokens = token_count(content)
    selected_model_id = model_id

    if tokens > 105_000:
        defaults = await model_manager.get_defaults()
        selected_model_id = defaults.large_context_model
    elif not selected_model_id:
        defaults = await model_manager.get_defaults()
        default_fields = {
            "chat": "default_chat_model",
            "transformation": "default_transformation_model",
            "tools": "default_tools_model",
            "large_context": "large_context_model",
            "vision": "default_vision_model",
        }
        field = default_fields.get(default_type)
        selected_model_id = getattr(defaults, field, None) if field else None
        if not selected_model_id and default_type in {"transformation", "tools"}:
            selected_model_id = defaults.default_chat_model

    if not selected_model_id:
        raise ConfigurationError(
            f"No model configured for default type={default_type}. "
            f"Please go to Settings → Models and configure a default model."
        )

    return await Model.get(selected_model_id), tokens


async def provision_langchain_model_with_info(
    content, model_id, default_type, **kwargs
) -> ProvisionedModelInfo:
    model_record, input_tokens = await resolve_model_record(
        content, model_id, default_type
    )
    model, credential = await model_manager.get_model_from_record(model_record, **kwargs)
    if model is None:
        raise ConfigurationError(
            f"No model configured for model_id={model_record.id}. "
            "Please go to Settings -> Models and configure the model."
        )
    if not isinstance(model, LanguageModel):
        raise ConfigurationError(
            f"Model is not a LanguageModel: {type(model).__name__}."
        )

    langchain_model = attach_usage_callback(
        maybe_make_redaction_aware(
            maybe_make_reasoning_aware(model.to_langchain())
        ),
        model=model_record,
        credential=credential,
    )
    context_window_tokens, context_window_source = (
        model_record.get_effective_context_window()
    )
    return ProvisionedModelInfo(
        model=langchain_model,
        model_id=model_record.id or str(model_id or ""),
        model_name=model_record.name,
        provider=model_record.provider,
        input_tokens=input_tokens,
        context_window_tokens=context_window_tokens,
        context_window_source=context_window_source,
    )


async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    """
    Returns the best model to use based on the context size and on whether there is a specific model being requested in Config.
    If context > 105_000, returns the large_context_model
    If model_id is specified in Config, returns that model
    Otherwise, returns the default model for the given type
    """
    model_record, tokens = await resolve_model_record(content, model_id, default_type)
    selection_reason = (
        f"large_context (content has {tokens} tokens)"
        if tokens > 105_000
        else f"explicit model_id={model_id}"
        if model_id
        else f"default for type={default_type}"
    )
    model, credential = await model_manager.get_model_from_record(model_record, **kwargs)

    logger.debug(
        "Using model type={} ({})",
        type(model).__name__ if model is not None else "None",
        selection_reason,
    )

    if model is None:
        logger.error(
            f"Model provisioning failed: No model found. "
            f"Selection reason: {selection_reason}. "
            f"model_id={model_id}, default_type={default_type}. "
            f"Please check Settings → Models and ensure a default model is configured for '{default_type}'."
        )
        raise ConfigurationError(
            f"No model configured for {selection_reason}. "
            f"Please go to Settings → Models and configure a default model for '{default_type}'."
        )

    if not isinstance(model, LanguageModel):
        logger.error(
            f"Model type mismatch: Expected LanguageModel but got {type(model).__name__}. "
            f"Selection reason: {selection_reason}. "
            f"model_id={model_id}, default_type={default_type}."
        )
        raise ConfigurationError(
            f"Model is not a LanguageModel: {type(model).__name__}. "
            f"Please check that the model configured for '{default_type}' is a language model, not an embedding or speech model."
        )

    return attach_usage_callback(
        maybe_make_redaction_aware(
            maybe_make_reasoning_aware(model.to_langchain())
        ),
        model=model_record,
        credential=credential,
    )
