"""
Router for Learning Studio: AI-powered tools grounded in project sources.
Endpoints:
- POST /api/projects/{project_id}/studio/{tool_type}
- GET /api/projects/{project_id}/studio/{tool_type}
- GET /api/projects/{project_id}/studio  (list all generated artifacts)
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from database import get_db, get_utc_now
from services.auth import get_current_user
from services.embedder import load_index
from services.studio import (
    generate_summary,
    generate_flashcards,
    generate_quiz,
    generate_mindmap,
    generate_study_notes,
    generate_datatable,
)

router = APIRouter(prefix="/projects/{project_id}/studio", tags=["studio"])

VALID_TOOLS = {"summary", "flashcards", "quiz", "mindmap", "notes", "datatable"}

class StudioGenerateRequest(BaseModel):
    tool_type: Optional[str] = None
    force_refresh: bool = False

@router.get("")
async def list_studio_artifacts(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List all saved studio artifacts for the project."""
    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    artifacts = await db.studio_artifacts.find({"project_id": project_id}).to_list(length=20)
    return [
        {
            "id": a["_id"],
            "tool_type": a["tool_type"],
            "title": a.get("data", {}).get("title") or a["tool_type"].capitalize(),
            "updated_at": a["updated_at"],
        }
        for a in artifacts
    ]

@router.get("/{tool_type}")
async def get_studio_tool_content(
    project_id: str,
    tool_type: str,
    refresh: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retrieve or generate studio tool content for a project."""
    tool_clean = tool_type.lower().strip()
    if tool_clean not in VALID_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid studio tool '{tool_type}'. Valid tools are: {', '.join(sorted(VALID_TOOLS))}"
        )

    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Check cache if not forcing refresh
    if not refresh:
        cached = await db.studio_artifacts.find_one({
            "project_id": project_id,
            "tool_type": tool_clean,
        })
        if cached:
            return {
                "project_id": project_id,
                "tool_type": tool_clean,
                "data": cached["data"],
                "cached": True,
                "updated_at": cached["updated_at"],
            }

    # Load FAISS index & metadata to get chunks and sources
    index_id = project.get("index_id") or project_id
    try:
        _, meta = load_index(index_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="No sources have been indexed for this project yet. Please add sources before using Studio tools."
        )

    sources = meta.get("sources", [])
    chunks = meta.get("chunks", [])

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No indexed source content available. Please index at least one source."
        )

    # Generate according to tool_type
    try:
        if tool_clean == "summary":
            data = generate_summary(sources, chunks)
        elif tool_clean == "flashcards":
            cards = generate_flashcards(sources, chunks)
            data = {"flashcards": cards, "count": len(cards), "title": "Flashcards"}
        elif tool_clean == "quiz":
            questions = generate_quiz(sources, chunks)
            data = {"questions": questions, "count": len(questions), "title": "Interactive Quiz"}
        elif tool_clean == "mindmap":
            data = generate_mindmap(sources, chunks)
        elif tool_clean == "notes":
            data = generate_study_notes(sources, chunks)
        elif tool_clean == "datatable":
            data = generate_datatable(sources, chunks)
        else:
            raise HTTPException(status_code=400, detail="Unsupported tool type.")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate {tool_clean}: {str(e)}"
        )

    now = get_utc_now()
    doc_id = f"{project_id}_{tool_clean}"

    # Cache in MongoDB
    await db.studio_artifacts.update_one(
        {"_id": doc_id},
        {
            "$set": {
                "project_id": project_id,
                "user_id": current_user["_id"],
                "tool_type": tool_clean,
                "data": data,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    return {
        "project_id": project_id,
        "tool_type": tool_clean,
        "data": data,
        "cached": False,
        "updated_at": now,
    }

@router.post("/{tool_type}")
async def generate_studio_tool_content_post(
    project_id: str,
    tool_type: str,
    req: Optional[StudioGenerateRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """POST endpoint to generate/regenerate Studio tool content."""
    force_refresh = req.force_refresh if req else True
    return await get_studio_tool_content(
        project_id=project_id,
        tool_type=tool_type,
        refresh=force_refresh,
        current_user=current_user,
        db=db,
    )
