import operator
from typing import Any, Dict, List, Optional

from content_core import extract_content
from content_core.common import ProcessSourceState
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from loguru import logger
from typing_extensions import Annotated, TypedDict

from open_notebook.ai.models import Model, ModelManager
from open_notebook.domain.content_settings import ContentSettings
from open_notebook.domain.notebook import Asset, Source
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.transformation import graph as transform_graph


class SourceState(TypedDict):
    content_state: ProcessSourceState
    apply_transformations: List[Transformation]
    source_id: str
    notebook_ids: List[str]
    source: Source
    transformation: Annotated[list, operator.add]
    embed: bool


class TransformationState(TypedDict):
    source: Source
    transformation: Transformation


def _sanitize_excel_table_newlines(content: str) -> str:
    """Fix broken markdown table rows caused by newlines in Excel cells.

    content_core's openpyxl-based Excel extraction inserts raw \\n into
    markdown table rows, which splits a single row into multiple lines.
    This merges orphan continuation lines back into the preceding table row
    using <br> to preserve multi-line semantics.
    """
    lines = content.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if (
            result
            and result[-1].lstrip().startswith("|")
            and not stripped.startswith("|")
            and stripped
            and not stripped.startswith("#")
        ):
            result[-1] = result[-1] + "<br>" + line
        else:
            result.append(line)
    return "\n".join(result)


