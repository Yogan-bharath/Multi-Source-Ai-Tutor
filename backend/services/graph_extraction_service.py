"""
Graph Extraction Service: Extract entities and relationships from document chunks using Groq LLM.
Runs as a non-blocking enhancement after normal source ingestion completes.
Graph extraction failures never interrupt the existing ingestion pipeline.
"""
import json
import logging
import traceback
from typing import List, Dict, Optional, Any

from groq import Groq

from config import get_settings
from repositories.graph_repository import GraphRepository
from schemas.graph_schemas import GraphExtractionPayload

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge graph extraction system. Your task is to identify important entities and meaningful relationships from text chunks of educational/technical documents.

Rules:
- Only extract SIGNIFICANT entities: key concepts, technologies, algorithms, methods, people, organizations, products, standards.
- Do NOT extract common words, generic verbs, articles, pronouns, or trivial terms.
- Only extract relationships that are EXPLICITLY stated or strongly implied in the text.
- Do NOT speculate about relationships not supported by the text.
- Normalize entity names (e.g., "ML" and "machine learning" should be the same entity).
- Keep descriptions concise and grounded in the source text.

Respond ONLY with a valid JSON object in this exact format:
{
  "entities": [
    {
      "name": "Entity Name",
      "entity_type": "Technology|Concept|Method|Algorithm|Person|Organization|Product|Standard|Framework|Language",
      "description": "One-sentence factual description from text",
      "aliases": ["alternate name", "abbreviation"]
    }
  ],
  "relationships": [
    {
      "source_entity": "Entity A Name",
      "target_entity": "Entity B Name",
      "relation_type": "USES|DEPENDS_ON|PART_OF|IMPROVES|CATEGORY_OF|RELATED_TO|CREATED_BY|IMPLEMENTS|WORKS_WITH|ALTERNATIVE_TO",
      "description": "Brief explanation of the relationship",
      "weight": 0.8
    }
  ]
}

