import asyncio
import os
import re
import unicodedata
from typing import Annotated, Any, List, Optional

from ai_prompter import Prompter
from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from loguru import logger
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from open_notebook.ai.models import model_manager
from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Source
from open_notebook.exceptions import OpenNotebookError
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.chunking import ContentType, chunk_text, detect_content_type
from open_notebook.utils.error_classifier import classify_error
from open_notebook.utils.text_utils import extract_text_content


def slugify(value: str) -> str:
    """Create a URL-safe, DB-safe slug from a string."""
    value = str(value)
    value = unicodedata.normalize('NFKC', value)
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

class KGEntity(BaseModel):
    id: str = Field(description="Unique ID for the entity (e.g. material_graphene)")
    type: str = Field(description="Entity type (e.g. MATERIAL, EXPERIMENT)")
    name: str = Field(description="Human-readable name of the entity")
    description: Optional[str] = Field(default=None, description="Optional properties, values, or details")

class KGRelation(BaseModel):
    source: str = Field(description="Source entity ID")
    target: str = Field(description="Target entity ID")
    type: str = Field(description="Relationship type (e.g. USES_MATERIAL)")
    description: Optional[str] = Field(default=None, description="Details like conditions or numerical values")

class KnowledgeGraphSchema(BaseModel):
    entities: List[KGEntity] = Field(default_factory=list)
    relationships: List[KGRelation] = Field(default_factory=list)

class KGState(TypedDict):
    source: Source
    chunks: List[str]
    extracted_entities: Annotated[list, list.__add__]
    extracted_relations: Annotated[list, list.__add__]

async def prepare_chunks(state: KGState, config: RunnableConfig) -> dict:
    source = state["source"]
    text = source.full_text or ""
    
    # Bypass chunking: send the entire document as a single chunk to leverage long-context models
    chunks = [text] if text.strip() else []
    
    logger.info(f"Prepared full text as a single chunk for KG extraction on source {source.id}")
    return {"chunks": chunks}

