"""
Graph Router: Project-scoped Knowledge Graph inspection and status endpoints.
Strictly authenticated and scoped to current_user and project_id.
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_db
from models import ProjectResponse
from services.auth import get_current_user
from repositories.graph_repository import GraphRepository
from schemas.graph_schemas import (
    GraphEntity,
    GraphRelationship,
    GraphStatusResponse,
    GraphSummaryResponse,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/projects/{project_id}/graph", tags=["graph"])


async def validate_project_access(
    project_id: str,
    user_id: str,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Validate project existence and verify ownership."""
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


@router.get("/status", response_model=List[GraphStatusResponse])
async def get_project_graph_status(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get the graph extraction status for all sources in this project."""
    await validate_project_access(project_id, current_user["_id"], db)
    repo = GraphRepository(db)
    cursor = db.graph_processing_status.find({
        "user_id": current_user["_id"],
        "project_id": project_id,
    })
    statuses = await cursor.to_list(length=100)
    return [GraphStatusResponse(**s) for s in statuses]


@router.get("/summary", response_model=GraphSummaryResponse)
async def get_project_graph_summary(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get entity count, relationship count, and entity types in this project's graph."""
    await validate_project_access(project_id, current_user["_id"], db)
    repo = GraphRepository(db)
    counts = await repo.count_graph_elements(current_user["_id"], project_id)
    return GraphSummaryResponse(
        project_id=project_id,
        entity_count=counts["entity_count"],
        relationship_count=counts["relationship_count"],
        entity_types=counts["entity_types"],
    )


@router.get("/entities", response_model=List[GraphEntity])
async def list_project_entities(
    project_id: str,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List knowledge graph entities extracted for this project."""
    await validate_project_access(project_id, current_user["_id"], db)
    repo = GraphRepository(db)
    entities = await repo.get_entities_by_project(
        user_id=current_user["_id"],
        project_id=project_id,
        entity_type=entity_type,
        limit=limit,
    )
    return entities


@router.get("/relationships", response_model=List[GraphRelationship])
async def list_project_relationships(
    project_id: str,
    entity_id: Optional[str] = Query(None, description="Filter by connected entity ID"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List knowledge graph relationships extracted for this project."""
    await validate_project_access(project_id, current_user["_id"], db)
    repo = GraphRepository(db)
    relationships = await repo.get_relationships_for_project(
        user_id=current_user["_id"],
        project_id=project_id,
        entity_id=entity_id,
        limit=limit,
    )
    return relationships