async def content_process(state: SourceState) -> dict:
    ContentSettings.clear_instance()  # Force reload from DB
    content_settings = await ContentSettings.get_instance()
    content_state: Dict[str, Any] = state["content_state"]  # type: ignore[assignment]

    content_state["url_engine"] = (
        content_settings.default_content_processing_engine_url or "auto"
    )
    content_state["document_engine"] = (
        content_settings.default_content_processing_engine_doc or "auto"
    )
    content_state["output_format"] = "markdown"

    # Add speech-to-text model configuration from Default Models
    try:
        model_manager = ModelManager()
        defaults = await model_manager.get_defaults()
        if defaults.default_speech_to_text_model:
            stt_model = await Model.get(defaults.default_speech_to_text_model)
            if stt_model:
                content_state["audio_provider"] = stt_model.provider
                content_state["audio_model"] = stt_model.name
                logger.info(
                    f"Using speech-to-text model: {stt_model.provider}/{stt_model.name}"
                )
    except Exception as e:
        logger.warning(f"Failed to retrieve speech-to-text model configuration: {e}")
        # Continue without custom audio model (content-core will use its default)

    logger.info(f"Starting content extraction for source_id={state.get('source_id')}")
    logger.info(f"Engine doc: {content_state.get('document_engine')}, URL: {content_state.get('url_engine')}")
    try:
        import asyncio
        import os
        import subprocess
        import tempfile
        from content_core.common import ProcessSourceState
        
        def _sync_extract(state, source_id):
            engine = state.get("document_engine")
            file_path = state.get("file_path")
            
            # Intercept MinerU extraction
            if engine == "mineru" and file_path and file_path.lower().endswith(('.pdf', '.ppt', '.pptx', '.doc', '.docx')):
                logger.info(f"Using MinerU to extract content from {file_path}")
                try:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        if file_path.lower().endswith(('.ppt', '.pptx', '.doc', '.docx')):
                            from open_notebook.utils.office_converter import convert_to_modern_office_format

                            file_path = convert_to_modern_office_format(file_path)
                            state["file_path"] = file_path

                        # Run mineru CLI
                        env = os.environ.copy()
                        if "HF_ENDPOINT" not in env:
                            env["HF_ENDPOINT"] = "https://hf-mirror.com"
                            
                        try:
                            # Enable table extraction enhancement
                            env["MINERU_TABLE_ENABLE"] = "true"
                            # Enable fast downloads
                            env["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
                            # Use modelscope for faster downloads
                            env["MINERU_MODEL_SOURCE"] = "modelscope"
                            import sys
                            
                            logger.info("MinerU may need to download models on first run. Streaming output to console...")
                            subprocess.run([
                                "mineru",
                                "-p", file_path,
                                "-o", temp_dir,
                                "-m", "auto",
                                "--backend", "pipeline",
                            ], check=True, env=env, stdout=sys.stdout, stderr=sys.stderr)
                        except subprocess.CalledProcessError as e:
                            logger.error(f"MinerU extraction process failed with exit code {e.returncode}")
                            raise
                        
                        # Find the output directory (mineru creates a dir based on filename and model name)
                        base_name = os.path.splitext(os.path.basename(file_path))[0]
                        out_dir = os.path.join(temp_dir, base_name, "auto")
                        
                        target_dir = out_dir if os.path.exists(out_dir) else os.path.join(temp_dir, base_name)
                        
                        md_content = ""
                        if os.path.exists(target_dir):
                            for file in os.listdir(target_dir):
                                if file.endswith(".md"):
                                    with open(os.path.join(target_dir, file), "r", encoding="utf-8") as f:
                                        md_content = f.read()
                                    break
                            
                            # Copy images to persistent storage
                            import shutil
                            import re
                            
                            images_dir = os.path.join(target_dir, "images")
                            if os.path.exists(images_dir) and source_id:
                                safe_source_id = str(source_id).split(':')[-1]
                                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                                persistent_images_dir = os.path.join(project_root, "data", "uploads", "images", safe_source_id)
                                os.makedirs(persistent_images_dir, exist_ok=True)
                                
                                for img_file in os.listdir(images_dir):
                                    shutil.copy2(os.path.join(images_dir, img_file), os.path.join(persistent_images_dir, img_file))
                                
                                # Replace image paths in both Markdown and HTML formats
                                safe_images_url = f"/api/uploads/images/{safe_source_id}"
                                
                                # 1. Replace Markdown image syntax: ![alt](images/xxx.jpg)
                                md_content = re.sub(
                                    r'\!?\[.*?\]\((images/[^)]+)\)',
                                    lambda m: f"![](/api/uploads/images/{safe_source_id}/{os.path.basename(m.group(1))})",
                                    md_content
                                )
                                # 2. Replace HTML <img> tags: <img src="images/xxx.jpg" ...>
                                md_content = re.sub(
                                    r'<img\s+([^>]*?)src=["\']images/([^"\']+)["\']([^>]*)>',
                                    lambda m: f'<img {m.group(1)}src="{safe_images_url}/{os.path.basename(m.group(2))}"{m.group(3)}>',
                                    md_content
                                )
                                logger.debug(f"Replaced image paths pointing to {safe_images_url}")
                        
                        if md_content:
                            logger.info(f"Successfully extracted {len(md_content)} chars using MinerU.")
                            state["content"] = md_content
                            if not state.get("title") and "file_path" in state and state["file_path"]:
                                state["title"] = os.path.basename(state["file_path"])
                            # Bypass content_core's Pydantic validation which only allows 'auto', 'simple', 'docling'
                            state["document_engine"] = "auto"
                            return ProcessSourceState(**state)
                        else:
                            logger.warning("MinerU failed to produce markdown output. Falling back to simple engine.")
                            state["document_engine"] = "simple"
                except Exception as e:
                    logger.error(f"MinerU extraction failed: {e}. Falling back to simple engine.")
                    state["document_engine"] = "simple"
            elif engine == "mineru":
                logger.warning("MinerU does not support this file type. Falling back to simple engine.")
                state["document_engine"] = "simple"

            # Create a new event loop for this thread to run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(extract_content(state))
            finally:
                loop.close()
                
        # 让 CPU 密集型任务在背景线程中运行，不阻塞主事件循环
        processed_state = await asyncio.to_thread(_sync_extract, content_state, state.get("source_id"))
        logger.info(f"Content extraction completed for source_id={state.get('source_id')}")

        file_path = content_state.get("file_path", "")
        if file_path and file_path.lower().endswith(('.xls', '.xlsx')):
            processed_state.content = _sanitize_excel_table_newlines(
                processed_state.content or ""
            )

        logger.debug(f"Extracted content length: {len(processed_state.content or '')} characters")
    except Exception as e:
        logger.error(f"Error during content extraction for source_id={state.get('source_id')}: {e}")
        raise

    if not processed_state.content or not processed_state.content.strip():
        url = processed_state.url or ""
        if url and ("youtube.com" in url or "youtu.be" in url):
            raise ValueError(
                "Could not extract content from this YouTube video. "
                "No transcript or subtitles are available. "
                "Try configuring a Speech-to-Text model in Settings "
                "to transcribe the audio instead."
            )
        raise ValueError(
            "Could not extract any text content from this source. "
            "The content may be empty, inaccessible, or in an unsupported format."
        )

    return {"content_state": processed_state}


async def save_source(state: SourceState) -> dict:
    content_state = state["content_state"]

    # Get existing source using the provided source_id
    source = await Source.get(state["source_id"])
    if not source:
        raise ValueError(f"Source with ID {state['source_id']} not found")

    # Update the source with processed content
    source.asset = Asset(url=content_state.url, file_path=content_state.file_path)
    source.full_text = content_state.content

    # Preserve user-set title; only overwrite placeholder or empty titles
    if content_state.title and (not source.title or source.title == "Processing..."):
        source.title = content_state.title

    await source.save()

    # NOTE: Notebook associations are created by the API immediately for UI responsiveness
    # No need to create them here to avoid duplicate edges

    if state["embed"]:
        if source.full_text and source.full_text.strip():
            logger.debug("Embedding content for vector search")
            await source.vectorize()
        else:
            logger.warning(
                f"Source {source.id} has no text content to embed, skipping vectorization"
            )

    return {"source": source}


def trigger_transformations(state: SourceState, config: RunnableConfig) -> List[Send]:
    if len(state["apply_transformations"]) == 0:
        return []

    to_apply = state["apply_transformations"]
    logger.debug(f"Applying transformations {to_apply}")

    return [
        Send(
            "transform_content",
            {
                "source": state["source"],
                "transformation": t,
            },
        )
        for t in to_apply
    ]


async def transform_content(state: TransformationState) -> Optional[dict]:
    source = state["source"]
    content = source.full_text
    if not content:
        return None
    transformation: Transformation = state["transformation"]

    logger.info(f"Submitting background job for transformation {transformation.title or transformation.name}")
    from surreal_commands import submit_command
    submit_command(
        "open_notebook",
        "run_transformation",
        {
            "source_id": str(source.id),
            "transformation_id": str(transformation.id)
        }
    )
    
    return {
        "transformation": [
            {
                "output": "Transformation job submitted to background worker",
                "transformation_name": transformation.title or transformation.name,
            }
        ]
    }


# Create and compile the workflow
workflow = StateGraph(SourceState)

# Add nodes
workflow.add_node("content_process", content_process)
workflow.add_node("save_source", save_source)
workflow.add_node("transform_content", transform_content)
# Define the graph edges
workflow.add_edge(START, "content_process")
workflow.add_edge("content_process", "save_source")
workflow.add_conditional_edges(
    "save_source", trigger_transformations, ["transform_content"]
)
workflow.add_edge("transform_content", END)

# Compile the graph
source_graph = workflow.compile()
