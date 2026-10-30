"""
Projects Router: Create, List, Retrieve, Update, and Delete Learning Projects with ownership validation.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo

from database import get_db, get_utc_now
from models import ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse
from services.auth import get_current_user
from services.embedder import delete_index_files
from repositories.graph_repository import GraphRepository

router = APIRouter(prefix="/projects", tags=["projects"])

async def get_project_with_ownership(
    project_id: str,
    user_id: str,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Validate project existence and strict user ownership."""
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    if project.get("user_id") != user_id:
        # Avoid leaking whether another user's project exists
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create a new learning project for the authenticated user."""
    project_id = str(uuid.uuid4())
    index_id = f"proj_{project_id[:12]}"
    now = get_utc_now()

    doc = {
        "_id": project_id,
        "user_id": current_user["_id"],
        "name": req.name.strip(),
        "description": (req.description or "").strip(),
        "index_id": index_id,
        "created_at": now,
        "updated_at": now,
    }

    await db.projects.insert_one(doc)

    return ProjectResponse(
        _id=project_id,
        user_id=current_user["_id"],
        name=doc["name"],
        description=doc["description"],
        index_id=index_id,
        created_at=now,
        updated_at=now,
        source_count=0,
        conversation_count=0,
    )

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    q: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List all projects belonging to the current user, optionally filtered by name search, ordered by recent activity."""
    query = {"user_id": current_user["_id"]}
    if q and q.strip():
        import re
        query["name"] = {"$regex": re.escape(q.strip()), "$options": "i"}

    cursor = db.projects.find(query).sort("updated_at", pymongo.DESCENDING)
    projects = await cursor.to_list(length=100)

    results = []
    for p in projects:
        # Count active sources
        src_cnt = await db.sources.count_documents({
            "project_id": p["_id"],
            "status": "success",
        })
        # Count conversations
        conv_cnt = await db.conversations.count_documents({
            "project_id": p["_id"],
        })
        results.append(
            ProjectResponse(
                _id=p["_id"],
                user_id=p["user_id"],
                name=p["name"],
                description=p.get("description", ""),
                index_id=p["index_id"],
                created_at=p["created_at"],
                updated_at=p["updated_at"],
                source_count=src_cnt,
                conversation_count=conv_cnt,
            )
        )
    return results

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retrieve details for a specific project."""
    project = await get_project_with_ownership(project_id, current_user["_id"], db)
    src_cnt = await db.sources.count_documents({
        "project_id": project_id,
        "status": "success",
    })
    conv_cnt = await db.conversations.count_documents({
        "project_id": project_id,
    })
    return ProjectResponse(
        _id=project["_id"],
        user_id=project["user_id"],
        name=project["name"],
        description=project.get("description", ""),
        index_id=project["index_id"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
        source_count=src_cnt,
        conversation_count=conv_cnt,
    )

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Rename or update project description."""
    project = await get_project_with_ownership(project_id, current_user["_id"], db)
    updates = {}
    if req.name is not None and req.name.strip():
        updates["name"] = req.name.strip()
    if req.description is not None:
        updates["description"] = req.description.strip()

    if updates:
        updates["updated_at"] = get_utc_now()
        await db.projects.update_one({"_id": project_id}, {"$set": updates})
        project.update(updates)

    src_cnt = await db.sources.count_documents({"project_id": project_id, "status": "success"})
    conv_cnt = await db.conversations.count_documents({"project_id": project_id})

    return ProjectResponse(
        _id=project["_id"],
        user_id=project["user_id"],
        name=project["name"],
        description=project.get("description", ""),
        index_id=project["index_id"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
        source_count=src_cnt,
        conversation_count=conv_cnt,
    )

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Cascading delete of project and all associated resources:
    - Verifies ownership strictly before destructive ops
    - Cleans up FAISS files on disk safely
    - Removes studio_artifacts
    - Removes messages and conversations
    - Removes sources
    - Removes GraphRAG entities, relationships, and processing statuses
    - Removes project document
    - Is idempotent and retryable if partial failure occurs
    """
    project = await get_project_with_ownership(project_id, current_user["_id"], db)
    index_id = project.get("index_id")

    # 1. Clean up FAISS files on disk safely
    if index_id:
        try:
            delete_index_files(index_id)
        except Exception as e:
            pass

    # 2. Delete messages in all conversations belonging to project
    await db.messages.delete_many({"project_id": project_id})

    # 3. Delete conversations
    await db.conversations.delete_many({"project_id": project_id})

    # 4. Delete studio artifacts
    await db.studio_artifacts.delete_many({"project_id": project_id})

    # 5. Delete sources
    await db.sources.delete_many({"project_id": project_id})

    # 6. Delete graph data (entities, relationships, processing status)
    try:
        graph_repo = GraphRepository(db)
        await graph_repo.delete_project_graph(project_id, current_user["_id"])
    except Exception:
        pass

    # 7. Delete project document verifying ownership
    await db.projects.delete_one({"_id": project_id, "user_id": current_user["_id"]})

    return {"message": "Project and all associated data deleted successfully."}

@router.get("/{project_id}/sources")
async def get_project_sources(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retrieve all indexed sources for a project, including rich metadata."""
    await get_project_with_ownership(project_id, current_user["_id"], db)
    cursor = db.sources.find({"project_id": project_id}).sort("created_at", pymongo.ASCENDING)
    sources = await cursor.to_list(length=100)
    return [
        {
            "id": str(s["_id"]),
            "_id": str(s["_id"]),
            "source_type": s.get("source_type", "url"),
            "source_id": s.get("source_id") if s.get("source_id") else str(s["_id"]),
            "url": s.get("original_url") or s.get("resolved_url", ""),
            "original_url": s.get("original_url"),
            "resolved_url": s.get("resolved_url"),
            "title": s.get("title", ""),
            "status": s.get("status", "success"),
            "chunk_count": s.get("chunks_indexed", 0),
            "chunks_indexed": s.get("chunks_indexed", 0),
            "char_count": s.get("char_count", 0),
            "truncated": s.get("truncated", False),
            "error": s.get("error"),
            "video_id": s.get("video_id"),
            "channel_name": s.get("channel_name"),
            "thumbnail_url": s.get("thumbnail_url"),
            "duration": s.get("duration"),
            "duration_formatted": s.get("duration_formatted"),
            "updated_at": s.get("updated_at"),
            "created_at": s.get("created_at"),
        }
        for s in sources
    ]

