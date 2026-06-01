import os
from pathlib import Path
from typing import List, Optional

from dotenv import dotenv_values
from fastapi import APIRouter, Header, HTTPException, Query
from loguru import logger

from api.models import (
    NotebookAggregateRequest,
    NotebookCreate,
    NotebookDeletePreview,
    NotebookDeleteResponse,
    NotebookResponse,
    NotebookUpdate,
)
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


@router.get("/notebooks", response_model=List[NotebookResponse])
async def get_notebooks(
    archived: Optional[bool] = Query(None, description="Filter by archived status"),
    order_by: str = Query("updated desc", description="Order by field and direction"),
):
    """Get all notebooks with optional filtering and ordering."""
    try:
        # Validate order_by against allowlist to prevent SurrealQL injection
        allowed_fields = {"name", "created", "updated"}
        allowed_directions = {"asc", "desc"}

        parts = order_by.strip().lower().split()
        if len(parts) == 1:
            if parts[0] not in allowed_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid order_by field: '{order_by}'. Allowed fields: {', '.join(sorted(allowed_fields))}",
                )
            validated_order_by = parts[0]
        elif len(parts) == 2:
            if parts[0] not in allowed_fields or parts[1] not in allowed_directions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid order_by: '{order_by}'. Allowed fields: {', '.join(sorted(allowed_fields))}. Allowed directions: asc, desc",
                )
            validated_order_by = f"{parts[0]} {parts[1]}"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by format: '{order_by}'. Expected 'field' or 'field direction'",
            )

        # Build the query with counts
        query = f"""
            SELECT *,
            (SELECT VALUE out.name FROM aggregates WHERE in = $parent.id) as aggregated_notebooks,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-reference.in, ->aggregates.out<-reference.in).flatten()),
                    (hidden_sources ?? [])
                )
            ) as source_count,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-artifact.in, ->aggregates.out<-artifact.in).flatten()),
                    (hidden_notes ?? [])
                )
            ) as note_count
            FROM notebook
            ORDER BY {validated_order_by}
        """

        result = await repo_query(query)

        # Filter by archived status if specified
        if archived is not None:
            result = [nb for nb in result if nb.get("archived") == archived]

        return [
            NotebookResponse(
                id=str(nb.get("id", "")),
                name=nb.get("name", ""),
                description=nb.get("description", ""),
                archived=nb.get("archived", False),
                created=str(nb.get("created", "")),
                updated=str(nb.get("updated", "")),
                source_count=nb.get("source_count", 0),
                note_count=nb.get("note_count", 0),
                password=nb.get("password"),
                creator_name=nb.get("creator_name"),
                is_aggregated=nb.get("is_aggregated", False),
                aggregated_notebooks=nb.get("aggregated_notebooks", []),
            )
            for nb in result
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notebooks: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching notebooks: {str(e)}"
        )


@router.post("/notebooks", response_model=NotebookResponse)
async def create_notebook(notebook: NotebookCreate):
    """Create a new notebook."""
    try:
        new_notebook = Notebook(
            name=notebook.name,
            description=notebook.description,
            password=notebook.password,
            creator_name=notebook.creator_name,
        )
        await new_notebook.save()

        return NotebookResponse(
            id=new_notebook.id or "",
            name=new_notebook.name,
            description=new_notebook.description,
            archived=new_notebook.archived or False,
            created=str(new_notebook.created),
            updated=str(new_notebook.updated),
            source_count=0,  # New notebook has no sources
            note_count=0,  # New notebook has no notes
            password=new_notebook.password,
            creator_name=new_notebook.creator_name,
            is_aggregated=new_notebook.is_aggregated or False,
            aggregated_notebooks=[],
        )
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating notebook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error creating notebook: {str(e)}"
        )


