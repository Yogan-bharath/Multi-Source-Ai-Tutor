"""
Graph Retrieval Service: Query the knowledge graph to find entities, relationships,
and supporting source chunks relevant to a user question.
Strictly scoped by user_id and project_id for multi-tenant isolation.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Set

from config import get_settings
from repositories.graph_repository import GraphRepository, normalize_entity_name
from schemas.graph_schemas import GraphEntityInfo, GraphRelationshipInfo

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


def extract_query_terms(question: str) -> List[str]:
    """
    Extract candidate entity terms from a user question using simple NLP heuristics.
    Splits on stop words, filters short/trivial words, and produces candidate n-grams.
    """
    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "them", "their", "this", "that", "these", "those",
        "what", "which", "who", "whom", "how", "when", "where", "why",
        "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "under", "about", "against", "over",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "if", "then", "because", "since", "while", "although", "though",
        "very", "really", "just", "also", "too", "more", "most", "much",
        "many", "some", "any", "all", "each", "every", "no", "few",
        "tell", "explain", "describe", "define", "compare", "discuss",
        "does", "work", "use", "used", "using", "related", "connect",
        "give", "example", "examples", "way", "ways",
    }

    # Clean the question
    cleaned = re.sub(r"[^\w\s\-]", " ", question.lower())
    words = cleaned.split()

    # Filter out stop words and short tokens
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) >= 2]

    terms: List[str] = []

    # Add individual words
    terms.extend(meaningful)

    # Add bigrams and trigrams for multi-word entity matching
    for n in [2, 3]:
        for i in range(len(meaningful) - n + 1):
            ngram = " ".join(meaningful[i:i + n])
            terms.append(ngram)

    # Also add the full cleaned question minus stop words as a single term (for long entity names)
    full_cleaned = " ".join(meaningful)
    if full_cleaned and len(meaningful) > 1:
        terms.append(full_cleaned)

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_terms = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique_terms.append(t)

    return unique_terms


async def retrieve_graph_evidence(
    repo: GraphRepository,
    project_id: str,
    user_id: str,
    question: str,
    max_entities: int = 0,
    max_relationships: int = 0,
    max_hops: int = 0,
) -> Dict[str, Any]:
    """
    Main entry point for graph-based retrieval.
    
    1. Extract candidate terms from the question.
    2. Match entities in the project's knowledge graph.
    3. Traverse relationships (multi-hop bounded).
    4. Collect supporting chunk IDs and source IDs.
    5. Return structured evidence with provenance.
    
    Returns:
        {
            "entities": [GraphEntityInfo, ...],
            "relationships": [GraphRelationshipInfo, ...],
            "supporting_chunk_ids": [...],
            "supporting_source_ids": [...],
            "graph_paths": [...],
        }
    """
    max_entities = max_entities or settings.graph_max_entities
    max_relationships = max_relationships or settings.graph_max_relationships
    max_hops = max_hops or settings.graph_max_hops

    empty_result = {
        "entities": [],
        "relationships": [],
        "supporting_chunk_ids": [],
        "supporting_source_ids": [],
        "graph_paths": [],
    }

    try:
        # Step 1: Extract query terms
        terms = extract_query_terms(question)
        if not terms:
            logger.debug("[graph_retrieval] No meaningful terms extracted from question")
            return empty_result

        # Step 2: Find matching entities
        matched_entities = await repo.search_entities_by_terms(
            project_id=project_id,
            user_id=user_id,
            terms=terms,
            limit=max_entities,
        )

        if not matched_entities:
            logger.debug(f"[graph_retrieval] No entities matched for terms: {terms[:5]}")
            return empty_result

        seed_entity_ids = [e.get("entity_id") for e in matched_entities if e.get("entity_id")]

        # Step 3: Multi-hop graph traversal
        traversal = await repo.traverse_subgraph(
            project_id=project_id,
            user_id=user_id,
            seed_entity_ids=seed_entity_ids,
            max_hops=max_hops,
            max_relationships=max_relationships,
            max_entities=max_entities,
        )

        # Step 4: Collect supporting evidence references
        all_chunk_ids: Set[str] = set()
        all_source_ids: Set[str] = set()

        entity_infos: List[Dict[str, Any]] = []
        for e in traversal.get("entities", []):
            info = GraphEntityInfo(
                entity_id=e.get("entity_id", ""),
                name=e.get("name", ""),
                entity_type=e.get("entity_type", "Concept"),
                description=e.get("description", ""),
                source_ids=e.get("source_ids", []),
                chunk_ids=e.get("chunk_ids", []),
            )
            entity_infos.append(info.model_dump())
            all_chunk_ids.update(e.get("chunk_ids", []))
            all_source_ids.update(e.get("source_ids", []))

        relationship_infos: List[Dict[str, Any]] = []
        for r in traversal.get("relationships", []):
            info = GraphRelationshipInfo(
                relationship_id=r.get("relationship_id", ""),
                source_entity_name=r.get("source_entity_name", ""),
                target_entity_name=r.get("target_entity_name", ""),
                relation_type=r.get("relation_type", ""),
                description=r.get("description", ""),
                source_ids=r.get("source_ids", []),
                chunk_ids=r.get("chunk_ids", []),
            )
            relationship_infos.append(info.model_dump())
            all_chunk_ids.update(r.get("chunk_ids", []))
            all_source_ids.update(r.get("source_ids", []))

        graph_paths = traversal.get("paths", [])

        logger.info(
            f"[graph_retrieval] Project '{project_id}': found {len(entity_infos)} entities, "
            f"{len(relationship_infos)} relationships, {len(graph_paths)} paths"
        )

        return {
            "entities": entity_infos,
            "relationships": relationship_infos,
            "supporting_chunk_ids": list(all_chunk_ids),
            "supporting_source_ids": list(all_source_ids),
            "graph_paths": graph_paths,
        }

    except Exception as exc:
        logger.error(f"[graph_retrieval] Error during graph retrieval: {exc}")
        return empty_result


async def graph_retrieve(
    user_id: str,
    project_id: str,
    question: str,
    repo: GraphRepository,
    max_hops: int = 0,
    max_entities: int = 0,
    max_relationships: int = 0,
) -> Dict[str, Any]:
    """Convenience alias for retrieve_graph_evidence."""
    return await retrieve_graph_evidence(
        repo=repo,
        project_id=project_id,
        user_id=user_id,
        question=question,
        max_entities=max_entities,
        max_relationships=max_relationships,
        max_hops=max_hops,
    )
