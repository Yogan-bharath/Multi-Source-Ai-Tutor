"""
Hybrid Retrieval Service: Combines FAISS vector retrieval with graph-based retrieval.
Normalizes scores, deduplicates evidence, ranks combined results, and applies context limits.
Falls back gracefully to vector-only if graph retrieval is unavailable or fails.
"""
import logging
from typing import List, Dict, Any, Optional

from config import get_settings
from services.retriever import retrieve_per_source
from services.graph_retrieval_service import retrieve_graph_evidence
from services.embedder import load_index
from repositories.graph_repository import GraphRepository
from schemas.graph_schemas import RetrievalMetadata

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


def normalize_scores(chunks_or_scores: Any) -> Any:
    """
    Min-max normalize scores to [0, 1].
    Supports either a list of float scores or a list of chunk dicts.
    """
    if not chunks_or_scores:
        return chunks_or_scores

    if isinstance(chunks_or_scores[0], (int, float)):
        min_s = min(chunks_or_scores)
        max_s = max(chunks_or_scores)
        score_range = max_s - min_s
        if score_range > 0:
            return [(s - min_s) / score_range for s in chunks_or_scores]
        return [1.0 for _ in chunks_or_scores]

    # Otherwise list of chunk dicts
    chunks = chunks_or_scores
    scores = [c.get("score", 0.0) for c in chunks]
    min_s = min(scores)
    max_s = max(scores)
    score_range = max_s - min_s

    for c in chunks:
        if score_range > 0:
            c["normalized_score"] = (c.get("score", 0.0) - min_s) / score_range
        else:
            c["normalized_score"] = 1.0

    return chunks


_normalize_scores = normalize_scores


def _flatten_per_source_chunks(
    per_source: Dict[str, List[dict]],
) -> List[Dict[str, Any]]:
    """Flatten per-source retrieval results into a single list with retrieval_method tag."""
    flat: List[Dict[str, Any]] = []
    for source_id, chunks in per_source.items():
        for chunk in chunks:
            flat.append({
                "source_id": chunk.get("source_id", source_id),
                "url": chunk.get("url") or chunk.get("source_url", ""),
                "title": chunk.get("title") or chunk.get("source_title", source_id),
                "text": chunk.get("text", ""),
                "score": float(chunk.get("score", 0.0)),
                "chunk_index": chunk.get("chunk_index", 0),
                "topic_name": chunk.get("topic_name", ""),
                "retrieval_method": "vector",
                "supporting_entities": [],
                "supporting_relationships": [],
            })
    return flat


def _resolve_graph_chunks_from_faiss(
    graph_evidence: Dict[str, Any],
    index_id: str,
) -> List[Dict[str, Any]]:
    """
    Resolve graph-referenced chunk IDs and source IDs back to actual FAISS chunk content.
    Returns chunks tagged with graph retrieval method and supporting entity/relationship info.
    """
    supporting_chunk_ids = set(graph_evidence.get("supporting_chunk_ids", []))
    supporting_source_ids = set(graph_evidence.get("supporting_source_ids", []))

    if not supporting_chunk_ids and not supporting_source_ids:
        return []

    try:
        _, meta = load_index(index_id)
    except FileNotFoundError:
        return []

    all_chunks = meta.get("chunks", [])
    graph_chunks: List[Dict[str, Any]] = []
    seen_texts = set()

    # Collect entity/relationship IDs for provenance
    entity_ids = [e.get("entity_id", "") for e in graph_evidence.get("entities", [])]
    rel_ids = [r.get("relationship_id", "") for r in graph_evidence.get("relationships", [])]

    for i, chunk in enumerate(all_chunks):
        chunk_id = chunk.get("chunk_id", f"{chunk.get('source_id', '')}:chunk_{i}")
        source_id = chunk.get("source_id", "")
        text = chunk.get("text", "")

        # Match by chunk_id reference or source_id reference
        matched = chunk_id in supporting_chunk_ids or source_id in supporting_source_ids
        if matched and text and text not in seen_texts:
            seen_texts.add(text)
            graph_chunks.append({
                "source_id": source_id,
                "url": chunk.get("source_url") or chunk.get("url", ""),
                "title": chunk.get("source_title") or chunk.get("title", source_id),
                "text": text,
                "score": 0.5,  # Base graph retrieval score (will be normalized)
                "chunk_index": chunk.get("chunk_index", i),
                "topic_name": chunk.get("topic_name", ""),
                "retrieval_method": "graph",
                "supporting_entities": entity_ids[:5],
                "supporting_relationships": rel_ids[:5],
            })

    return graph_chunks


