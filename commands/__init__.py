"""Surreal-commands integration for Lumiton·Omax"""

from open_notebook.utils.logger_config import setup_logging
from open_notebook.utils.office_converter import get_libreoffice_command_info
from loguru import logger

setup_logging()

libreoffice_info = get_libreoffice_command_info()
logger.info(
    "LibreOffice command resolved: "
    f"command={libreoffice_info['command']}, "
    f"source={libreoffice_info['source']}, "
    f"available={libreoffice_info['available']}"
)

from .embedding_commands import (
    embed_insight_command,
    embed_note_command,
    embed_source_command,
    rebuild_embeddings_command,
)
from .example_commands import analyze_data_command, process_text_command
from .kg_commands import extract_knowledge_graph_command
from .podcast_commands import generate_podcast_command
from .source_commands import process_source_command

__all__ = [
    # Embedding commands
    "embed_note_command",
    "embed_insight_command",
    "embed_source_command",
    "rebuild_embeddings_command",
    # Other commands
    "generate_podcast_command",
    "process_source_command",
    "extract_knowledge_graph_command",
    "process_text_command",
    "analyze_data_command",
]
