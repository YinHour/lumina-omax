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
    def _is_table_separator_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return False
        body = stripped.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
        return body == ""

    lines = content.split("\n")
    result = []
    expected_pipes = None
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped.startswith("|"):
            expected_pipes = None
            result.append(line)
            i += 1
            continue

        if _is_table_separator_line(line):
            expected_pipes = line.count("|")
            result.append(line)
            i += 1
            continue

        if expected_pipes is None:
            expected_pipes = line.count("|")

        merged = line
        while merged.count("|") < expected_pipes and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()

            if not next_stripped or next_stripped.startswith("#"):
                break

            merged += "<br>" + next_line
            i += 1

        result.append(merged)
        i += 1

    return "\n".join(result)


def _excel_col_name(index_1_based: int) -> str:
    name = ""
    index = max(index_1_based, 1)
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _infer_excel_image_ext(image_obj: Any) -> str:
    path = getattr(image_obj, "path", "") or ""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext:
        return ext
    fmt = (getattr(image_obj, "format", "") or "").lower()
    if fmt:
        return fmt
    return "png"


def _extract_excel_image_bytes(image_obj: Any) -> Optional[bytes]:
    data_fn = getattr(image_obj, "_data", None)
    if callable(data_fn):
        try:
            data = data_fn()
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        except Exception:
            return None
    return None


def _excel_anchor_label(image_obj: Any, sheet_title: str) -> str:
    anchor = getattr(image_obj, "anchor", None)
    anchor_from = getattr(anchor, "_from", None)
    if anchor_from is None:
        return ""
    try:
        col = int(getattr(anchor_from, "col", 0)) + 1
        row = int(getattr(anchor_from, "row", 0)) + 1
    except Exception:
        return ""
    return f"{sheet_title}!{_excel_col_name(col)}{row}"


