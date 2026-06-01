import time
from typing import Optional

from loguru import logger
from surreal_commands import CommandInput, CommandOutput, command

from open_notebook.database.repository import ensure_record_id, repo_insert, repo_query
from open_notebook.domain.notebook import Source
from open_notebook.exceptions import ConfigurationError


class ExtractKGInput(CommandInput):
    source_id: str

class ExtractKGOutput(CommandOutput):
    success: bool
    source_id: str
    entities_extracted: int
    relations_extracted: int
    processing_time: float
    error_message: Optional[str] = None

@command(
    "extract_knowledge_graph",
    app="open_notebook",
    retry={
        "max_attempts": 3,
        "wait_strategy": "exponential_jitter",
        "wait_min": 1,
        "wait_max": 60,
        "stop_on": [ValueError, ConfigurationError],
        "retry_log_level": "debug",
    },
)
async def extract_knowledge_graph_command(input_data: ExtractKGInput) -> ExtractKGOutput:
    """
    Extract knowledge graph from a source using an LLM and save to SurrealDB.
    """
    start_time = time.time()

    try:
        from open_notebook.graphs.knowledge_graph import graph as kg_graph
        
        logger.info(f"Starting KG extraction for source: {input_data.source_id}")

        source = await Source.get(input_data.source_id)
        if not source:
            raise ValueError(f"Source '{input_data.source_id}' not found")

        if not source.full_text or not source.full_text.strip():
            raise ValueError(f"Source '{input_data.source_id}' has no text to extract KG")

        # First, delete existing KG for this source
        await repo_query(
            "DELETE kg_relation WHERE source_id = $source_id",
            {"source_id": input_data.source_id},
        )
        await repo_query(
            "DELETE kg_entity WHERE source_id = $source_id",
            {"source_id": input_data.source_id},
        )

        # Execute KG graph
        result = await kg_graph.ainvoke({"source": source})
        
        entities = result.get("extracted_entities", [])
        relations = result.get("extracted_relations", [])
        
        entities_count = len(entities)
        relations_count = len(relations)

        processing_time = time.time() - start_time
        logger.info(
            f"Successfully extracted KG for source {input_data.source_id}: "
            f"{entities_count} entities, {relations_count} relations in {processing_time:.2f}s"
        )

        return ExtractKGOutput(
            success=True,
            source_id=input_data.source_id,
            entities_extracted=entities_count,
            relations_extracted=relations_count,
            processing_time=processing_time,
        )

    except ValueError as e:
        processing_time = time.time() - start_time
        logger.error(f"Failed to extract KG for source {input_data.source_id}: {e}")
        return ExtractKGOutput(
            success=False,
            source_id=input_data.source_id,
            entities_extracted=0,
            relations_extracted=0,
            processing_time=processing_time,
            error_message=str(e),
        )
    except Exception as e:
        logger.debug(f"Transient error extracting KG for source {input_data.source_id}: {e}")
        raise
