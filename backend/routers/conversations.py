"""
Conversations & Messages Router: Persistent Multi-Turn AI Tutor Chat History with Project Scoping.
"""
import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo

from database import get_db, get_utc_now
from config import get_settings
from models import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationResponse,
    SendMessageRequest,
    MessageResponse,
    PaginatedMessagesResponse,
    SendChatMessageResponse,
)

from services.auth import get_current_user
from services.retriever import retrieve_per_source
from services.classifier import classify_sources
from services.synthesizer import synthesize_answer
from services.embedder import load_index
from services.hybrid_retrieval_service import hybrid_retrieve
from repositories.graph_repository import GraphRepository

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["conversations"])

async def get_conversation_with_ownership(
    chat_id: str,
    user_id: str,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Validate conversation existence and ownership."""
    conv = await db.conversations.find_one({"_id": chat_id})
    if not conv or conv.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conv

# ---------------------------------------------------------
# Project Scoped Conversation Endpoints
# ---------------------------------------------------------

@router.post("/projects/{project_id}/chats", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
@router.post("/projects/{project_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    project_id: str,
    req: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create a new chat conversation for a project."""
    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    chat_id = str(uuid.uuid4())
    now = get_utc_now()
    doc = {
        "_id": chat_id,
        "user_id": current_user["_id"],
        "project_id": project_id,
        "title": req.title or "New Conversation",
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "last_message_at": now,
    }

    await db.conversations.insert_one(doc)

    return ConversationResponse(
        _id=chat_id,
        user_id=current_user["_id"],
        project_id=project_id,
        title=doc["title"],
        status="active",
        created_at=now,
        updated_at=now,
        last_message_at=now,
        message_count=0,
    )

@router.get("/projects/{project_id}/chats", response_model=List[ConversationResponse])
@router.get("/projects/{project_id}/conversations", response_model=List[ConversationResponse])
async def list_project_conversations(
    project_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, alias="q"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List conversations for a project, sorted by most recent activity."""
    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    query: dict = {"project_id": project_id, "user_id": current_user["_id"]}
    if status_filter:
        query["status"] = status_filter
    if q and q.strip():
        query["title"] = {"$regex": q.strip(), "$options": "i"}

    cursor = db.conversations.find(query).sort("last_message_at", pymongo.DESCENDING)
    convs = await cursor.to_list(length=100)

    results = []
    for c in convs:
        msg_count = await db.messages.count_documents({"conversation_id": c["_id"]})
        results.append(
            ConversationResponse(
                _id=c["_id"],
                user_id=c["user_id"],
                project_id=c["project_id"],
                title=c["title"],
                status=c.get("status", "active"),
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                last_message_at=c.get("last_message_at", c["updated_at"]),
                message_count=msg_count,
            )
        )
    return results

# ---------------------------------------------------------
# Individual Conversation Endpoints
# ---------------------------------------------------------

@router.get("/chats/{chat_id}", response_model=ConversationResponse)
@router.get("/conversations/{chat_id}", response_model=ConversationResponse)
async def get_conversation(
    chat_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Fetch single conversation metadata."""
    conv = await get_conversation_with_ownership(chat_id, current_user["_id"], db)
    msg_count = await db.messages.count_documents({"conversation_id": chat_id})
    return ConversationResponse(
        _id=conv["_id"],
        user_id=conv["user_id"],
        project_id=conv["project_id"],
        title=conv["title"],
        status=conv.get("status", "active"),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        last_message_at=conv.get("last_message_at", conv["updated_at"]),
        message_count=msg_count,
    )

@router.get("/chats/{chat_id}/messages", response_model=PaginatedMessagesResponse)
@router.get("/conversations/{chat_id}/messages", response_model=PaginatedMessagesResponse)
async def get_conversation_messages(
    chat_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Fetch chronological message history for a conversation."""
    await get_conversation_with_ownership(chat_id, current_user["_id"], db)

    total = await db.messages.count_documents({"conversation_id": chat_id})
    cursor = db.messages.find({"conversation_id": chat_id}).sort("created_at", pymongo.ASCENDING).limit(limit)
    raw_msgs = await cursor.to_list(length=limit)

    messages = [
        MessageResponse(
            _id=m["_id"],
            user_id=m["user_id"],
            project_id=m["project_id"],
            conversation_id=m["conversation_id"],
            role=m["role"],
            content=m["content"],
            created_at=m["created_at"],
            classification=m.get("classification"),
            source_summaries=m.get("source_summaries"),
            retrieved_chunks=m.get("retrieved_chunks"),
            retrieval_metadata=m.get("retrieval_metadata"),
        )
        for m in raw_msgs
    ]

    return PaginatedMessagesResponse(
        messages=messages,
        total=total,
        conversation_id=chat_id,
    )

@router.post("/chats/{chat_id}/message", response_model=SendChatMessageResponse)
async def send_conversation_message(
    chat_id: str,
    req: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Submit question in conversation:
    1. Validate ownership of conversation & project
    2. Persist user question in MongoDB
    3. Load project active sources & FAISS index
    4. Retrieve multi-source chunks and run classification & synthesis with conversation context
    5. Persist assistant response with citations
    6. Auto-generate conversation title from first question if default
    """
    conv = await get_conversation_with_ownership(chat_id, current_user["_id"], db)
    project_id = conv["project_id"]
    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Associated project not found.")

    question = req.text
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    now = get_utc_now()
    user_msg_id = str(uuid.uuid4())
    user_doc = {
        "_id": user_msg_id,
        "user_id": current_user["_id"],
        "project_id": project_id,
        "conversation_id": chat_id,
        "role": "user",
        "content": question,
        "created_at": now,
    }
    await db.messages.insert_one(user_doc)

    # Load FAISS index & metadata
    index_id = project["index_id"]
    try:
        _, meta = load_index(index_id)
    except FileNotFoundError:
        # No sources indexed yet
        assistant_doc = {
            "_id": str(uuid.uuid4()),
            "user_id": current_user["_id"],
            "project_id": project_id,
            "conversation_id": chat_id,
            "role": "assistant",
            "content": "No sources have been indexed for this project yet. Please add and index at least one source URL in the project panel before asking questions.",
            "created_at": get_utc_now(),
        }
        await db.messages.insert_one(assistant_doc)
        return SendChatMessageResponse(
            user_message=MessageResponse(**user_doc),
            assistant_message=MessageResponse(**assistant_doc),
        )

    active_sources = meta.get("sources", [])
    if not active_sources:
        assistant_doc = {
            "_id": str(uuid.uuid4()),
            "user_id": current_user["_id"],
            "project_id": project_id,
            "conversation_id": chat_id,
            "role": "assistant",
            "content": "No active sources found for this project. Please add and index source URLs.",
            "created_at": get_utc_now(),
        }
        await db.messages.insert_one(assistant_doc)
        return SendChatMessageResponse(
            user_message=MessageResponse(**user_doc),
            assistant_message=MessageResponse(**assistant_doc),
        )


    # Determine retrieval mode from request override or backend settings
    app_settings = get_settings()
    requested_mode = (req.retrieval_mode or app_settings.rag_mode or "vector").lower().strip()
    rag_mode = "hybrid" if requested_mode == "hybrid" else "vector"
    retrieval_metadata = None

    # Retrieval: use hybrid service which handles both vector and hybrid modes
    try:
        graph_repo = GraphRepository(db) if rag_mode == "hybrid" else None
        retrieval_result = await hybrid_retrieve(
            index_id=index_id,
            question=question,
            project_id=project_id,
            user_id=current_user["_id"],
            repo=graph_repo,
            rag_mode=rag_mode,
        )
        per_source = retrieval_result["per_source"]
        retrieval_metadata = retrieval_result.get("retrieval_metadata")
    except Exception as retrieval_exc:
        logger.warning(f"[conversations] Hybrid retrieval failed, falling back to vector-only: {retrieval_exc}")
        per_source = retrieve_per_source(session_id=index_id, question=question)
        retrieval_metadata = {"retrieval_mode": "vector", "fallback": True}

    # Classify relationship (Groq Call #1)
    classification_raw = classify_sources(question=question, per_source_chunks=per_source)

    # Fetch bounded previous conversation messages for multi-turn tutoring context
    prev_cursor = db.messages.find({"conversation_id": chat_id}).sort("created_at", pymongo.ASCENDING).limit(6)
    prev_history = await prev_cursor.to_list(length=6)

    # Synthesize answer (Groq Call #2)
    answer = synthesize_answer(
        question=question,
        per_source_chunks=per_source,
        classification=classification_raw,
        conversation_history=prev_history,
    )

    # Build source summaries
    source_meta = {s["source_id"]: s for s in active_sources}
    per_src_summary = classification_raw.get("per_source_summary", {})
    source_summaries = []

    for s in active_sources:
        sid = s["source_id"]
        summary = per_src_summary.get(sid)
        if not summary:
            match = next((v for k, v in per_src_summary.items() if sid.lower() in k.lower() or k.lower() in sid.lower()), None)
            if match:
                summary = match
            elif sid in per_source and per_source[sid]:
                summary = per_source[sid][0]["text"][:160] + "..."
            else:
                summary = "Source indexed but contains no direct answer to this specific question."

        source_summaries.append({
            "source_id": sid,
            "url": s.get("url") or s.get("resolved_url") or s.get("original_url", ""),
            "title": s.get("title", sid),
            "summary": summary,
        })

    retrieved_chunks_out = {}
    for sid, chunks in per_source.items():
        retrieved_chunks_out[sid] = [
            {
                "source_id": c.get("source_id", sid),
                "url": c.get("url") or c.get("source_url", ""),
                "title": c.get("title") or c.get("source_title", sid),
                "text": c["text"],
                "score": c["score"],
                "retrieval_method": c.get("retrieval_method", "vector"),
            }
            for c in chunks
        ]

    # Persist assistant response
    assistant_msg_id = str(uuid.uuid4())
    assistant_time = get_utc_now()
    assistant_doc = {
        "_id": assistant_msg_id,
        "user_id": current_user["_id"],
        "project_id": project_id,
        "conversation_id": chat_id,
        "role": "assistant",
        "content": answer,
        "created_at": assistant_time,
        "classification": classification_raw,
        "source_summaries": source_summaries,
        "retrieved_chunks": retrieved_chunks_out,
        "retrieval_metadata": retrieval_metadata,
    }
    await db.messages.insert_one(assistant_doc)

    # Auto-generate title if default
    updates: dict = {"last_message_at": assistant_time, "updated_at": assistant_time}
    if conv.get("title") in ("New Conversation", "", None):
        auto_title = question[:45] + ("..." if len(question) > 45 else "")
        updates["title"] = auto_title

    await db.conversations.update_one({"_id": chat_id}, {"$set": updates})

    return SendChatMessageResponse(
        user_message=MessageResponse(**user_doc),
        assistant_message=MessageResponse(
            _id=assistant_msg_id,
            user_id=current_user["_id"],
            project_id=project_id,
            conversation_id=chat_id,
            role="assistant",
            content=answer,
            created_at=assistant_time,
            classification=classification_raw,
            source_summaries=source_summaries,
            retrieved_chunks=retrieved_chunks_out,
            retrieval_metadata=retrieval_metadata,
        ),
    )


@router.patch("/chats/{chat_id}", response_model=ConversationResponse)
@router.patch("/conversations/{chat_id}", response_model=ConversationResponse)
async def update_conversation(
    chat_id: str,
    req: ConversationUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Rename conversation or change status (active/archived)."""
    conv = await get_conversation_with_ownership(chat_id, current_user["_id"], db)
    updates = {}
    if req.title is not None and req.title.strip():
        updates["title"] = req.title.strip()
    if req.status is not None:
        updates["status"] = req.status

    if updates:
        updates["updated_at"] = get_utc_now()
        await db.conversations.update_one({"_id": chat_id}, {"$set": updates})
        conv.update(updates)

    msg_count = await db.messages.count_documents({"conversation_id": chat_id})
    return ConversationResponse(
        _id=conv["_id"],
        user_id=conv["user_id"],
        project_id=conv["project_id"],
        title=conv["title"],
        status=conv.get("status", "active"),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        last_message_at=conv.get("last_message_at", conv["updated_at"]),
        message_count=msg_count,
    )

@router.post("/chats/{chat_id}/archive", response_model=ConversationResponse)
@router.post("/conversations/{chat_id}/archive", response_model=ConversationResponse)
async def archive_conversation(
    chat_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Archive a conversation."""
    return await update_conversation(
        chat_id,
        ConversationUpdateRequest(status="archived"),
        current_user,
        db,
    )

@router.delete("/chats/{chat_id}")
@router.delete("/conversations/{chat_id}")
async def delete_conversation(
    chat_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Delete conversation and all its messages."""
    await get_conversation_with_ownership(chat_id, current_user["_id"], db)
    await db.messages.delete_many({"conversation_id": chat_id})
    await db.conversations.delete_one({"_id": chat_id})
    return {"message": "Conversation deleted successfully."}