def _deduplicate_and_rank(
    vector_chunks: List[Dict[str, Any]],
    graph_chunks: List[Dict[str, Any]],
    vector_weight: float,
    graph_weight: float,
    max_context_chunks: int = 15,
) -> List[Dict[str, Any]]:
    """
    Merge vector and graph retrieval results:
    1. Normalize scores within each source independently.
    2. Combine using weighted scoring.
    3. Deduplicate by text content.
    4. Sort by final score descending.
    5. Apply context limit.
    """
    # Normalize each source's scores independently
    vector_chunks = _normalize_scores(vector_chunks)
    graph_chunks = _normalize_scores(graph_chunks)

    # Apply weights
    for c in vector_chunks:
        c["weighted_score"] = c.get("normalized_score", 0.0) * vector_weight
    for c in graph_chunks:
        c["weighted_score"] = c.get("normalized_score", 0.0) * graph_weight

    # Merge and deduplicate by text content
    seen_texts = set()
    merged: List[Dict[str, Any]] = []

    # Process vector chunks first (generally higher confidence)
    for c in sorted(vector_chunks, key=lambda x: x.get("weighted_score", 0), reverse=True):
        text_key = c.get("text", "").strip()[:200]  # Use first 200 chars as dedup key
        if text_key and text_key not in seen_texts:
            seen_texts.add(text_key)
            merged.append(c)

    # Add graph chunks that aren't duplicates
    for c in sorted(graph_chunks, key=lambda x: x.get("weighted_score", 0), reverse=True):
        text_key = c.get("text", "").strip()[:200]
        if text_key and text_key not in seen_texts:
            seen_texts.add(text_key)
            # If graph-only chunk overlaps with a vector-retrieved source, boost its score
            c["retrieval_method"] = "graph"
            merged.append(c)
        elif text_key in seen_texts:
            # Chunk exists from vector too — mark as hybrid and boost
            for existing in merged:
                if existing.get("text", "").strip()[:200] == text_key:
                    existing["retrieval_method"] = "hybrid"
                    existing["weighted_score"] = max(
                        existing.get("weighted_score", 0),
                        existing.get("weighted_score", 0) + c.get("weighted_score", 0) * 0.3,
                    )
                    # Merge provenance
                    existing.setdefault("supporting_entities", []).extend(c.get("supporting_entities", []))
                    existing.setdefault("supporting_relationships", []).extend(c.get("supporting_relationships", []))
                    break

    # Final sort and truncation
    merged.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
    return merged[:max_context_chunks]


combine_and_deduplicate = _deduplicate_and_rank


def _rebuild_per_source(
    ranked_chunks: List[Dict[str, Any]],
) -> Dict[str, List[dict]]:
    """
    Rebuild per-source chunk structure from ranked flat list.
    This maintains backward compatibility with the existing chat pipeline.
    """
    per_source: Dict[str, List[dict]] = {}
    for chunk in ranked_chunks:
        sid = chunk.get("source_id", "Unknown")
        if sid not in per_source:
            per_source[sid] = []
        per_source[sid].append({
            "source_id": sid,
            "url": chunk.get("url", ""),
            "source_url": chunk.get("url", ""),
            "title": chunk.get("title", sid),
            "source_title": chunk.get("title", sid),
            "topic_name": chunk.get("topic_name", ""),
            "chunk_index": chunk.get("chunk_index", 0),
            "text": chunk.get("text", ""),
            "score": float(chunk.get("weighted_score", chunk.get("score", 0.0))),
            "retrieval_method": chunk.get("retrieval_method", "vector"),
            "supporting_entities": chunk.get("supporting_entities", []),
            "supporting_relationships": chunk.get("supporting_relationships", []),
        })
    return per_source