Important:
- Limit to at most 15 entities and 15 relationships per chunk.
- Entity names must exactly match between the entities list and the relationships list.
- Return an empty entities/relationships list if the text has no extractable knowledge structure."""


def _parse_extraction_response(raw_text: str) -> Optional[GraphExtractionPayload]:
    """Safely parse the LLM JSON response into a validated Pydantic model."""
    if not raw_text:
        return None

    # Try parsing as JSON directly
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code fences
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                logger.warning("[graph_extraction] Failed to parse LLM JSON even after fence extraction")
                return None
        else:
            logger.warning("[graph_extraction] Failed to parse LLM extraction response as JSON")
            return None

    try:
        payload = GraphExtractionPayload(**data)
        return payload
    except Exception as e:
        logger.warning(f"[graph_extraction] Pydantic validation failed: {e}")
        return None


def _extract_from_chunks_batch(
    chunks_batch: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Send a batch of chunks to the LLM for entity/relationship extraction.
    Returns a list of dicts: [{"chunk_id": ..., "payload": GraphExtractionPayload or None}]
    """
    client = Groq(api_key=settings.groq_api_key)
    model = model or settings.llm_model_primary
    results = []

    # Combine chunks into a single prompt for batched extraction
    combined_text_parts = []
    for i, chunk in enumerate(chunks_batch):
        chunk_id = chunk.get("chunk_id", f"chunk_{i}")
        text = chunk.get("text", "")
        if text.strip():
            combined_text_parts.append(f"--- CHUNK [{chunk_id}] ---\n{text}")

    if not combined_text_parts:
        return results

    combined_text = "\n\n".join(combined_text_parts)

    # Truncate to avoid exceeding context limits
    max_chars = 12000
    if len(combined_text) > max_chars:
        combined_text = combined_text[:max_chars]

    user_msg = f"""Extract entities and relationships from the following document chunks:

{combined_text}

Return the consolidated entities and relationships as a single JSON object. Merge duplicate entities across chunks."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        payload = _parse_extraction_response(raw_content)

        results.append({
            "chunk_ids": [c.get("chunk_id", f"chunk_{i}") for i, c in enumerate(chunks_batch)],
            "payload": payload,
        })

    except Exception as exc:
        logger.error(f"[graph_extraction] LLM call failed with {model}: {exc}")
        # Try fallback model
        if model == settings.llm_model_primary:
            try:
                return _extract_from_chunks_batch(chunks_batch, model=settings.llm_model_fallback)
            except Exception as fallback_exc:
                logger.error(f"[graph_extraction] Fallback LLM also failed: {fallback_exc}")

        results.append({
            "chunk_ids": [c.get("chunk_id", f"chunk_{i}") for i, c in enumerate(chunks_batch)],
            "payload": None,
        })

    return results


async def extract_and_store_graph(
    repo: GraphRepository,
    project_id: str,
    user_id: str,
    source_id: str,
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Main entry point: extract entities and relationships from chunks and persist to MongoDB.
    
    This function is designed to be called AFTER normal source ingestion completes.
    It never raises exceptions to the caller — all errors are logged and recorded in processing status.
    
    Args:
        repo: GraphRepository instance (with active DB connection)
        project_id: Owning project ID
        user_id: Owning user ID
        source_id: Source document ID (e.g., "Source A")
        chunks: List of dicts with at least "text" and optionally "chunk_id"
    
    Returns:
        Dict with extraction stats: {"status": ..., "entity_count": ..., "relationship_count": ...}
    """
    result = {"status": "failed", "entity_count": 0, "relationship_count": 0, "error": None}

    try:
        await repo.update_processing_status(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            status="processing",
        )

        if not chunks:
            await repo.update_processing_status(
                project_id=project_id,
                user_id=user_id,
                source_id=source_id,
                status="completed",
                entity_count=0,
                relationship_count=0,
            )
            result["status"] = "completed"
            return result

        # Assign chunk IDs if missing
        for i, chunk in enumerate(chunks):
            if "chunk_id" not in chunk:
                chunk["chunk_id"] = f"{source_id}:chunk_{i}"

        # Process in batches
        batch_size = settings.graph_extraction_batch_size
        all_entities: List[dict] = []
        all_relationships: List[dict] = []

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start:batch_start + batch_size]
            batch_results = _extract_from_chunks_batch(batch)

            for br in batch_results:
                payload = br.get("payload")
                if payload and isinstance(payload, GraphExtractionPayload):
                    for ent in payload.entities:
                        all_entities.append(ent.model_dump())
                    for rel in payload.relationships:
                        all_relationships.append(rel.model_dump())

        # Deduplicate entities by normalized name before upserting
        seen_names = {}
        deduped_entities = []
        for ent in all_entities:
            from repositories.graph_repository import normalize_entity_name
            norm = normalize_entity_name(ent.get("name", ""))
            if norm and norm not in seen_names:
                seen_names[norm] = True
                deduped_entities.append(ent)
            elif norm and norm in seen_names:
                # Merge aliases if duplicate
                for existing in deduped_entities:
                    if normalize_entity_name(existing.get("name", "")) == norm:
                        existing_aliases = set(existing.get("aliases", []))
                        new_aliases = set(ent.get("aliases", []))
                        existing["aliases"] = list(existing_aliases | new_aliases)
                        break

        # Upsert entities
        name_to_id = await repo.upsert_entities(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            raw_entities=deduped_entities,
        )

        # Upsert relationships
        rel_count = await repo.upsert_relationships(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            raw_relationships=all_relationships,
            name_to_id=name_to_id,
        )

        entity_count = len(name_to_id)
        await repo.update_processing_status(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            status="completed",
            entity_count=entity_count,
            relationship_count=rel_count,
        )

        result["status"] = "completed"
        result["entity_count"] = entity_count
        result["relationship_count"] = rel_count

        logger.info(
            f"[graph_extraction] Source '{source_id}' in project '{project_id}': "
            f"extracted {entity_count} entities, {rel_count} relationships"
        )

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.error(f"[graph_extraction] Failed for source '{source_id}': {error_msg}\n{traceback.format_exc()}")
        result["error"] = error_msg

        try:
            await repo.update_processing_status(
                project_id=project_id,
                user_id=user_id,
                source_id=source_id,
                status="failed",
                error=error_msg,
            )
        except Exception:
            pass

    return result