def _build_excel_figure_markdown(
    safe_source_id: str,
    figures: List[Dict[str, str]],
    descriptions_by_file: Dict[str, str],
) -> str:
    figures_section_parts = ["\n\n## Extracted Figures\n"]
    descriptions_section_parts = ["\n\n## Figure Descriptions\n"]

    for fig_index, fig in enumerate(figures, start=1):
        filename = fig["filename"]
        anchor = fig.get("anchor", "")
        anchor_text = f" ({anchor})" if anchor else ""
        figures_section_parts.append(
            f"\n### Figure {fig_index}{anchor_text}\n"
            f"![](/api/uploads/images/{safe_source_id}/{filename})\n"
        )
        descriptions_section_parts.append(
            f"\n### Figure {fig_index}\n"
            f"{descriptions_by_file.get(filename, 'Description unavailable.')}\n"
        )

    return "".join(figures_section_parts) + "".join(descriptions_section_parts)


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
    extracted_excel_figures: List[Dict[str, str]] = []
    is_excel_source = False
    safe_source_id = str(state.get("source_id") or "").split(":")[-1] if state.get("source_id") else ""
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
                            from open_notebook.utils.office_converter import (
                                convert_to_modern_office_format,
                            )

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
                            import re
                            import shutil
                            
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
        excel_ext = os.path.splitext(file_path)[1].lower() if file_path else ""
        is_excel_source = bool(file_path and excel_ext in (".xls", ".xlsx", ".xlsm"))
        if is_excel_source:
            processed_state.content = _sanitize_excel_table_newlines(
                processed_state.content or ""
            )

            # Extract embedded images directly from .xlsx/.xlsm files
            if excel_ext == ".xls":
                logger.warning(
                    "Excel image extraction skipped for legacy .xls format. "
                    "Only .xlsx/.xlsm image extraction is supported."
                )
            else:
                try:
                    from openpyxl import load_workbook

                    source_id = state.get("source_id")
                    if source_id and file_path and safe_source_id:
                        project_root = os.path.dirname(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        )
                        images_dir = os.path.join(
                            project_root, "data", "uploads", "images", safe_source_id
                        )
                        os.makedirs(images_dir, exist_ok=True)

                        existing_images = sorted(
                            [
                                f
                                for f in os.listdir(images_dir)
                                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
                            ]
                        )
                        if existing_images:
                            extracted_excel_figures = [
                                {"filename": name, "anchor": ""} for name in existing_images
                            ]
                            logger.info(
                                f"Reusing {len(existing_images)} existing Excel images for source_id={source_id}"
                            )
                        else:
                            workbook = load_workbook(file_path, data_only=True)
                            image_counter = 1
                            try:
                                for sheet in workbook.worksheets:
                                    images = getattr(sheet, "_images", []) or []
                                    for image in images:
                                        image_bytes = _extract_excel_image_bytes(image)
                                        if not image_bytes:
                                            continue

                                        ext = _infer_excel_image_ext(image)
                                        filename = f"excel_img_{image_counter:03d}.{ext}"
                                        image_path = os.path.join(images_dir, filename)
                                        with open(image_path, "wb") as f_img:
                                            f_img.write(image_bytes)

                                        anchor_label = _excel_anchor_label(image, sheet.title)

                                        extracted_excel_figures.append(
                                            {"filename": filename, "anchor": anchor_label}
                                        )
                                        image_counter += 1
                            finally:
                                workbook.close()

                            if extracted_excel_figures:
                                logger.info(
                                    f"Extracted {len(extracted_excel_figures)} images from Excel workbook "
                                    f"for source_id={source_id}"
                                )
                            else:
                                logger.debug(
                                    f"No embedded images found in Excel workbook for source_id={source_id}"
                                )
                except Exception as img_e:
                    logger.warning(f"Excel image extraction failed (non-fatal): {img_e}")

        logger.debug(f"Extracted content length: {len(processed_state.content or '')} characters")
    except Exception as e:
        logger.error(f"Error during content extraction for source_id={state.get('source_id')}: {e}")
        raise

    # Describe extracted images with vision model
    try:
        source_id = state.get("source_id")
        if source_id:
            safe_source_id = str(source_id).split(':')[-1]
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            images_dir = os.path.join(project_root, "data", "uploads", "images", safe_source_id)

            if os.path.isdir(images_dir):
                image_files = sorted([
                    f for f in os.listdir(images_dir)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))
                ])
                if image_files:
                    from esperanto import LanguageModel

                    from open_notebook.ai.models import model_manager

                    vision_model = await model_manager.get_vision_model()
                    if vision_model and isinstance(vision_model, LanguageModel):
                        import base64

                        from langchain_core.messages import HumanMessage

                        vision_lc = vision_model.to_langchain()
                        descriptions: List[Dict[str, str]] = []
                        mime_map = {'.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.gif': 'gif', '.webp': 'webp', '.bmp': 'bmp'}

                        descriptions_by_file: Dict[str, str] = {}
                        for img_file in image_files:
                            descriptions_by_file[img_file] = "Description generation failed."

                        for idx, img_file in enumerate(image_files):
                            img_path = os.path.join(images_dir, img_file)
                            try:
                                with open(img_path, "rb") as f:
                                    img_data = base64.b64encode(f.read()).decode("utf-8")
                                ext = os.path.splitext(img_file)[1].lower()
                                mime_type = mime_map.get(ext, 'jpeg')

                                msg = HumanMessage(content=[
                                    {
                                        "type": "text",
                                        "text": (
                                            "Please describe this figure from a document concisely. "
                                            "Include: 1) What type of visual it is (chart, diagram, photo, screenshot), "
                                            "2) The key information or data presented, "
                                            "3) Any text labels or captions visible."
                                        )
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/{mime_type};base64,{img_data}"}
                                    }
                                ])

                                response = await vision_lc.ainvoke([msg])
                                desc = response.content if hasattr(response, 'content') else str(response)
                                descriptions.append({"filename": img_file, "description": desc})
                                descriptions_by_file[img_file] = desc
                                logger.info(f"Described image {idx+1}/{len(image_files)}: {img_file}")
                            except Exception as img_e:
                                logger.warning(f"Failed to describe image {img_file}: {img_e}")
                                descriptions_by_file[img_file] = f"Description generation failed: {img_e}"

                        if is_excel_source:
                            figures = extracted_excel_figures or [
                                {"filename": name, "anchor": ""} for name in image_files
                            ]
                            if figures:
                                processed_state.content = (
                                    (processed_state.content or "")
                                    + _build_excel_figure_markdown(
                                        safe_source_id,
                                        figures,
                                        descriptions_by_file,
                                    )
                                )
                                logger.info(
                                    f"Added {len(figures)} extracted figure entries and descriptions "
                                    f"to source content"
                                )
                        elif descriptions:
                            desc_section = (
                                "\n\n## Figure Descriptions\n\n"
                                + "\n".join(
                                    f"### Figure: {item['filename']}\n{item['description']}\n"
                                    for item in descriptions
                                )
                            )
                            processed_state.content = (processed_state.content or "") + desc_section
                            logger.info(f"Added {len(descriptions)} figure descriptions to source content")
                    else:
                        logger.debug("No vision model configured. Skipping image description.")
                        if is_excel_source:
                            figures = extracted_excel_figures or [
                                {"filename": name, "anchor": ""} for name in image_files
                            ]
                            if figures:
                                placeholder_descriptions = {
                                    fig["filename"]: "Vision model is not configured. Description unavailable."
                                    for fig in figures
                                }

                                processed_state.content = (
                                    (processed_state.content or "")
                                    + _build_excel_figure_markdown(
                                        safe_source_id,
                                        figures,
                                        placeholder_descriptions,
                                    )
                                )
                                logger.info(
                                    f"Added {len(figures)} extracted figure entries with placeholder descriptions "
                                    "to source content"
                                )
    except Exception as e:
        logger.warning(f"Image description failed (non-fatal): {e}")

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
    raw_original_filename = getattr(content_state, "original_filename", None)
    original_filename = raw_original_filename if isinstance(raw_original_filename, str) else None
    source.asset = Asset(
        url=content_state.url,
        file_path=content_state.file_path,
        original_filename=original_filename,
    )
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
