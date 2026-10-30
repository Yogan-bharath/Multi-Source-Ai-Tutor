"""
POST /api/ingest
Accepts multiple source URLs + topic name.
Supports project-based persistence in MongoDB with ownership checks,
as well as backward-compatible session indexing.
"""
import uuid
from typing import Optional, List
import io
import pypdf
from fastapi import APIRouter, HTTPException, Depends, Request, status, UploadFile, File, Form
from pydantic import BaseModel, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo


from services.scraper import scrape_multiple_sources, normalize_url, validate_url
from services.embedder import (
    build_index,
    append_to_index,
    remove_source_from_index,
    load_index,
    get_next_source_label,
    _chunk_text,
)
from services.discovery import discover_related_urls
from services.auth import get_optional_current_user, get_current_user
from services.graph_extraction_service import extract_and_store_graph
from repositories.graph_repository import GraphRepository
from database import get_db, get_utc_now
from config import get_settings
import logging

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("uvicorn.error")


class IngestRequest(BaseModel):
    project_id: Optional[str] = None
    source_urls: Optional[List[str]] = None
    topic_url: Optional[str] = None  # backward compatibility
    topic_name: Optional[str] = ""
    session_id: Optional[str] = None  # for retrying or adding to existing session
    n_related: Optional[int] = 0

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls_count(cls, v):
        if v is not None:
            non_empty = [u.strip() for u in v if u and u.strip()]
            if len(non_empty) > settings.max_sources_per_request:
                raise ValueError(f"Maximum of {settings.max_sources_per_request} sources allowed per indexing request.")
        return v


class SourceResult(BaseModel):
    source_id: str = ""
    url: str = ""  # alias for backward compatibility
    original_url: str
    resolved_url: Optional[str] = None
    title: str = ""
    status: str  # "success" | "failed"
    chunk_count: int = 0
    chunks_indexed: int = 0  # alias
    char_count: int = 0
    truncated: bool = False
    error: Optional[str] = None


class IngestResponse(BaseModel):
    session_id: str
    project_id: Optional[str] = None
    topic_name: str
    total_sources: int
    successful_sources: int
    failed_sources: int
    total_chunks_indexed: int
    total_submitted: int
    successful_count: int
    failed_count: int
    total_chunks: int
    sources: List[SourceResult]
    results: List[SourceResult]


