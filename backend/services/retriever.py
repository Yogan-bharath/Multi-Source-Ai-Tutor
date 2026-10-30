"""
Per-source top-k retrieval from FAISS.
Ensures every active indexed source independently contributes its best relevant chunks
so no single source crowds out others and removed sources are never returned.
"""
import numpy as np
import faiss
from typing import List, Dict

from config import get_settings
from services.embedder import load_index, _get_model

settings = get_settings()


def retrieve_per_source(
    session_id: str,
    question: str,
    top_k: int | None = None,
) -> Dict[str, List[dict]]:
    """
    Returns dict: source_id -> list of top-k chunk dicts {source_id, url, title, text, score, ...}.
    Guarantees every active source independently contributes relevant chunks.
    """
    top_k = top_k or settings.top_k_per_source
    index, meta = load_index(session_id)
    model = _get_model()

    active_sources = meta.get("sources", [])
    all_chunks = meta.get("chunks", [])

    if not active_sources or not all_chunks:
        return {}

    # Set of valid active source IDs
    active_sids = {s["source_id"] for s in active_sources}

    # Encode & normalize query using fastembed
    q_vec = list(model.embed([question]))
    q_vec = np.array(q_vec, dtype=np.float32)
    faiss.normalize_L2(q_vec)

    # Search broad candidate pool so every source gets represented
    n_chunks = len(all_chunks)
    # Search all chunks if manageable, or at least a generous multiple
    k_global = min(n_chunks, max(150, top_k * len(active_sources) * 15))
    scores, indices = index.search(q_vec, k_global)

    scores = scores[0]
    indices = indices[0]

    # Initialize container for every active source
    per_source: Dict[str, List[dict]] = {s["source_id"]: [] for s in active_sources}
    per_source_count: Dict[str, int] = {s["source_id"]: 0 for s in active_sources}

    for score, idx in zip(scores, indices):
        if idx < 0 or idx >= n_chunks:
            continue
        chunk = all_chunks[idx]
        sid = chunk["source_id"]

        # Only accept active sources (prevents removed sources from returning)
        if sid in active_sids and per_source_count[sid] < top_k:
            source_url = chunk.get("source_url") or chunk.get("url", "")
            source_title = chunk.get("source_title") or chunk.get("title", sid)
            per_source[sid].append({
                "source_id": sid,
                "url": source_url,
                "source_url": source_url,
                "title": source_title,
                "source_title": source_title,
                "topic_name": chunk.get("topic_name", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "text": chunk["text"],
                "score": float(score),
            })
            per_source_count[sid] += 1

    return per_source