@router.post("/notebooks/aggregate", response_model=NotebookResponse)
async def aggregate_notebooks(request: NotebookAggregateRequest):
    """Aggregate multiple notebooks into a new one."""
    try:
        # 1. Verify passwords and existence of all notebooks
        notebooks_to_aggregate = []
        for nb_id in request.notebook_ids:
            nb = await Notebook.get(nb_id)
            if not nb:
                raise HTTPException(status_code=404, detail=f"Notebook {nb_id} not found")
            
            if nb.password:
                provided_pwd = request.notebook_passwords.get(nb_id)
                if not provided_pwd or provided_pwd != nb.password:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Incorrect password for notebook: {nb.name}"
                    )
            notebooks_to_aggregate.append(nb)

        # 2. Create the new notebook
        new_notebook = Notebook(
            name=request.name,
            description=request.description,
            password=request.password,
            creator_name=request.creator_name,
            is_aggregated=True,
        )
        await new_notebook.save()

        # 3. Copy links for sources, notes, and chat sessions
        new_nb_id = ensure_record_id(new_notebook.id)
        
        for nb in notebooks_to_aggregate:
            old_nb_id = ensure_record_id(nb.id)
            
            await repo_query(
                "RELATE $new_nb_id->aggregates->$old_nb_id;",
                {"old_nb_id": old_nb_id, "new_nb_id": new_nb_id}
            )

        # 4. Return the new notebook
        query = """
            SELECT *,
            (SELECT VALUE out.name FROM aggregates WHERE in = $parent.id) as aggregated_notebooks,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-reference.in, ->aggregates.out<-reference.in).flatten()),
                    (hidden_sources ?? [])
                )
            ) as source_count,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-artifact.in, ->aggregates.out<-artifact.in).flatten()),
                    (hidden_notes ?? [])
                )
            ) as note_count
            FROM $notebook_id
        """
        result = await repo_query(query, {"notebook_id": new_nb_id})

        if result:
            nb_res = result[0]
            return NotebookResponse(
                id=str(nb_res.get("id", "")),
                name=nb_res.get("name", ""),
                description=nb_res.get("description", ""),
                archived=nb_res.get("archived", False),
                created=str(nb_res.get("created", "")),
                updated=str(nb_res.get("updated", "")),
                source_count=nb_res.get("source_count", 0),
                note_count=nb_res.get("note_count", 0),
                password=nb_res.get("password"),
                creator_name=nb_res.get("creator_name"),
                is_aggregated=nb_res.get("is_aggregated", False),
            )
            
        raise HTTPException(status_code=500, detail="Error retrieving created notebook")
        
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error aggregating notebooks: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error aggregating notebooks: {str(e)}"
        )