class RemoveSourceRequest(BaseModel):
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    source_id: str
    original_url: Optional[str] = None


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Ingest up to 5 sources:
    - If project_id provided, validates ownership and binds to project's stable FAISS index
    - Persists source records in MongoDB sources collection
    - Enforces hard 5-source limit and SSRF protections
    """
    raw_urls = []
    if req.source_urls is not None:
        raw_urls = [u.strip() for u in req.source_urls if u and u.strip()]
    elif req.topic_url:
        raw_urls = [req.topic_url.strip()]
        if req.n_related and req.n_related > 0:
            try:
                related = discover_related_urls(
                    primary_url=req.topic_url,
                    topic_hint=req.topic_name or "",
                    n=min(req.n_related, settings.max_sources_per_request - 1),
                )
                raw_urls.extend([r["url"] for r in related])
            except Exception as e:
                print(f"[ingest] Discovery error: {e}")

    if not raw_urls:
        raise HTTPException(
            status_code=400,
            detail="Please enter at least one source URL."
        )

    if len(raw_urls) > settings.max_sources_per_request:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {settings.max_sources_per_request} sources allowed per indexing request."
        )

    # Pre-validate schemes
    for u in raw_urls:
        is_val, _, err = validate_url(u)
        if not is_val and ("http://" not in u.lower() and "https://" not in u.lower() and "://" in u):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported URL scheme: {err or 'Only HTTP and HTTPS URLs are supported.'}"
            )

    # Determine index target: Project or Session
    project = None
    if req.project_id:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to modify project sources.",
            )
        project = await db.projects.find_one({"_id": req.project_id, "user_id": current_user["_id"]})
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        index_target_id = project["index_id"]
        session_id = req.project_id
        topic_hint = req.topic_name.strip() if req.topic_name else project["name"]
    else:
        index_target_id = req.session_id or str(uuid.uuid4())
        session_id = index_target_id
        topic_hint = req.topic_name.strip() if req.topic_name else ""

    # Check if index already exists
    is_append = False
    existing_sources = []
    existing_urls = []
    existing_sids = []

    try:
        _, meta = load_index(index_target_id)
        existing_sources = meta.get("sources", [])
        existing_urls = [s.get("url", "") for s in existing_sources] + [s.get("original_url", "") for s in existing_sources]
        existing_sids = [s.get("source_id", "") for s in existing_sources]
        if not topic_hint and meta.get("topic_name"):
            topic_hint = meta["topic_name"]
        is_append = True
    except FileNotFoundError:
        pass

    print(f"[ingest] Processing {len(raw_urls)} sources for index {index_target_id} (append={is_append})...")

    scraped_results = scrape_multiple_sources(raw_urls, existing_urls=existing_urls)

    successful_to_index = []
    results_out: List[SourceResult] = []
    now = get_utc_now()

    for item in scraped_results:
        orig_url = item["original_url"]
        res_url = item.get("resolved_url") or orig_url
        title = item.get("title") or orig_url
        is_trunc = item.get("truncated", False)

        if item["status"] == "success" and item["text"]:
            next_label = get_next_source_label(existing_sids)
            sid = f"Source {next_label}"
            existing_sids.append(sid)

            chunks = _chunk_text(item["text"], settings.chunk_size, settings.chunk_overlap)
            if len(chunks) > settings.max_chunks_per_source:
                chunks = chunks[:settings.max_chunks_per_source]
                is_trunc = True
            chunk_count = len(chunks)

            src_entry = {
                "source_id": sid,
                "url": res_url,
                "original_url": orig_url,
                "resolved_url": res_url,
                "title": title,
                "text": item["text"],
                "char_count": item["char_count"],
                "chunk_count": chunk_count,
                "truncated": is_trunc,
            }
            successful_to_index.append(src_entry)

            results_out.append(SourceResult(
                source_id=sid,
                url=res_url,
                original_url=orig_url,
                resolved_url=res_url,
                title=title,
                status="success",
                chunk_count=chunk_count,
                chunks_indexed=chunk_count,
                char_count=item["char_count"],
                truncated=is_trunc,
                error=None,
            ))

            # Persist in MongoDB if project exists
            if project and current_user:
                source_update = {
                    "user_id": current_user["_id"],
                    "project_id": project["_id"],
                    "source_id": sid,
                    "original_url": orig_url,
                    "resolved_url": res_url,
                    "title": title,
                    "status": "success",
                    "chunks_indexed": chunk_count,
                    "truncated": is_trunc,
                    "error": None,
                    "updated_at": now,
                }
                await db.sources.update_one(
                    {"project_id": project["_id"], "original_url": orig_url},
                    {
                        "$set": source_update,
                        "$setOnInsert": {
                            "_id": str(uuid.uuid4()),
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )
        else:
            failed_id = f"failed_{uuid.uuid4().hex[:8]}"
            results_out.append(SourceResult(
                source_id=failed_id,
                url=res_url,
                original_url=orig_url,
                resolved_url=item.get("resolved_url"),
                title=title,
                status="failed",
                chunk_count=0,
                chunks_indexed=0,
                char_count=0,
                truncated=False,
                error=item.get("error") or "Unknown error while indexing source.",
            ))

            if project and current_user:
                existing_src = await db.sources.find_one({"project_id": project["_id"], "original_url": orig_url})
                assigned_sid = (existing_src.get("source_id") if existing_src and existing_src.get("source_id") else None) or failed_id
                failed_update = {
                    "user_id": current_user["_id"],
                    "project_id": project["_id"],
                    "source_id": assigned_sid,
                    "original_url": orig_url,
                    "resolved_url": item.get("resolved_url"),
                    "title": title,
                    "status": "failed",
                    "chunks_indexed": 0,
                    "truncated": False,
                    "error": item.get("error"),
                    "updated_at": now,
                }
                await db.sources.update_one(
                    {"project_id": project["_id"], "original_url": orig_url},
                    {
                        "$set": failed_update,
                        "$setOnInsert": {
                            "_id": str(uuid.uuid4()),
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )


    # Persist in FAISS
    if successful_to_index:
        if is_append:
            meta = append_to_index(successful_to_index, index_target_id, topic_hint)
        else:
            meta = build_index(successful_to_index, index_target_id, topic_hint)
        total_chunks = len(meta.get("chunks", []))
    else:
        if is_append:
            _, meta = load_index(index_target_id)
            total_chunks = len(meta.get("chunks", []))
        else:
            meta = {"chunks": [], "sources": []}
            total_chunks = 0

    if project:
        await db.projects.update_one({"_id": project["_id"]}, {"$set": {"updated_at": now}})

    # Non-blocking graph extraction for newly ingested sources
    if project and current_user and successful_to_index and settings.graph_rag_enabled:
        try:
            graph_repo = GraphRepository(db)
            for src_entry in successful_to_index:
                src_chunks = _chunk_text(src_entry["text"], settings.chunk_size, settings.chunk_overlap)
                chunk_dicts = [
                    {"text": c, "chunk_id": f"{src_entry['source_id']}:chunk_{i}"}
                    for i, c in enumerate(src_chunks)
                ]
                try:
                    await extract_and_store_graph(
                        repo=graph_repo,
                        project_id=project["_id"],
                        user_id=current_user["_id"],
                        source_id=src_entry["source_id"],
                        chunks=chunk_dicts,
                    )
                except Exception as graph_exc:
                    logger.warning(f"[ingest] Graph extraction failed for {src_entry['source_id']}: {graph_exc}")
        except Exception as graph_init_exc:
            logger.warning(f"[ingest] Graph extraction initialization failed: {graph_init_exc}")

    all_sources: List[SourceResult] = []
    if is_append:
        for es in existing_sources:
            chunk_cnt = es.get("chunk_count", 0)
            all_sources.append(SourceResult(
                source_id=es["source_id"],
                url=es.get("url") or es.get("resolved_url", ""),
                original_url=es.get("original_url", es.get("url", "")),
                resolved_url=es.get("resolved_url"),
                title=es.get("title", ""),
                status="success",
                chunk_count=chunk_cnt,
                chunks_indexed=chunk_cnt,
                char_count=es.get("char_count", 0),
                truncated=es.get("truncated", False),
                error=None,
            ))

    all_sources.extend(results_out)

    successful_count = len([s for s in all_sources if s.status == "success"])
    failed_count = len([s for s in results_out if s.status == "failed"])
    topic_name = topic_hint or (raw_urls[0] if raw_urls else "General Topic")

    return IngestResponse(
        session_id=session_id,
        project_id=req.project_id,
        topic_name=topic_name,
        total_sources=len(raw_urls),
        successful_sources=successful_count,
        failed_sources=failed_count,
        total_chunks_indexed=total_chunks,
        total_submitted=len(raw_urls),
        successful_count=successful_count,
        failed_count=failed_count,
        total_chunks=total_chunks,
        sources=all_sources,
        results=all_sources,
    )


@router.delete("/sources/{target_id}/{source_id:path}", response_model=IngestResponse)
@router.delete("/ingest/sources/{target_id}/{source_id:path}", response_model=IngestResponse)
async def delete_source(
    target_id: str,
    source_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Remove a source (indexed or failed) from project or session and rebuild index if needed.
    """
    # Check if target_id is a project
    project = await db.projects.find_one({"_id": target_id})
    if project:
        if not current_user or project["user_id"] != current_user["_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to modify this project.")
        index_target = project["index_id"]
        # Delete from MongoDB sources by source_id, _id, or original_url variations
        norm_url = source_id.rstrip("/")
        or_conditions = [
            {"source_id": source_id},
            {"_id": source_id},
            {"original_url": source_id},
            {"original_url": norm_url},
            {"original_url": norm_url + "/"},
            {"url": source_id},
            {"url": norm_url},
            {"url": norm_url + "/"},
            {"resolved_url": source_id},
        ]
        await db.sources.delete_many({
            "project_id": target_id,
            "$or": or_conditions,
        })
        await db.projects.update_one({"_id": target_id}, {"$set": {"updated_at": get_utc_now()}})
        # Also clean up graph data for this source
        try:
            graph_repo = GraphRepository(db)
            await graph_repo.delete_source_graph(target_id, current_user["_id"], source_id)
        except Exception as graph_exc:
            logger.warning(f"[delete_source] Graph cleanup failed for {source_id}: {graph_exc}")
    else:
        index_target = target_id

    try:
        updated_meta = remove_source_from_index(index_target, source_id)
    except FileNotFoundError:
        updated_meta = {"topic_name": "", "chunks": [], "sources": []}
    except Exception as e:
        print(f"[delete_source] FAISS index removal note for {source_id}: {e}")
        try:
            _, meta = load_index(index_target)
            updated_meta = meta
        except Exception:
            updated_meta = {"topic_name": "", "chunks": [], "sources": []}

    if project:
        cursor = db.sources.find({"project_id": target_id}).sort("created_at", pymongo.ASCENDING)
        db_sources = await cursor.to_list(length=100)
        sources_out = [
            SourceResult(
                source_id=s.get("source_id") if s.get("source_id") else str(s["_id"]),
                url=s.get("original_url") or s.get("resolved_url", ""),
                original_url=s.get("original_url", s.get("url", "")),
                resolved_url=s.get("resolved_url"),
                title=s.get("title", ""),
                status=s.get("status", "success"),
                chunk_count=s.get("chunks_indexed", 0),
                chunks_indexed=s.get("chunks_indexed", 0),
                char_count=s.get("char_count", 0),
                truncated=s.get("truncated", False),
                error=s.get("error"),
            )
            for s in db_sources
        ]
        total_chunks = len(updated_meta.get("chunks", []))
        topic_name = updated_meta.get("topic_name") or project.get("name", "")
    else:
        sources_out = [
            SourceResult(
                source_id=s["source_id"],
                url=s.get("url") or s.get("resolved_url", ""),
                original_url=s.get("original_url", s.get("url", "")),
                resolved_url=s.get("resolved_url"),
                title=s.get("title", ""),
                status="success",
                chunk_count=s.get("chunk_count", 0),
                chunks_indexed=s.get("chunk_count", 0),
                char_count=s.get("char_count", 0),
                truncated=s.get("truncated", False),
                error=None,
            )
            for s in updated_meta.get("sources", [])
        ]
        total_chunks = len(updated_meta.get("chunks", []))
        topic_name = updated_meta.get("topic_name", "")

    successful_count = len([s for s in sources_out if s.status == "success"])
    failed_count = len([s for s in sources_out if s.status == "failed"])

    return IngestResponse(
        session_id=target_id,
        project_id=target_id if project else None,
        topic_name=topic_name,
        total_sources=len(sources_out),
        successful_sources=successful_count,
        failed_sources=failed_count,
        total_chunks_indexed=total_chunks,
        total_submitted=len(sources_out),
        successful_count=successful_count,
        failed_count=failed_count,
        total_chunks=total_chunks,
        sources=sources_out,
        results=sources_out,
    )