async def process_chunks(state: KGState, config: RunnableConfig) -> dict:
    source = state["source"]
    chunks = state["chunks"]
    
    all_entities = []
    all_relations = []
    
    # Check if tools model is available, else fallback to chat model
    defaults = await model_manager.get_defaults()
    model_id = defaults.default_tools_model or defaults.default_chat_model
    
    entity_types_str = os.environ.get("KG_ENTITY_TYPES", "MATERIAL,CHEMICAL,PROPERTY,CONDITION,RESULT,EXPERIMENT,PRODUCT,METHOD")
    relation_types_str = os.environ.get("KG_RELATION_TYPES", "USES_MATERIAL,HAS_CONDITION,YIELDS_RESULT,CONTAINS_CHEMICAL,MEASURES_PROPERTY,COMPARES_WITH,APPLIES_TO")

    parser = PydanticOutputParser(pydantic_object=KnowledgeGraphSchema)
    
    async def extract_from_chunk(chunk_text_data: str):
        try:
            payload = dict(
                text=chunk_text_data,
                entity_types=entity_types_str,
                relation_types=relation_types_str,
            )
            system_prompt = Prompter(prompt_template="kg/extraction", parser=parser).render(data=payload)
            
            # Using tools model since this is an extraction task
            model = await provision_langchain_model(
                system_prompt,
                model_id,
                "tools",
                max_tokens=60000,
            )
            
            ai_message = await model.ainvoke(system_prompt)
            message_content = extract_text_content(ai_message.content)
            cleaned_content = clean_thinking_content(message_content)
            
            parsed_graph = parser.parse(cleaned_content)
            return parsed_graph
        except Exception as e:
            import traceback
            logger.warning(f"Failed to extract KG from chunk: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return KnowledgeGraphSchema()

    # Process chunks concurrently in batches of 5 to avoid API rate limits
    batch_size = 5
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        logger.info(f"Extracting KG for chunks {i+1} to {min(i+batch_size, len(chunks))} of {len(chunks)}")
        tasks = [extract_from_chunk(c) for c in batch]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res:
                all_entities.extend(res.entities)
                all_relations.extend(res.relationships)
                
        # Sleep slightly to prevent rate limits
        await asyncio.sleep(1.0)

    logger.info(f"Extracted {len(all_entities)} raw entities and {len(all_relations)} raw relations")
    return {
        "extracted_entities": all_entities,
        "extracted_relations": all_relations
    }

async def ingest_to_db(state: KGState, config: RunnableConfig) -> dict:
    source_id = str(state["source"].id)
    entities = state["extracted_entities"]
    relations = state["extracted_relations"]
    
    # Map raw extraction IDs to slugified DB IDs
    id_map = {}
    valid_entities = []
    
    # 1. Upsert Entities
    for e in entities:
        if not e.name or not e.id:
            continue
        # Use slugified name as the DB ID to automatically merge duplicates
        slug = slugify(e.name)
        if not slug:
            continue
        
        db_id = slug
        id_map[e.id] = db_id
        
        # Merge properties into valid entities map
        valid_entities.append({
            "id": f"kg_entity:{db_id}",
            "name": e.name,
            "type": e.type,
            "description": e.description,
            "source_id": str(source_id)
        })

    # Insert entities using UPSERT strategy in SurrealDB (UPDATE)
    logger.info(f"Ingesting {len(valid_entities)} entities into SurrealDB")
    for batch_i in range(0, len(valid_entities), 100):
        batch = valid_entities[batch_i:batch_i+100]
        # Perform sequential updates to prevent read/write transaction conflicts
        async def upsert_entity(ent):
            try:
                await repo_query(
                    """
                    UPSERT $id MERGE {
                        name: $name,
                        type: $type,
                        description: $description,
                        source_id: <string> $source_id
                    };
                    """,
                    {
                        "id": ensure_record_id(ent["id"]),
                        "name": ent["name"],
                        "type": ent["type"],
                        "description": ent["description"],
                        "source_id": str(ent["source_id"])
                    }
                )
            except Exception as e:
                logger.error(f"Error upserting entity {ent['id']}: {e}")
        
        for ent in batch:
            await upsert_entity(ent)

    # 2. Insert Relations
    valid_relations = []
    for r in relations:
        source_db_id = id_map.get(r.source)
        target_db_id = id_map.get(r.target)
        
        if source_db_id and target_db_id and r.type:
            valid_relations.append({
                "in": f"kg_entity:{source_db_id}",
                "out": f"kg_entity:{target_db_id}",
                "type": r.type,
                "description": r.description,
                "source_id": str(source_id)
            })
            
    logger.info(f"Ingesting {len(valid_relations)} relations into SurrealDB")
    for batch_i in range(0, len(valid_relations), 100):
        batch = valid_relations[batch_i:batch_i+100]
        async def insert_rel(rel):
            try:
                # Use RELATE to create the edge
                await repo_query(
                    """
                    RELATE $in->kg_relation->$out SET type = $type, description = $description, source_id = <string> $source_id;
                    """,
                    {
                        "in": ensure_record_id(rel["in"]),
                        "out": ensure_record_id(rel["out"]),
                        "type": rel["type"],
                        "description": rel["description"],
                        "source_id": str(rel["source_id"])
                    }
                )
            except Exception as e:
                logger.error(f"Error inserting relation: {e}")
        
        for rel in batch:
            await insert_rel(rel)

    return {}


workflow = StateGraph(KGState)

workflow.add_node("prepare_chunks", prepare_chunks)
workflow.add_node("process_chunks", process_chunks)
workflow.add_node("ingest_to_db", ingest_to_db)

workflow.add_edge(START, "prepare_chunks")
workflow.add_edge("prepare_chunks", "process_chunks")
workflow.add_edge("process_chunks", "ingest_to_db")
workflow.add_edge("ingest_to_db", END)

graph = workflow.compile()
