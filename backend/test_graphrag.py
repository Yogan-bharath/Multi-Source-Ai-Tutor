"""
Comprehensive Test Suite for GraphRAG:
- Unit tests for schemas & ID generation
- Graph repository CRUD and upsert merging
- Multi-tenant security & data isolation (user A vs user B, project A vs project B)
- Graph retrieval & multi-hop traversal
- Hybrid retrieval combining vector & graph evidence
- Cascading deletion & cleanup
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from config import get_settings
from database import connect_to_mongodb, close_mongodb_connection, get_db
from repositories.graph_repository import (
    GraphRepository,
    normalize_entity_name,
    generate_entity_id,
    generate_relationship_id,
)
from schemas.graph_schemas import (
    ExtractedEntity,
    ExtractedRelationship,
    GraphExtractionPayload,
    GraphProcessingStatus,
    RetrievedEvidenceChunk,
    RetrievalMetadata,
)
from services.graph_retrieval_service import (
    extract_query_terms,
    graph_retrieve,
)
from services.hybrid_retrieval_service import (
    hybrid_retrieve,
    normalize_scores,
    combine_and_deduplicate,
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


async def run_graphrag_tests():
    print("=" * 70)
    print("RUNNING GRAPHRAG VERIFICATION TEST SUITE")
    print("=" * 70)

    # ---------------------------------------------------------
    # Test 1: Normalization and ID Generation
    # ---------------------------------------------------------
    print("\n--- Test 1: Schemas, Normalization & ID Generation ---")
    assert normalize_entity_name("  FastAPI  ") == "fastapi"
    assert normalize_entity_name("Deep Learning (DL)") == "deep learning dl"

    id1 = generate_entity_id("proj1", "Convolutional Neural Network")
    id2 = generate_entity_id("proj1", "convolutional neural network")
    id3 = generate_entity_id("proj2", "Convolutional Neural Network")
    assert id1 == id2, "Entity IDs should match regardless of capitalization"
    assert id1 != id3, "Entity IDs must be scoped by project_id"

    rel_id1 = generate_relationship_id("proj1", id1, "proj1_e2", "USES")
    rel_id2 = generate_relationship_id("proj1", id1, "proj1_e2", "uses")
    assert rel_id1 == rel_id2, "Relationship IDs should be consistent regardless of relation casing"
    print("PASS: Normalization and project-scoped ID generation verified.")

    # ---------------------------------------------------------
    # Test 2: Database Indexes & Repository Persistence
    # ---------------------------------------------------------
    print("\n--- Test 2: Repository CRUD & Upsert Merging ---")
    await connect_to_mongodb()
    db = await get_db()
    repo = GraphRepository(db)

    # Verify collections and indexes exist
    colls = await db.list_collection_names()
    assert "graph_entities" in colls, "graph_entities collection must exist"
    assert "graph_relationships" in colls, "graph_relationships collection must exist"
    assert "graph_processing_status" in colls, "graph_processing_status collection must exist"

    ent_indexes = await db.graph_entities.index_information()
    assert "idx_graph_entity_project_user" in ent_indexes, "graph_entities must have project_user index"
    assert "idx_graph_entity_project_entity_id" in ent_indexes, "graph_entities must have unique entity_id index"

    rel_indexes = await db.graph_relationships.index_information()
    assert "idx_graph_rel_project_source_ent" in rel_indexes, "graph_relationships must have source entity index"
    assert "idx_graph_rel_project_rel_id" in rel_indexes, "graph_relationships must have unique relationship_id index"
    print("PASS: MongoDB Atlas GraphRAG collections and compound indexes confirmed.")

    # Test inserting & upserting entities
    user_a = f"test_user_a_{uuid.uuid4().hex[:6]}"
    user_b = f"test_user_b_{uuid.uuid4().hex[:6]}"
    proj_a = f"test_proj_a_{uuid.uuid4().hex[:6]}"
    proj_b = f"test_proj_b_{uuid.uuid4().hex[:6]}"
    src_1 = f"src_1_{uuid.uuid4().hex[:6]}"
    src_2 = f"src_2_{uuid.uuid4().hex[:6]}"

    extracted_entities = [
        ExtractedEntity(
            name="FastAPI",
            entity_type="Technology",
            description="A modern, fast web framework for building APIs with Python.",
            aliases=["FastAPI Framework"],
        ),
        ExtractedEntity(
            name="Pydantic",
            entity_type="Technology",
            description="Data validation library used for request schemas.",
            aliases=["Pydantic v2"],
        ),
    ]

    extracted_relationships = [
        ExtractedRelationship(
            source_entity="FastAPI",
            target_entity="Pydantic",
            relation_type="DEPENDS_ON",
            description="FastAPI leverages Pydantic for data validation and OpenAPI schema generation.",
            weight=0.95,
        )
    ]

    chunk_ids = [f"{src_1}_chunk_0", f"{src_1}_chunk_1"]

    stats = await repo.upsert_extracted_graph(
        user_id=user_a,
        project_id=proj_a,
        source_id=src_1,
        chunk_ids=chunk_ids,
        entities=extracted_entities,
        relationships=extracted_relationships,
    )
    assert stats["entities_created"] == 2
    assert stats["relationships_created"] == 1
    print(f"PASS: Upserted 2 entities and 1 relationship. Created stats: {stats}")

    # Test upsert merging (second source mentions same entity)
    chunk_ids_src2 = [f"{src_2}_chunk_0"]
    extracted_entities_2 = [
        ExtractedEntity(
            name="FastAPI",
            entity_type="Technology",
            description="High-performance async web framework.",
            aliases=["FastAPI Lib"],
        )
    ]
    stats2 = await repo.upsert_extracted_graph(
        user_id=user_a,
        project_id=proj_a,
        source_id=src_2,
        chunk_ids=chunk_ids_src2,
        entities=extracted_entities_2,
        relationships=[],
    )
    assert stats2["entities_updated"] == 1, "Existing entity must be updated/merged, not duplicated"

    fastapi_ent = await repo.find_entity_by_name(user_a, proj_a, "FastAPI")
    assert fastapi_ent is not None
    assert src_1 in fastapi_ent["source_ids"]
    assert src_2 in fastapi_ent["source_ids"], "Entity must track all contributing source IDs"
    assert f"{src_1}_chunk_0" in fastapi_ent["chunk_ids"]
    assert f"{src_2}_chunk_0" in fastapi_ent["chunk_ids"], "Entity must track all chunk IDs"
    print("PASS: Entity merging and multi-source provenance tracking verified.")

    # ---------------------------------------------------------
    # Test 3: Multi-Tenant Data Isolation & Security
    # ---------------------------------------------------------
    print("\n--- Test 3: Multi-Tenant Isolation & Security ---")
    # User B should NOT be able to view or access User A's entities
    user_b_ent = await repo.find_entity_by_name(user_b, proj_a, "FastAPI")
    assert user_b_ent is None, "Cross-user data leakage! User B found User A's entity."

    # Project B should NOT see Project A's entities
    proj_b_ent = await repo.find_entity_by_name(user_a, proj_b, "FastAPI")
    assert proj_b_ent is None, "Cross-project data leakage! Project B found Project A's entity."

    # User B should not see element counts
    counts_b = await repo.count_graph_elements(user_b, proj_a)
    assert counts_b["entity_count"] == 0
    assert counts_b["relationship_count"] == 0

    counts_a = await repo.count_graph_elements(user_a, proj_a)
    assert counts_a["entity_count"] == 2
    assert counts_a["relationship_count"] == 1
    print("PASS: Multi-tenant data isolation strictly enforced across users and projects.")

    # ---------------------------------------------------------
    # Test 4: Graph Retrieval & Multi-Hop Traversal
    # ---------------------------------------------------------
    print("\n--- Test 4: Graph Retrieval & Multi-Hop Traversal ---")
    query = "How does FastAPI work with Pydantic for API schemas?"
    terms = extract_query_terms(query)
    assert "fastapi" in terms
    assert "pydantic" in terms

    # Test graph retrieval execution
    graph_res = await graph_retrieve(
        user_id=user_a,
        project_id=proj_a,
        question=query,
        repo=repo,
        max_hops=2,
    )
    assert len(graph_res["entities"]) >= 2
    assert len(graph_res["relationships"]) >= 1
    assert src_1 in graph_res["supporting_source_ids"]
    print(f"PASS: Graph retrieval extracted {len(graph_res['entities'])} entities, {len(graph_res['relationships'])} relationships.")

    # ---------------------------------------------------------
    # Test 5: Score Normalization & Deduplication
    # ---------------------------------------------------------
    print("\n--- Test 5: Score Normalization & Deduplication ---")
    raw_scores = [1.2, 0.6, 0.0, -0.4]
    norm = normalize_scores(raw_scores)
    assert abs(max(norm) - 1.0) < 1e-4
    assert abs(min(norm) - 0.0) < 1e-4

    # Test combine and deduplicate
    vec_chunks = [
        {"source_id": "src1", "chunk_index": 0, "text": "Content A", "score": 0.8},
        {"source_id": "src1", "chunk_index": 1, "text": "Content B", "score": 0.5},
    ]
    graph_chunks = [
        {
            "source_id": "src1",
            "chunk_index": 0,
            "text": "Content A",
            "score": 0.9,
            "supporting_entities": ["FastAPI"],
            "supporting_relationships": ["DEPENDS_ON"],
        },
        {
            "source_id": "src2",
            "chunk_index": 0,
            "text": "Content C",
            "score": 0.7,
            "supporting_entities": ["Pydantic"],
            "supporting_relationships": [],
        },
    ]
    combined = combine_and_deduplicate(
        vector_chunks=vec_chunks,
        graph_chunks=graph_chunks,
        vector_weight=0.6,
        graph_weight=0.4,
    )
    # The chunk present in both should have method "hybrid"
    overlap = next((c for c in combined if c.get("chunk_index") == 0 and c.get("source_id") == "src1"), None)
    assert overlap is not None
    assert overlap["retrieval_method"] == "hybrid"
    assert "FastAPI" in overlap["supporting_entities"]
    print(f"PASS: Hybrid combination and deduplication confirmed. Total deduplicated chunks: {len(combined)}")

    # ---------------------------------------------------------
    # Test 6: Fallback Gracefulness
    # ---------------------------------------------------------
    print("\n--- Test 6: Graceful Fallback on Missing Index/Graph ---")
    # Calling hybrid retrieval on non-existent project returns empty gracefully without crashing
    res_fallback = await hybrid_retrieve(
        index_id="non_existent_index_12345",
        question="What is this?",
        project_id="non_existent_proj",
        user_id="user_nobody",
        repo=repo,
        rag_mode="hybrid",
    )
    assert "per_source" in res_fallback
    assert res_fallback["retrieval_metadata"]["retrieval_mode"] in ("hybrid", "vector")
    print("PASS: Fallback behavior gracefully returns empty without unhandled exceptions.")

    # ---------------------------------------------------------
    # Test 7: Cascading Deletion & Cleanup
    # ---------------------------------------------------------
    print("\n--- Test 7: Cascading Deletion & Cleanup ---")
    # Delete source 1 from project A
    del_src_res = await repo.delete_source_graph_elements(user_a, proj_a, src_1)
    # Source 2 still references FastAPI, so entity should still exist with source 2
    fastapi_after = await repo.find_entity_by_name(user_a, proj_a, "FastAPI")
    assert fastapi_after is not None
    assert src_1 not in fastapi_after["source_ids"]
    assert src_2 in fastapi_after["source_ids"]
    print("PASS: Source deletion pruned source references while preserving shared entity.")

    # Delete entire project A
    del_proj_res = await repo.delete_project_graph(user_a, proj_a)
    assert del_proj_res["entities_deleted"] >= 1
    counts_after = await repo.count_graph_elements(user_a, proj_a)
    assert counts_after["entity_count"] == 0
    assert counts_after["relationship_count"] == 0
    print(f"PASS: Project graph purge verified. Cleaned: {del_proj_res}")

    await close_mongodb_connection()
    print("\n" + "=" * 70)
    print("ALL GRAPHRAG VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_graphrag_tests())