@router.post("/sources/remove", response_model=IngestResponse)
@router.post("/ingest/sources/remove", response_model=IngestResponse)
async def post_remove_source(
    req: RemoveSourceRequest,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    target_id = req.project_id or req.session_id
    if not target_id:
        raise HTTPException(status_code=400, detail="project_id or session_id required")
    if req.original_url and req.project_id:
        norm = req.original_url.rstrip("/")
        await db.sources.delete_many({
            "project_id": req.project_id,
            "$or": [
                {"original_url": req.original_url},
                {"original_url": norm},
                {"original_url": norm + "/"},
                {"url": req.original_url},
                {"url": norm},
                {"url": norm + "/"},
            ]
        })
    return await delete_source(target_id, req.source_id, current_user, db)


class TextIngestRequest(BaseModel):
    project_id: str
    title: Optional[str] = "Pasted Study Note"
    text: str


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_pasted_text(
    req: TextIngestRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Index user-pasted text directly into project FAISS vectors & MongoDB."""
    project = await db.projects.find_one({"_id": req.project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pasted text cannot be empty.")

    title = req.title.strip() if req.title and req.title.strip() else "Pasted Study Note"
    index_target_id = project["index_id"]
    topic_hint = project["name"]

    existing_sids = []
    try:
        _, meta = load_index(index_target_id)
        existing_sids = [s.get("source_id", "") for s in meta.get("sources", [])]
    except FileNotFoundError:
        pass

    next_label = get_next_source_label(existing_sids)
    sid = f"Source {next_label}"

    is_trunc = False
    if len(text) > settings.max_chars_per_source:
        text = text[:settings.max_chars_per_source]
        is_trunc = True

    chunks = _chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if len(chunks) > settings.max_chunks_per_source:
        chunks = chunks[:settings.max_chunks_per_source]
        is_trunc = True
    chunk_count = len(chunks)

    src_entry = {
        "source_id": sid,
        "url": f"text://{title.replace(' ', '_').lower()}",
        "original_url": f"text://{title.replace(' ', '_').lower()}",
        "resolved_url": f"text://{title.replace(' ', '_').lower()}",
        "title": title,
        "text": text,
        "char_count": len(text),
        "chunk_count": chunk_count,
        "truncated": is_trunc,
        "source_type": "text",
    }

    meta = append_to_index([src_entry], index_target_id, topic_hint)
    total_chunks = len(meta.get("chunks", []))
    now = get_utc_now()

    source_update = {
        "user_id": current_user["_id"],
        "project_id": project["_id"],
        "source_id": sid,
        "original_url": src_entry["original_url"],
        "resolved_url": src_entry["resolved_url"],
        "title": title,
        "source_type": "text",
        "status": "success",
        "chunks_indexed": chunk_count,
        "truncated": is_trunc,
        "error": None,
        "updated_at": now,
    }
    await db.sources.update_one(
        {"project_id": project["_id"], "original_url": src_entry["original_url"]},
        {
            "$set": source_update,
            "$setOnInsert": {
                "_id": str(uuid.uuid4()),
                "created_at": now,
            },
        },
        upsert=True,
    )
    await db.projects.update_one({"_id": project["_id"]}, {"$set": {"updated_at": now}})

    source_res = SourceResult(
        source_id=sid,
        url=src_entry["url"],
        original_url=src_entry["original_url"],
        resolved_url=src_entry["resolved_url"],
        title=title,
        status="success",
        chunk_count=chunk_count,
        chunks_indexed=chunk_count,
        char_count=len(text),
        truncated=is_trunc,
        error=None,
    )

    all_sources = [
        SourceResult(
            source_id=s["source_id"],
            url=s.get("url") or "",
            original_url=s.get("original_url", s.get("url", "")),
            resolved_url=s.get("resolved_url"),
            title=s.get("title", ""),
            status="success",
            chunk_count=s.get("chunk_count", 0),
            chunks_indexed=s.get("chunk_count", 0),
            char_count=s.get("char_count", 0),
            truncated=s.get("truncated", False),
            error=None,
        )
        for s in meta.get("sources", [])
    ]

    return IngestResponse(
        session_id=index_target_id,
        project_id=project["_id"],
        topic_name=topic_hint,
        total_sources=len(all_sources),
        successful_sources=len(all_sources),
        failed_sources=0,
        total_chunks_indexed=total_chunks,
        total_submitted=1,
        successful_count=1,
        failed_count=0,
        total_chunks=total_chunks,
        sources=all_sources,
        results=[source_res],
    )


@router.post("/ingest/upload", response_model=IngestResponse)
async def ingest_uploaded_file(
    project_id: str = Form(...),
    title: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Extract and index uploaded PDF, TXT, or MD file into project FAISS vectors & MongoDB."""
    project = await db.projects.find_one({"_id": project_id, "user_id": current_user["_id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    filename = file.filename or "uploaded_document"
    ext = filename.lower().split(".")[-1]
    allowed_exts = {"pdf", "txt", "md", "markdown"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PDF (.pdf), Text (.txt), Markdown (.md)"
        )

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File size exceeds maximum limit of 20MB.")

    raw_text = ""
    if ext == "pdf":
        try:
            reader = pypdf.PdfReader(io.BytesIO(contents))
            pages = []
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    pages.append(t)
            raw_text = "\n\n".join(pages).strip()
            if not raw_text:
                raise ValueError("No extractable text found in PDF (it may contain only scanned images).")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read PDF document: {str(e)}")
    else:
        raw_text = contents.decode("utf-8", errors="replace").strip()

    if not raw_text:
        raise HTTPException(status_code=400, detail="Document contains no readable text.")

    doc_title = title.strip() if title and title.strip() else filename
    index_target_id = project["index_id"]
    topic_hint = project["name"]

    existing_sids = []
    try:
        _, meta = load_index(index_target_id)
        existing_sids = [s.get("source_id", "") for s in meta.get("sources", [])]
    except FileNotFoundError:
        pass

    next_label = get_next_source_label(existing_sids)
    sid = f"Source {next_label}"

    is_trunc = False
    if len(raw_text) > settings.max_chars_per_source:
        raw_text = raw_text[:settings.max_chars_per_source]
        is_trunc = True

    chunks = _chunk_text(raw_text, settings.chunk_size, settings.chunk_overlap)
    if len(chunks) > settings.max_chunks_per_source:
        chunks = chunks[:settings.max_chunks_per_source]
        is_trunc = True
    chunk_count = len(chunks)

    src_entry = {
        "source_id": sid,
        "url": f"file://{filename}",
        "original_url": f"file://{filename}",
        "resolved_url": f"file://{filename}",
        "title": doc_title,
        "text": raw_text,
        "char_count": len(raw_text),
        "chunk_count": chunk_count,
        "truncated": is_trunc,
        "source_type": ext,
    }

    meta = append_to_index([src_entry], index_target_id, topic_hint)
    total_chunks = len(meta.get("chunks", []))
    now = get_utc_now()

    source_update = {
        "user_id": current_user["_id"],
        "project_id": project["_id"],
        "source_id": sid,
        "original_url": src_entry["original_url"],
        "resolved_url": src_entry["resolved_url"],
        "title": doc_title,
        "source_type": ext,
        "status": "success",
        "chunks_indexed": chunk_count,
        "truncated": is_trunc,
        "error": None,
        "updated_at": now,
    }
    await db.sources.update_one(
        {"project_id": project["_id"], "original_url": src_entry["original_url"]},
        {
            "$set": source_update,
            "$setOnInsert": {
                "_id": str(uuid.uuid4()),
                "created_at": now,
            },
        },
        upsert=True,
    )
    await db.projects.update_one({"_id": project["_id"]}, {"$set": {"updated_at": now}})

    source_res = SourceResult(
        source_id=sid,
        url=src_entry["url"],
        original_url=src_entry["original_url"],
        resolved_url=src_entry["resolved_url"],
        title=doc_title,
        status="success",
        chunk_count=chunk_count,
        chunks_indexed=chunk_count,
        char_count=len(raw_text),
        truncated=is_trunc,
        error=None,
    )

    all_sources = [
        SourceResult(
            source_id=s["source_id"],
            url=s.get("url") or "",
            original_url=s.get("original_url", s.get("url", "")),
            resolved_url=s.get("resolved_url"),
            title=s.get("title", ""),
            status="success",
            chunk_count=s.get("chunk_count", 0),
            chunks_indexed=s.get("chunk_count", 0),
            char_count=s.get("char_count", 0),
            truncated=s.get("truncated", False),
            error=None,
        )
        for s in meta.get("sources", [])
    ]

    return IngestResponse(
        session_id=index_target_id,
        project_id=project["_id"],
        topic_name=topic_hint,
        total_sources=len(all_sources),
        successful_sources=len(all_sources),
        failed_sources=0,
        total_chunks_indexed=total_chunks,
        total_submitted=1,
        successful_count=1,
        failed_count=0,
        total_chunks=total_chunks,
        sources=all_sources,
        results=[source_res],
    )