async def hybrid_retrieve(
    index_id: str,
    question: str,
    project_id: str,
    user_id: str,
    repo: Optional[GraphRepository] = None,
    rag_mode: Optional[str] = None,
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main hybrid retrieval entry point.
    
    Args:
        index_id: FAISS index identifier
        question: User question
        project_id: Project ID for scoping
        user_id: Authenticated user ID
        repo: GraphRepository (required for hybrid mode)
        rag_mode: "vector" or "hybrid" (defaults to settings.rag_mode)
        top_k: Top-K per source for vector retrieval
    
    Returns:
        {
            "per_source": {source_id: [chunks...]},  # backward-compatible format
            "retrieval_metadata": RetrievalMetadata dict,
        }
    """
    rag_mode = rag_mode or settings.rag_mode

    # Step 1: Run vector retrieval with safe fallback
    try:
        per_source = retrieve_per_source(
            session_id=index_id,
            question=question,
            top_k=top_k,
        )
    except FileNotFoundError:
        logger.warning(f"[hybrid_retrieval] No FAISS index found for {index_id}")
        per_source = {}
    except Exception as exc:
        logger.error(f"[hybrid_retrieval] Error during vector retrieval: {exc}")
        per_source = {}

    vector_chunks = _flatten_per_source_chunks(per_source)

    metadata = RetrievalMetadata(
        retrieval_mode=rag_mode,
        vector_results_count=len(vector_chunks),
        source_ids=list(per_source.keys()),
    )

    # Step 2: If vector-only mode, return immediately
    if rag_mode != "hybrid" or repo is None:
        metadata.final_context_count = len(vector_chunks)
        return {
            "per_source": per_source,
            "retrieval_metadata": metadata.model_dump(),
        }

    # Step 3: Run graph retrieval (with graceful fallback)
    graph_evidence = {}
    graph_chunks: List[Dict[str, Any]] = []

    try:
        graph_evidence = await retrieve_graph_evidence(
            repo=repo,
            project_id=project_id,
            user_id=user_id,
            question=question,
        )

        # Resolve graph references to actual FAISS chunks
        graph_chunks = _resolve_graph_chunks_from_faiss(graph_evidence, index_id)

        metadata.graph_results_count = len(graph_chunks)
        metadata.graph_entity_ids = [
            e.get("entity_id", "") for e in graph_evidence.get("entities", [])
        ]
        metadata.graph_relationship_ids = [
            r.get("relationship_id", "") for r in graph_evidence.get("relationships", [])
        ]

    except Exception as exc:
        logger.warning(f"[hybrid_retrieval] Graph retrieval failed, falling back to vector-only: {exc}")
        # Continue with vector-only — graceful degradation

    # Step 4: Combine, deduplicate, rank
    if graph_chunks:
        ranked = _deduplicate_and_rank(
            vector_chunks=vector_chunks,
            graph_chunks=graph_chunks,
            vector_weight=settings.hybrid_vector_weight,
            graph_weight=settings.hybrid_graph_weight,
        )
        combined_per_source = _rebuild_per_source(ranked)
        metadata.final_context_count = len(ranked)
    else:
        # No graph results — return vector-only
        combined_per_source = per_source
        metadata.final_context_count = len(vector_chunks)
        metadata.retrieval_mode = "vector"  # Downgrade since graph had nothing

    # Collect all chunk and source IDs
    all_chunk_ids = set()
    all_source_ids = set()
    for sid, chunks in combined_per_source.items():
        all_source_ids.add(sid)
        for c in chunks:
            ci = c.get("chunk_index")
            if ci is not None:
                all_chunk_ids.add(f"{sid}:chunk_{ci}")

    metadata.chunk_ids = list(all_chunk_ids)
    metadata.source_ids = list(all_source_ids)

    return {
        "per_source": combined_per_source,
        "retrieval_metadata": metadata.model_dump(),
    }
