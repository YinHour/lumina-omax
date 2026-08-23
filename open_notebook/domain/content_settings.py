import os
from typing import ClassVar, List, Literal, Optional

from pydantic import Field, model_validator

from open_notebook.domain.base import RecordModel


class ContentSettings(RecordModel):
    record_id: ClassVar[str] = "open_notebook:content_settings"
    default_content_processing_engine_doc: Optional[
        Literal["auto", "docling", "mineru", "simple"]
    ] = Field(None, description="Default Content Processing Engine for Documents")
    default_content_processing_engine_url: Optional[
        Literal["auto", "firecrawl", "jina", "simple"]
    ] = Field("auto", description="Default Content Processing Engine for URLs")
    firecrawl_api_key: Optional[str] = Field(
        None, description="Firecrawl API Key for URL extraction"
    )
    default_embedding_option: Optional[Literal["ask", "always", "never"]] = Field(
        "ask", description="Default Embedding Option for Vector Search"
    )
    auto_delete_files: Optional[Literal["yes", "no"]] = Field(
        "yes", description="Auto Delete Uploaded Files"
    )
    source_batch_limit: int = Field(
        50,
        ge=1,
        le=200,
        description="Maximum number of sources allowed in one notebook",
    )
    youtube_preferred_languages: Optional[List[str]] = Field(
        ["en", "pt", "es", "de", "nl", "en-GB", "fr", "de", "hi", "ja"],
        description="Preferred languages for YouTube transcripts",
    )
    tavily_api_key: Optional[str] = Field(
        None, description="Tavily Search API Key"
    )
    tavily_include_domains: Optional[str] = Field(
        None, description="Tavily Search Include Domains (comma separated)"
    )
    redaction_enabled: Optional[bool] = Field(
        False,
        description="Egress redaction gateway: mask sensitive terms before sending prompts to external LLM providers",
    )

    @model_validator(mode="after")
    def set_defaults_from_env(self):
        if not self.default_content_processing_engine_doc:
            env_val = os.environ.get("CCORE_DOCUMENT_ENGINE", "auto").strip().lower()
            if env_val in ["auto", "docling", "mineru", "simple"]:
                self.default_content_processing_engine_doc = env_val
            else:
                self.default_content_processing_engine_doc = "auto"
        return self