@router.get(
    "/notebooks/{notebook_id}/delete-preview", response_model=NotebookDeletePreview
)
async def get_notebook_delete_preview(notebook_id: str):
    """Get a preview of what will be deleted when this notebook is deleted."""
    try:
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        preview = await notebook.get_delete_preview()

        return NotebookDeletePreview(
            notebook_id=str(notebook.id),
            notebook_name=notebook.name,
            note_count=preview["note_count"],
            exclusive_source_count=preview["exclusive_source_count"],
            shared_source_count=preview["shared_source_count"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting delete preview for notebook {notebook_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching notebook deletion preview: {str(e)}",
        )


@router.get("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(notebook_id: str):
    """Get a specific notebook by ID."""
    try:
        # Query with counts for single notebook
        query = """
            SELECT *,
            (SELECT VALUE out.name FROM aggregates WHERE in = $parent.id) as aggregated_notebooks,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-reference.in, ->aggregates.out<-reference.in).flatten()),
                    (hidden_sources ?? [])
                )
            ) as source_count,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-artifact.in, ->aggregates.out<-artifact.in).flatten()),
                    (hidden_notes ?? [])
                )
            ) as note_count
            FROM $notebook_id
        """
        result = await repo_query(query, {"notebook_id": ensure_record_id(notebook_id)})

        if not result:
            raise HTTPException(status_code=404, detail="Notebook not found")

        nb = result[0]
        return NotebookResponse(
            id=str(nb.get("id", "")),
            name=nb.get("name", ""),
            description=nb.get("description", ""),
            archived=nb.get("archived", False),
            created=str(nb.get("created", "")),
            updated=str(nb.get("updated", "")),
            source_count=nb.get("source_count", 0),
            note_count=nb.get("note_count", 0),
            password=nb.get("password"),
            creator_name=nb.get("creator_name"),
            is_aggregated=nb.get("is_aggregated", False),
            aggregated_notebooks=nb.get("aggregated_notebooks", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching notebook: {str(e)}"
        )


@router.put("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(notebook_id: str, notebook_update: NotebookUpdate):
    """Update a notebook."""
    try:
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # Update only provided fields
        if notebook_update.name is not None:
            notebook.name = notebook_update.name
        if notebook_update.description is not None:
            notebook.description = notebook_update.description
        if notebook_update.archived is not None:
            notebook.archived = notebook_update.archived
        if notebook_update.password is not None:
            notebook.password = notebook_update.password
        if notebook_update.creator_name is not None:
            notebook.creator_name = notebook_update.creator_name

        await notebook.save()

        # Query with counts after update
        query = """
            SELECT *,
            (SELECT VALUE out.name FROM aggregates WHERE in = $parent.id) as aggregated_notebooks,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-reference.in, ->aggregates.out<-reference.in).flatten()),
                    (hidden_sources ?? [])
                )
            ) as source_count,
            array::len(
                array::difference(
                    array::distinct(array::concat(<-artifact.in, ->aggregates.out<-artifact.in).flatten()),
                    (hidden_notes ?? [])
                )
            ) as note_count
            FROM $notebook_id
        """
        result = await repo_query(query, {"notebook_id": ensure_record_id(notebook_id)})

        if result:
            nb = result[0]
            return NotebookResponse(
                id=str(nb.get("id", "")),
                name=nb.get("name", ""),
                description=nb.get("description", ""),
                archived=nb.get("archived", False),
                created=str(nb.get("created", "")),
                updated=str(nb.get("updated", "")),
                source_count=nb.get("source_count", 0),
                note_count=nb.get("note_count", 0),
                password=nb.get("password"),
                creator_name=nb.get("creator_name"),
                is_aggregated=nb.get("is_aggregated", False),
                aggregated_notebooks=nb.get("aggregated_notebooks", []),
            )

        # Fallback if query fails
        return NotebookResponse(
            id=notebook.id or "",
            name=notebook.name,
            description=notebook.description,
            archived=notebook.archived or False,
            created=str(notebook.created),
            updated=str(notebook.updated),
            source_count=0,
            note_count=0,
            password=notebook.password,
            creator_name=notebook.creator_name,
            is_aggregated=notebook.is_aggregated or False,
            aggregated_notebooks=notebook.get("aggregated_notebooks", []) if hasattr(notebook, "get") else [],
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error updating notebook: {str(e)}"
        )


@router.post("/notebooks/{notebook_id}/sources/{source_id}")
async def add_source_to_notebook(notebook_id: str, source_id: str):
    """Add an existing source to a notebook (create the reference)."""
    try:
        # Check if notebook exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        if notebook.is_aggregated:
            # If adding back to aggregated, we must unhide it
            await repo_query(
                "UPDATE $notebook_id SET hidden_sources = array::difference(hidden_sources, [$source_id])",
                {
                    "notebook_id": ensure_record_id(notebook_id),
                    "source_id": ensure_record_id(source_id),
                },
            )

        # Check if source exists
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Check if reference already exists (idempotency)
        existing_ref = await repo_query(
            "SELECT * FROM reference WHERE out = $source_id AND in = $notebook_id",
            {
                "notebook_id": ensure_record_id(notebook_id),
                "source_id": ensure_record_id(source_id),
            },
        )

        # If reference doesn't exist, create it
        if not existing_ref:
            await repo_query(
                "RELATE $source_id->reference->$notebook_id",
                {
                    "notebook_id": ensure_record_id(notebook_id),
                    "source_id": ensure_record_id(source_id),
                },
            )

        return {"message": "Source linked to notebook successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error linking source {source_id} to notebook {notebook_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error linking source to notebook: {str(e)}"
        )


@router.delete("/notebooks/{notebook_id}/sources/{source_id}")
async def remove_source_from_notebook(notebook_id: str, source_id: str):
    """Remove a source from a notebook (delete the reference)."""
    try:
        # Check if notebook exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        if notebook.is_aggregated:
            # If removing from aggregated, we must hide it so dynamic view stops showing it
            await repo_query(
                "UPDATE $notebook_id SET hidden_sources = array::union(hidden_sources, [$source_id])",
                {
                    "notebook_id": ensure_record_id(notebook_id),
                    "source_id": ensure_record_id(source_id),
                },
            )

        # Delete the reference record linking source to notebook
        await repo_query(
            "DELETE FROM reference WHERE out = $notebook_id AND in = $source_id",
            {
                "notebook_id": ensure_record_id(notebook_id),
                "source_id": ensure_record_id(source_id),
            },
        )

        return {"message": "Source removed from notebook successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error removing source {source_id} from notebook {notebook_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error removing source from notebook: {str(e)}"
        )


@router.delete("/notebooks/{notebook_id}", response_model=NotebookDeleteResponse)
async def delete_notebook(
    notebook_id: str,
    delete_exclusive_sources: bool = Query(
        False,
        description="Whether to delete sources that belong only to this notebook",
    ),
    x_notebook_password: Optional[str] = Header(None, alias="X-Notebook-Password")
):
    """
    Delete a notebook with cascade deletion.

    Always deletes all notes associated with the notebook.
    If delete_exclusive_sources is True, also deletes sources that belong only
    to this notebook (not linked to any other notebooks).
    """
    try:
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # Validate password if notebook is protected
        if notebook.password:
            # Check for master password
            master_pwd = os.environ.get("NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD")
            if not master_pwd:
                env_vals = dotenv_values(Path("frontend/.env.local"))
                master_pwd = env_vals.get("NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD")
                
            is_master = master_pwd and x_notebook_password == master_pwd
            
            if not is_master and (not x_notebook_password or x_notebook_password != notebook.password):
                raise HTTPException(status_code=403, detail="Incorrect notebook password")

        result = await notebook.delete(delete_exclusive_sources=delete_exclusive_sources)

        return NotebookDeleteResponse(
            message="Notebook deleted successfully",
            deleted_notes=result["deleted_notes"],
            deleted_sources=result["deleted_sources"],
            unlinked_sources=result["unlinked_sources"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notebook {notebook_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting notebook: {str(e)}"
        )
