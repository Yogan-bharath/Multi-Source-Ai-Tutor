"""
POST /api/chat
Accepts session_id + question.
Runs per-source retrieval → classification → synthesis → returns structured response.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from services.retriever import retrieve_per_source
from services.classifier import classify_sources
from services.synthesizer import synthesize_answer
from services.embedder import load_index

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    question: str
    top_k: Optional[int] = None


class ChunkInfo(BaseModel):
    source_id: str
    url: str
    title: str
    text: str
    score: float


class SourceSummary(BaseModel):
    source_id: str
    url: str
    title: str
    summary: str  # from classifier per_source_summary


class ClassificationResult(BaseModel):
    classification: str  # agree | partial | conflict
    confidence: float
    reasoning: str
    key_differences: str


class ChatResponse(BaseModel):
    answer: str
    classification: ClassificationResult
    source_summaries: List[SourceSummary]
    retrieved_chunks: Dict[str, List[ChunkInfo]]
    session_id: str
    question: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Validate session exists
    try:
        _, meta = load_index(req.session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found. Please ingest first.")

    active_sources = meta.get("sources", [])
    if not active_sources:
        raise HTTPException(status_code=400, detail="No active sources found in this session.")

    # Step 1: Per-source retrieval
    per_source = retrieve_per_source(
        session_id=req.session_id,
        question=req.question,
        top_k=req.top_k,
    )

    # Step 2: Classification (Groq call #1)
    classification_raw = classify_sources(
        question=req.question,
        per_source_chunks=per_source,
    )

    # Step 3: Synthesis (Groq call #2)
    answer = synthesize_answer(
        question=req.question,
        per_source_chunks=per_source,
        classification=classification_raw,
    )

    # Build source summaries from classification output
    source_meta = {s["source_id"]: s for s in active_sources}
    per_src_summary = classification_raw.get("per_source_summary", {})
    source_summaries = []

    for s in active_sources:
        sid = s["source_id"]
        summary = per_src_summary.get(sid)
        if not summary:
            # Fuzzy match keys in per_source_summary
            match = next((v for k, v in per_src_summary.items() if sid.lower() in k.lower() or k.lower() in sid.lower()), None)
            if match:
                summary = match
            elif sid in per_source and per_source[sid]:
                summary = per_source[sid][0]["text"][:160] + "..."
            else:
                summary = "Source indexed but contains no direct answer to this specific question."

        source_summaries.append(
            SourceSummary(
                source_id=sid,
                url=s.get("url") or s.get("resolved_url") or s.get("original_url", ""),
                title=s.get("title", sid),
                summary=summary,
            )
        )

    # Flatten chunks for response
    retrieved_chunks_out = {}
    for sid, chunks in per_source.items():
        retrieved_chunks_out[sid] = [
            ChunkInfo(
                source_id=c.get("source_id", sid),
                url=c.get("url") or c.get("source_url", ""),
                title=c.get("title") or c.get("source_title", sid),
                text=c["text"],
                score=c["score"],
            )
            for c in chunks
        ]

    return ChatResponse(
        answer=answer,
        classification=ClassificationResult(
            classification=classification_raw.get("classification", "agree"),
            confidence=float(classification_raw.get("confidence", 0.8)),
            reasoning=classification_raw.get("reasoning", ""),
            key_differences=classification_raw.get("key_differences", "None"),
        ),
        source_summaries=source_summaries,
        retrieved_chunks=retrieved_chunks_out,
        session_id=req.session_id,
        question=req.question,
    )
