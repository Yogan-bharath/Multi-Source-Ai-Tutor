"""
Chunk each source's text, embed with fastembed (ONNX-based, no PyTorch),
and store in a per-project FAISS index with safe JSON metadata (no pickle deserialization).
Enforces per-source chunk limits (max 100 chunks) and tracks truncation.
"""
import os
import re
import json
import string
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

import numpy as np
import faiss
from fastembed import TextEmbedding

from config import get_settings

settings = get_settings()
_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model


def sanitize_index_id(index_id: str) -> str:
    """Sanitize index identifier to prevent path traversal vulnerabilities."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", index_id)
    if not cleaned:
        raise ValueError("Invalid index identifier.")
    return cleaned


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step
    return chunks


def get_next_source_label(existing_source_ids: List[str]) -> str:
    """Generate next available source letter label (A, B, C, D, E...)."""
    used = set()
    for sid in existing_source_ids:
        parts = sid.split()
        if len(parts) >= 2 and parts[0].lower() == "source":
            used.add(parts[1].upper())

    for letter in string.ascii_uppercase:
        if letter not in used:
            return letter

    for l1 in string.ascii_uppercase:
        for l2 in string.ascii_uppercase:
            candidate = f"{l1}{l2}"
            if candidate not in used:
                return candidate

    return str(len(used) + 1)


def build_index(scraped_sources: List[dict], session_id: str, topic_name: str = "") -> dict:
    """
    Build a fresh FAISS index for the project/session using safe JSON metadata.
    Enforces max chunks limit per source and sets `truncated` accordingly.
    """
    safe_id = sanitize_index_id(session_id)
    model = _get_model()
    all_chunks: List[dict] = []
    all_texts: List[str] = []
    sources_meta: List[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    max_chunks = settings.max_chunks_per_source

    for src in scraped_sources:
        sid = src["source_id"]
        source_url = src.get("resolved_url") or src.get("url") or src.get("original_url", "")
        orig_url = src.get("original_url", source_url)
        source_title = src.get("title") or source_url
        is_truncated = src.get("truncated", False)

        chunks = _chunk_text(src["text"], settings.chunk_size, settings.chunk_overlap)
        if len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
            is_truncated = True

        for idx, c in enumerate(chunks):
            chunk_dict = {
                "source_id": sid,
                "original_url": orig_url,
                "resolved_url": source_url,
                "source_url": source_url,
                "url": source_url,
                "source_title": source_title,
                "title": source_title,
                "topic_name": topic_name,
                "chunk_index": idx,
                "timestamp": now_iso,
                "truncated": is_truncated,
                "text": c,
            }
            all_chunks.append(chunk_dict)
            all_texts.append(c)

        sources_meta.append({
            "source_id": sid,
            "url": source_url,
            "original_url": orig_url,
            "resolved_url": source_url,
            "title": source_title,
            "char_count": src.get("char_count", len(src.get("text", ""))),
            "chunk_count": len(chunks),
            "truncated": is_truncated,
            "timestamp": now_iso,
        })

    os.makedirs(settings.faiss_index_dir, exist_ok=True)
    index_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.index")
    json_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.meta.json")

    if all_texts:
        print(f"[embedder] Embedding {len(all_texts)} chunks for {safe_id}...")
        embeddings_gen = model.embed(all_texts, batch_size=32)
        embeddings = np.array(list(embeddings_gen), dtype=np.float32)
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        faiss.write_index(index, index_path)
    else:
        dim = 384
        index = faiss.IndexFlatIP(dim)
        faiss.write_index(index, index_path)

    meta = {
        "topic_name": topic_name,
        "chunks": all_chunks,
        "sources": sources_meta,
    }

    # Safe structured JSON storage (no pickle)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[embedder] Built index saved: {index_path} with {len(all_chunks)} chunks from {len(sources_meta)} sources (JSON metadata)")
    return meta


def append_to_index(new_scraped_sources: List[dict], session_id: str, topic_name: str = "") -> dict:
    """
    Append new sources to an existing index without re-indexing existing ones.
    """
    safe_id = sanitize_index_id(session_id)
    index_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.index")
    json_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.meta.json")

    if not os.path.exists(index_path) or not os.path.exists(json_path):
        return build_index(new_scraped_sources, session_id, topic_name)

    index, meta = load_index(session_id)
    model = _get_model()

    if not topic_name and meta.get("topic_name"):
        topic_name = meta["topic_name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    new_chunks = []
    new_texts = []
    max_chunks = settings.max_chunks_per_source

    for src in new_scraped_sources:
        sid = src["source_id"]
        source_url = src.get("resolved_url") or src.get("url") or src.get("original_url", "")
        orig_url = src.get("original_url", source_url)
        source_title = src.get("title") or source_url
        is_truncated = src.get("truncated", False)

        chunks = _chunk_text(src["text"], settings.chunk_size, settings.chunk_overlap)
        if len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
            is_truncated = True

        for idx, c in enumerate(chunks):
            chunk_dict = {
                "source_id": sid,
                "original_url": orig_url,
                "resolved_url": source_url,
                "source_url": source_url,
                "url": source_url,
                "source_title": source_title,
                "title": source_title,
                "topic_name": topic_name,
                "chunk_index": idx,
                "timestamp": now_iso,
                "truncated": is_truncated,
                "text": c,
            }
            new_chunks.append(chunk_dict)
            new_texts.append(c)

        meta["sources"].append({
            "source_id": sid,
            "url": source_url,
            "original_url": orig_url,
            "resolved_url": source_url,
            "title": source_title,
            "char_count": src.get("char_count", len(src.get("text", ""))),
            "chunk_count": len(chunks),
            "truncated": is_truncated,
            "timestamp": now_iso,
        })

    if new_texts:
        print(f"[embedder] Embedding {len(new_texts)} new chunks for {safe_id}...")
        embeddings_gen = model.embed(new_texts, batch_size=32)
        new_embeddings = np.array(list(embeddings_gen), dtype=np.float32)
        faiss.normalize_L2(new_embeddings)

        index.add(new_embeddings)
        faiss.write_index(index, index_path)

    meta["chunks"].extend(new_chunks)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[embedder] Updated {safe_id}: now {len(meta['chunks'])} chunks across {len(meta['sources'])} sources")
    return meta


def remove_source_from_index(session_id: str, source_id: str) -> dict:
    """
    Remove a specific source and all its associated chunks from the index.
    Rebuilds the FAISS index from remaining chunks so removed chunks cannot be retrieved.
    """
    safe_id = sanitize_index_id(session_id)
    index, meta = load_index(session_id)

    original_sources = meta.get("sources", [])
    original_chunks = meta.get("chunks", [])
    remaining_sources = [s for s in original_sources if s.get("source_id") != source_id and s.get("original_url") != source_id and s.get("url") != source_id]
    remaining_chunks = [c for c in original_chunks if c.get("source_id") != source_id and c.get("url") != source_id]

    if len(remaining_sources) == len(original_sources) and len(remaining_chunks) == len(original_chunks):
        print(f"[embedder] Source {source_id} had no indexed vectors in {safe_id}. Skipping FAISS rebuild.")
        return meta

    topic_name = meta.get("topic_name", "")
    model = _get_model()

    index_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.index")
    json_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.meta.json")

    if remaining_chunks:
        texts = [c["text"] for c in remaining_chunks]
        embeddings_gen = model.embed(texts, batch_size=32)
        embeddings = np.array(list(embeddings_gen), dtype=np.float32)
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        new_index = faiss.IndexFlatIP(dim)
        new_index.add(embeddings)
        faiss.write_index(new_index, index_path)
    else:
        dim = 384
        new_index = faiss.IndexFlatIP(dim)
        faiss.write_index(new_index, index_path)

    updated_meta = {
        "topic_name": topic_name,
        "chunks": remaining_chunks,
        "sources": remaining_sources,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(updated_meta, f, indent=2, ensure_ascii=False)

    print(f"[embedder] Removed {source_id} from {safe_id}. Remaining: {len(remaining_sources)} sources, {len(remaining_chunks)} chunks")
    return updated_meta


def load_index(session_id: str) -> Tuple[faiss.Index, dict]:
    """
    Load FAISS index and metadata safely using JSON (no pickle deserialization).
    """
    safe_id = sanitize_index_id(session_id)
    index_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.index")
    json_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.meta.json")
    pkl_path = os.path.join(settings.faiss_index_dir, f"{safe_id}.meta.pkl")

    if not os.path.exists(index_path):
        raise FileNotFoundError(f"No FAISS index found for {safe_id}")

    index = faiss.read_index(index_path)

    # Preferred: safe JSON
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return index, meta

    # Fallback migration for existing sessions created before upgrade:
    # Convert safely once to JSON so subsequent loads use JSON
    if os.path.exists(pkl_path):
        import pickle
        with open(pkl_path, "rb") as f:
            meta = pickle.load(f)
        # Migrate immediately to JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return index, meta

    raise FileNotFoundError(f"No metadata found for {safe_id}")


def delete_index_files(session_id: str):
    """Clean up FAISS index and metadata files when a project is deleted."""
    try:
        safe_id = sanitize_index_id(session_id)
        for ext in [".index", ".meta.json", ".meta.pkl"]:
            path = os.path.join(settings.faiss_index_dir, f"{safe_id}{ext}")
            if os.path.exists(path):
                os.remove(path)
                print(f"[embedder] Deleted index file: {path}")
    except Exception as exc:
        print(f"[embedder] Error deleting index files for {session_id}: {exc}")
