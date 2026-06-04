import asyncio
import os
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator
from surreal_commands import submit_command
from surrealdb import RecordID

from open_notebook.database.repository import ensure_record_id, repo_query, repo_transaction
from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError


class Notebook(ObjectModel):
    table_name: ClassVar[str] = "notebook"
    name: str
    description: str = ""
    archived: Optional[bool] = False
    password: Optional[str] = None
    creator_name: Optional[str] = None
    is_aggregated: Optional[bool] = False
    hidden_sources: Optional[List[Any]] = Field(default_factory=list)
    hidden_notes: Optional[List[Any]] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise InvalidInputError("Notebook name cannot be empty")
        return v

    async def get_sources(self) -> List["Source"]:
        try:
            srcs = await repo_query(
                """
                select * omit source.full_text from (
                    select in as source from reference 
                    where (out=$id OR out in (SELECT VALUE out FROM aggregates WHERE in = $id))
                    AND in NOT IN (SELECT VALUE (hidden_sources ?? []) FROM $id)[0]
                    fetch source
                ) order by source.updated desc
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [Source(**src["source"]) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching sources for notebook {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def get_notes(self) -> List["Note"]:
        try:
            srcs = await repo_query(
                """
                select * omit note.content, note.embedding from (
                    select in as note from artifact 
                    where (out=$id OR out in (SELECT VALUE out FROM aggregates WHERE in = $id))
                    AND in NOT IN (SELECT VALUE (hidden_notes ?? []) FROM $id)[0]
                    fetch note
                ) order by note.updated desc
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [Note(**src["note"]) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching notes for notebook {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def get_chat_sessions(self) -> List["ChatSession"]:
        try:
            srcs = await repo_query(
                """
                select * from (
                    select
                    <- chat_session as chat_session
                    from refers_to
                    where out=$id
                    fetch chat_session
                )
                order by chat_session.updated desc
                """,
                {"id": ensure_record_id(self.id)},
            )
            return (
                [ChatSession(**src["chat_session"][0]) for src in srcs] if srcs else []
            )
        except Exception as e:
            logger.error(
                f"Error fetching chat sessions for notebook {self.id}: {str(e)}"
            )
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def get_delete_preview(self) -> Dict[str, Any]:
        """
        Get counts of items that would be affected by deleting this notebook.

        Returns a dict with:
        - note_count: Number of notes that will be deleted
        - exclusive_source_count: Sources only in this notebook (can be deleted)
        - shared_source_count: Sources in other notebooks (will be unlinked only)
        """
        try:
            notebook_id = ensure_record_id(self.id)

            # Count notes
            note_result = await repo_query(
                "SELECT count() as count FROM artifact WHERE out = $notebook_id GROUP ALL",
                {"notebook_id": notebook_id},
            )
            note_count = note_result[0]["count"] if note_result else 0

            # Get sources with count of references to OTHER notebooks
            # If assigned_others = 0, source is exclusive to this notebook
            # If assigned_others > 0, source is shared with other notebooks
            source_counts = await repo_query(
                """
                SELECT
                    id,
                    count(->reference[WHERE out != $notebook_id].out) as assigned_others
                FROM (SELECT VALUE <-reference.in AS sources FROM $notebook_id)[0]
                """,
                {"notebook_id": notebook_id},
            )

            exclusive_count = 0
            shared_count = 0
            for src in source_counts:
                if src.get("assigned_others", 0) == 0:
                    exclusive_count += 1
                else:
                    shared_count += 1

            return {
                "note_count": note_count,
                "exclusive_source_count": exclusive_count,
                "shared_source_count": shared_count,
            }
        except Exception as e:
            logger.error(f"Error getting delete preview for notebook {self.id}: {e}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def delete(self, delete_exclusive_sources: bool = False) -> Dict[str, int]:
        """
        Delete notebook with cascade deletion of notes and optional source deletion.

        Args:
            delete_exclusive_sources: If True, also delete sources that belong
                                     only to this notebook. Default is False.

        Returns:
            Dict with counts: deleted_notes, deleted_sources, unlinked_sources
        """
        if self.id is None:
            raise InvalidInputError("Cannot delete notebook without an ID")

        try:
            notebook_id = ensure_record_id(self.id)
            deleted_notes = 0
            deleted_sources = 0
            unlinked_sources = 0

            # 1. Get and delete all notes linked directly to this notebook
            notes_records = await repo_query(
                """
                select in as note from artifact where out=$notebook_id
                fetch note
                """,
                {"notebook_id": notebook_id},
            )
            notes = [Note(**n["note"]) for n in notes_records] if notes_records else []
            for note in notes:
                await note.delete()
                deleted_notes += 1
            logger.info(f"Deleted {deleted_notes} notes for notebook {self.id}")

            # Delete artifact relationships
            await repo_query(
                "DELETE artifact WHERE out = $notebook_id",
                {"notebook_id": notebook_id},
            )

            # 2. Handle sources
            if delete_exclusive_sources:
                # Find sources with count of references to OTHER notebooks
                # If assigned_others = 0, source is exclusive to this notebook
                source_counts = await repo_query(
                    """
                    SELECT
                        id,
                        count(->reference[WHERE out != $notebook_id].out) as assigned_others
                    FROM (SELECT VALUE <-reference.in AS sources FROM $notebook_id)[0]
                    """,
                    {"notebook_id": notebook_id},
                )

                for src in source_counts:
                    source_id = src.get("id")
                    if source_id and src.get("assigned_others", 0) == 0:
                        # Exclusive source - delete it
                        try:
                            source = await Source.get(str(source_id))
                            await source.delete()
                            deleted_sources += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete exclusive source {source_id}: {e}"
                            )
                    else:
                        unlinked_sources += 1
            else:
                # Just count sources that will be unlinked
                source_result = await repo_query(
                    "SELECT count() as count FROM reference WHERE out = $notebook_id GROUP ALL",
                    {"notebook_id": notebook_id},
                )
                unlinked_sources = source_result[0]["count"] if source_result else 0

            # Delete reference relationships (unlink all sources)
            await repo_query(
                "DELETE reference WHERE out = $notebook_id",
                {"notebook_id": notebook_id},
            )
            
            # Delete aggregates relationships
            await repo_query(
                "DELETE aggregates WHERE in = $notebook_id OR out = $notebook_id",
                {"notebook_id": notebook_id},
            )
            logger.info(
                f"Unlinked {unlinked_sources} sources, deleted {deleted_sources} "
                f"exclusive sources for notebook {self.id}"
            )

            # 3. Delete the notebook record itself
            await super().delete()
            logger.info(f"Deleted notebook {self.id}")

            return {
                "deleted_notes": deleted_notes,
                "deleted_sources": deleted_sources,
                "unlinked_sources": unlinked_sources,
            }

        except Exception as e:
            logger.error(f"Error deleting notebook {self.id}: {e}")
            logger.exception(e)
            raise DatabaseOperationError(f"Failed to delete notebook: {e}")


class Asset(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None
    original_filename: Optional[str] = None


class SourceEmbedding(ObjectModel):
    table_name: ClassVar[str] = "source_embedding"
    content: str

    async def get_source(self) -> "Source":
        try:
            src = await repo_query(
                """
            select source.* from $id fetch source
            """,
                {"id": ensure_record_id(self.id)},
            )
            return Source(**src[0]["source"])
        except Exception as e:
            logger.error(f"Error fetching source for embedding {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)


class SourceInsight(ObjectModel):
    table_name: ClassVar[str] = "source_insight"
    insight_type: str
    content: str

    async def get_source(self) -> "Source":
        try:
            src = await repo_query(
                """
            select source.* from $id fetch source
            """,
                {"id": ensure_record_id(self.id)},
            )
            return Source(**src[0]["source"])
        except Exception as e:
            logger.error(f"Error fetching source for insight {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def save_as_note(self, notebook_id: Optional[str] = None) -> Any:
        source = await self.get_source()
        note = Note(
            title=f"{self.insight_type} from source {source.title}",
            content=self.content,
        )
        await note.save()
        if notebook_id:
            await note.add_to_notebook(notebook_id)
        return note


class Source(ObjectModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    table_name: ClassVar[str] = "source"
    asset: Optional[Asset] = None
    title: Optional[str] = None
    topics: Optional[List[str]] = Field(default_factory=list)
    full_text: Optional[str] = None
    origin_notebook_id: Optional[str] = None
    uploaded_by: Optional[Union[str, RecordID]] = None
    uploader_name: Optional[str] = None
    command: Optional[Union[str, RecordID]] = Field(
        default=None, description="Link to surreal-commands processing job"
    )

    @field_validator("command", mode="before")
    @classmethod
    def parse_command(cls, value):
        """Parse command field to ensure RecordID format"""
        if isinstance(value, str) and value:
            return ensure_record_id(value)
        return value

    @field_validator("id", mode="before")
    @classmethod
    def parse_id(cls, value):
        """Parse id field to handle both string and RecordID inputs"""
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return str(value) if value else None

    async def get_status(self) -> Optional[str]:
        """Get the processing status of the associated command"""
        if not self.command:
            return None

        try:
            from surreal_commands import get_command_status

            status = await get_command_status(str(self.command))
            return status.status if status else "unknown"
        except Exception as e:
            logger.warning(f"Failed to get command status for {self.command}: {e}")
            return "unknown"

    async def get_processing_progress(self) -> Optional[Dict[str, Any]]:
        """Get detailed processing information for the associated command"""
        if not self.command:
            return None

        try:
            from surreal_commands import get_command_status

            status_result = await get_command_status(str(self.command))
            if not status_result:
                return None

            # Extract execution metadata if available
            result = getattr(status_result, "result", None)
            execution_metadata = (
                result.get("execution_metadata", {}) if isinstance(result, dict) else {}
            )

            return {
                "status": status_result.status,
                "started_at": execution_metadata.get("started_at"),
                "completed_at": execution_metadata.get("completed_at"),
                "error": getattr(status_result, "error_message", None),
                "result": result,
            }
        except Exception as e:
            logger.warning(f"Failed to get command progress for {self.command}: {e}")
            return None

    async def get_context(
        self, context_size: Literal["short", "long"] = "short"
    ) -> Dict[str, Any]:
        insights_list = await self.get_insights()
        insights = [insight.model_dump() for insight in insights_list]
        if context_size == "long":
            return dict(
                id=self.id,
                title=self.title,
                insights=insights,
                full_text=self.full_text,
            )
        else:
            return dict(id=self.id, title=self.title, insights=insights)

    async def get_embedded_chunks(self) -> int:
        try:
            result = await repo_query(
                """
                select count() as chunks from source_embedding where source=$id GROUP ALL
                """,
                {"id": ensure_record_id(self.id)},
            )
            if len(result) == 0:
                return 0
            return result[0]["chunks"]
        except Exception as e:
            logger.error(f"Error fetching chunks count for source {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError(f"Failed to count chunks for source: {str(e)}")

    async def has_knowledge_graph(self) -> bool:
        try:
            result = await repo_query(
                """
                select count() as entities from kg_entity where source_id=$id GROUP ALL
                """,
                {"id": str(self.id)},
            )
            if len(result) == 0:
                return False
            return result[0]["entities"] > 0
        except Exception as e:
            logger.error(f"Error checking KG for source {self.id}: {str(e)}")
            return False

    async def get_insights(self) -> List[SourceInsight]:
        try:
            result = await repo_query(
                """
                SELECT * FROM source_insight WHERE source=$id
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [SourceInsight(**insight) for insight in result]
        except Exception as e:
            logger.error(f"Error fetching insights for source {self.id}: {str(e)}")
            logger.exception(e)
            raise DatabaseOperationError("Failed to fetch insights for source")

    async def add_to_notebook(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("reference", notebook_id)

    async def vectorize(self) -> str:
        """
        Submit vectorization as a background job using the embed_source command.

        This method leverages the job-based architecture to prevent HTTP connection
        pool exhaustion when processing large documents. The embed_source command:
        1. Detects content type from file path
        2. Chunks text using content-type aware splitter
        3. Generates all embeddings in batches
        4. Bulk inserts source_embedding records

        Returns:
            str: The command/job ID that can be used to track progress via the commands API

        Raises:
            ValueError: If source has no text to vectorize
            DatabaseOperationError: If job submission fails
        """
        logger.info(f"Submitting embed_source job for source {self.id}")

        try:
            if not self.full_text or not self.full_text.strip():
                raise ValueError(f"Source {self.id} has no text to vectorize")

            # Submit the embed_source command
            command_id = submit_command(
                "open_notebook",
                "embed_source",
                {"source_id": str(self.id)},
            )

            command_id_str = str(command_id)
            logger.info(
                f"Embed source job submitted for source {self.id}: "
                f"command_id={command_id_str}"
            )
            
            # Submitting KG extraction if enabled
            import os
            enable_kg = os.environ.get("ENABLE_KNOWLEDGE_GRAPH", "false").lower() == "true"
            if enable_kg:
                kg_command_id = submit_command(
                    "open_notebook",
                    "extract_knowledge_graph",
                    {"source_id": str(self.id)},
                )
                logger.info(f"Extract KG job submitted for source {self.id}: command_id={kg_command_id}")

            return command_id_str

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to submit embed_source job for source {self.id}: {e}"
            )
            logger.exception(e)
            raise DatabaseOperationError(e)

    async def add_insight(self, insight_type: str, content: str) -> Optional[str]:
        """
        Submit insight creation as an async command (fire-and-forget).

        Submits a create_insight command that handles database operations with
        automatic retry logic for transaction conflicts. The command also submits
        an embed_insight command for async embedding.

        This method returns immediately after submitting the command - it does NOT
        wait for the insight to be created. Use this for batch operations where
        throughput is more important than immediate confirmation.

        Args:
            insight_type: Type/category of the insight
            content: The insight content text

        Returns:
            command_id for optional tracking, or None if submission failed

        Raises:
            InvalidInputError: If insight_type or content is empty
        """
        if not insight_type or not content:
            raise InvalidInputError("Insight type and content must be provided")

        try:
            # Submit create_insight command (fire-and-forget)
            # Command handles retries internally for transaction conflicts
            command_id = submit_command(
                "open_notebook",
                "create_insight",
                {
                    "source_id": str(self.id),
                    "insight_type": insight_type,
                    "content": content,
                },
            )
            logger.info(
                f"Submitted create_insight command {command_id} for source {self.id} "
                f"(type={insight_type})"
            )
            return str(command_id)

        except Exception as e:
            logger.error(f"Error submitting create_insight for source {self.id}: {e}")
            return None

    def _prepare_save_data(self) -> dict:
        """Ensure record reference fields use RecordID format before database writes."""
        data = super()._prepare_save_data()

        # uploaded_by is stored as option<record<user>> in schema
        if data.get("uploaded_by") is not None:
            data["uploaded_by"] = ensure_record_id(data["uploaded_by"])

        # Ensure command field is RecordID format if not None
        if data.get("command") is not None:
            data["command"] = ensure_record_id(data["command"])

        return data

    async def delete(self) -> bool:
        """Delete source and clean up associated file, embeddings, and insights."""
        from open_notebook.domain.content_settings import ContentSettings
        settings = await ContentSettings.get_instance()
        
        # Clean up uploaded file if it exists and auto_delete_files is enabled
        if settings.auto_delete_files == "yes" and self.asset and self.asset.file_path:
            file_path = Path(self.asset.file_path)
            if file_path.exists():
                try:
                    os.unlink(file_path)
                    logger.info(f"Deleted file for source {self.id}: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to delete file {file_path} for source {self.id}: {e}. "
                        "Continuing with database deletion."
                    )
            else:
                logger.debug(
                    f"File {file_path} not found for source {self.id}, skipping cleanup"
                )
        elif self.asset and self.asset.file_path:
            logger.info(f"File deletion skipped for source {self.id} due to auto_delete_files setting")

        # Delete associated embeddings and insights to prevent orphaned records
        try:
            source_id = ensure_record_id(self.id)
            query = """
            DELETE source_embedding WHERE source = $source_id;
            DELETE source_insight WHERE source = $source_id;
            """
            
            if os.environ.get("ENABLE_KNOWLEDGE_GRAPH", "false").lower() == "true":
                query += """
                DELETE kg_entity WHERE source_id = $source_id_str;
                DELETE kg_relation WHERE source_id = $source_id_str;
                """
                
            await repo_transaction(
                query,
                {
                    "source_id": source_id,
                    "source_id_str": str(self.id)
                },
            )
            
            logger.debug(f"Deleted embeddings, insights, and KG data for source {self.id}")
        except Exception as e:
            logger.warning(
                f"Failed to delete associated data for source {self.id}: {e}. "
                "Continuing with source deletion."
            )

        # Call parent delete to remove database record
        return await super().delete()


class Note(ObjectModel):
    table_name: ClassVar[str] = "note"
    title: Optional[str] = None
    note_type: Optional[Literal["human", "ai"]] = None
    content: Optional[str] = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v):
        if v is not None and not v.strip():
            raise InvalidInputError("Note content cannot be empty")
        return v

    async def save(self) -> Optional[str]:
        """
        Save the note and submit embedding command.

        Overrides ObjectModel.save() to submit an async embed_note command
        after saving, instead of inline embedding.

        Returns:
            Optional[str]: The command_id if embedding was submitted, None otherwise
        """
        # Call parent save (without embedding)
        await super().save()

        # Submit embedding command (fire-and-forget) if note has content
        if self.id and self.content and self.content.strip():
            command_id = submit_command(
                "open_notebook",
                "embed_note",
                {"note_id": str(self.id)},
            )
            logger.debug(f"Submitted embed_note command {command_id} for {self.id}")
            return command_id

        return None

    async def add_to_notebook(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("artifact", notebook_id)

    def get_context(
        self, context_size: Literal["short", "long"] = "short"
    ) -> Dict[str, Any]:
        if context_size == "long":
            return dict(id=self.id, title=self.title, content=self.content)
        else:
            return dict(
                id=self.id,
                title=self.title,
                content=self.content[:100] if self.content else None,
            )


class ChatSession(ObjectModel):
    table_name: ClassVar[str] = "chat_session"
    nullable_fields: ClassVar[set[str]] = {"model_override"}
    title: Optional[str] = None
    model_override: Optional[str] = None

    async def relate_to_notebook(self, notebook_id: str) -> Any:
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("refers_to", notebook_id)

    async def relate_to_source(self, source_id: str) -> Any:
        if not source_id:
            raise InvalidInputError("Source ID must be provided")
        return await self.relate("refers_to", source_id)


async def text_search(
    keyword: str, results: int, source: bool = True, note: bool = True
):
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    try:
        search_results = await repo_query(
            """
            select *
            from fn::text_search($keyword, $results, $source, $note)
            """,
            {"keyword": keyword, "results": results, "source": source, "note": note},
        )
        return search_results
    except Exception as e:
        logger.error(f"Error performing text search: {str(e)}")
        logger.exception(e)
        raise DatabaseOperationError(e)


async def graph_search(keyword: str, results: int = 5):
    """
    Perform a hybrid Graph RAG search:
    1. Find entry entities via BM25 text search on name.
    2. Expand their relationships (1-hop) to gather subgraph context.
    """
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    try:
        # Step 1: Find entry points
        entry_nodes = await repo_query(
            """
            SELECT id, name, type, description, math::max([search::score(1), search::score(2)]) AS relevance
            FROM kg_entity
            WHERE name @1@ $keyword OR description @2@ $keyword
            GROUP BY id, name, type, description
            ORDER BY relevance DESC
            LIMIT $limit
            """,
            {"keyword": keyword, "limit": results},
        )
        
        if not entry_nodes:
            return []

        entry_ids = [node["id"] for node in entry_nodes]

        # Step 2: Expand the subgraph (1-hop traversal)
        subgraphs = await repo_query(
            """
            SELECT 
                id, 
                name, 
                type, 
                description,
                ->kg_relation->kg_entity.{id, name, type, description} AS outbound_nodes,
                ->kg_relation.{type, description} AS outbound_edges,
                <-kg_relation<-kg_entity.{id, name, type, description} AS inbound_nodes,
                <-kg_relation.{type, description} AS inbound_edges
            FROM $entry_ids
            """,
            {"entry_ids": entry_ids}
        )

        # Format the result into a clean text/structure for the LLM
        formatted_results = []
        for sg in subgraphs:
            context = f"Entity: [{sg.get('type', 'UNKNOWN')}] {sg.get('name', 'Unnamed')}"
            if sg.get('description'):
                context += f" (Details: {sg['description']})"
            context += "\nRelationships:\n"
            
            # Outbound
            out_edges = sg.get("outbound_edges", [])
            out_nodes = sg.get("outbound_nodes", [])
            for edge, node in zip(out_edges, out_nodes):
                edge_desc = f" ({edge.get('description')})" if edge and edge.get('description') else ""
                edge_type = edge.get('type', 'RELATES_TO') if edge else 'RELATES_TO'
                node_name = node.get('name', 'Unnamed') if node else 'Unnamed'
                node_type = node.get('type', 'UNKNOWN') if node else 'UNKNOWN'
                context += f"  - [{edge_type}]{edge_desc} -> [{node_type}] {node_name}\n"
                
            # Inbound
            in_edges = sg.get("inbound_edges", [])
            in_nodes = sg.get("inbound_nodes", [])
            for edge, node in zip(in_edges, in_nodes):
                edge_desc = f" ({edge.get('description')})" if edge and edge.get('description') else ""
                edge_type = edge.get('type', 'RELATES_TO') if edge else 'RELATES_TO'
                node_name = node.get('name', 'Unnamed') if node else 'Unnamed'
                node_type = node.get('type', 'UNKNOWN') if node else 'UNKNOWN'
                context += f"  - <- [{edge_type}]{edge_desc} - [{node_type}] {node_name}\n"
                
            formatted_results.append({
                "id": sg["id"],
                "title": f"Knowledge Graph Context for: {sg.get('name', '')}",
                "content": context,
                "type": "kg_subgraph"
            })
            
        return formatted_results

    except Exception as e:
        logger.error(f"Error performing graph search: {str(e)}")
        logger.exception(e)
        return []


async def vector_search(
    keyword: str,
    results: int,
    source: bool = True,
    note: bool = True,
    minimum_score=0.2,
):
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    try:
        from open_notebook.utils.embedding import generate_embedding

        # Use unified embedding function (handles chunking if query is very long)
        embed = await generate_embedding(keyword)
        search_results = await repo_query(
            """
            SELECT * FROM fn::vector_search($embed, $results, $source, $note, $minimum_score);
            """,
            {
                "embed": embed,
                "results": results,
                "source": source,
                "note": note,
                "minimum_score": minimum_score,
            },
        )
        return search_results
    except Exception as e:
        logger.error(f"Error performing vector search: {str(e)}")
        logger.exception(e)
        raise DatabaseOperationError(e)
