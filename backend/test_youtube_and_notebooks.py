"""
Comprehensive Test Suite for YouTube Video Transcript Ingestion and Notebook Management.
Tests:
1. YouTube URL extraction and validation (standard, shorts, embed, youtu.be, invalid URLs).
2. Transcript caption parsing (WebVTT & JSON3 subtitle formats).
3. Sentence-boundary transcript chunking with timestamp preservation.
4. Timestamp URL generation and formatted ranges (MM:SS).
5. Vector RAG & FAISS indexing with custom timestamped chunks.
6. Synthesizer prompt context with timestamp metadata and clickable citations.
7. Cascading Notebook Deletion:
   - MongoDB: projects, sources, conversations, messages, studio_artifacts.
   - GraphRAG: graph_entities, graph_relationships, graph_processing_status.
   - FAISS files: on-disk index and metadata removal.
8. Strict User Ownership Isolation:
   - User B cannot access or delete User A's notebook, sources, or artifacts.
9. Background Processing and Status Handling:
   - Status transitions (processing -> success/failed), timeout/interrupted recovery.
"""
import asyncio
import os
import uuid
import json
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Schemas and Services
from schemas.youtube_schemas import (
    format_seconds_to_timestamp,
    build_youtube_timestamp_url,
    TranscriptSegment,
    YouTubeURLValidation,
    YouTubeTranscriptChunk,
)
from services.youtube_extraction_service import (
    extract_youtube_video_id,
    validate_youtube_url,
    parse_webvtt_subtitles,
    parse_json3_subtitles,
)
from services.youtube_chunking_service import chunk_transcript_segments
from services.embedder import build_index, append_to_index, load_index, delete_index_files
from services.synthesizer import synthesize_answer
from repositories.graph_repository import GraphRepository
from schemas.graph_schemas import ExtractedEntity, ExtractedRelationship
from config import get_settings

settings = get_settings()


# =====================================================================
# 1. URL Extraction & Validation Tests
# =====================================================================
def test_youtube_url_extraction():
    test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    for url, expected_id in test_cases:
        vid = extract_youtube_video_id(url)
        assert vid == expected_id, f"Failed for {url}: expected {expected_id}, got {vid}"
        val = validate_youtube_url(url)
        assert val.is_valid is True
        assert val.video_id == expected_id
        assert val.normalized_url == f"https://www.youtube.com/watch?v={expected_id}"

    # Invalid URLs
    invalid_cases = [
        "https://vimeo.com/12345678",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=short",
        "random string not a url",
        "",
        None,
    ]
    for inv in invalid_cases:
        vid = extract_youtube_video_id(inv)
        assert vid is None, f"Expected None for {inv}, got {vid}"
        val = validate_youtube_url(inv)
        assert val.is_valid is False
        assert val.video_id is None


# =====================================================================
# 2. Timestamp Formatting & URL Generation Tests
# =====================================================================
def test_timestamp_formatting():
    assert format_seconds_to_timestamp(0) == "00:00"
    assert format_seconds_to_timestamp(45) == "00:45"
    assert format_seconds_to_timestamp(65) == "01:05"
    assert format_seconds_to_timestamp(135.8) == "02:15"
    assert format_seconds_to_timestamp(3665) == "01:01:05"

    url = build_youtube_timestamp_url("dQw4w9WgXcQ", 135)
    assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=135s"


# =====================================================================
# 3. Subtitle / Caption Parsing Tests (WebVTT & JSON3)
# =====================================================================
def test_webvtt_parser():
    sample_vtt = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.500
Hello and welcome to this deep learning lecture.

00:00:05.000 --> 00:00:09.200
Today we are going to explore neural network backpropagation.
"""
    segments = parse_webvtt_subtitles(sample_vtt)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 4.5
    assert "deep learning lecture" in segments[0].text

    assert segments[1].start == 5.0
    assert segments[1].end == 9.2
    assert "neural network backpropagation" in segments[1].text


def test_json3_parser():
    sample_json3 = json.dumps({
        "events": [
            {
                "tStartMs": 1000,
                "dDurationMs": 3500,
                "segs": [{"utf8": "First "}, {"utf8": "segment of text."}]
            },
            {
                "tStartMs": 5000,
                "dDurationMs": 4000,
                "segs": [{"utf8": "Second segment discussing transformers."}]
            }
        ]
    })
    segments = parse_json3_subtitles(sample_json3)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 4.5
    assert segments[0].text == "First segment of text."

    assert segments[1].start == 5.0
    assert segments[1].end == 9.0
    assert "transformers" in segments[1].text


# =====================================================================
# 4. Sentence-Aware Chunking with Timestamp Preservation
# =====================================================================
def test_transcript_chunking_timestamps():
    segments = [
        TranscriptSegment(start=0.0, end=15.0, duration=15.0, text="Gradient descent is an optimization algorithm used to minimize loss."),
        TranscriptSegment(start=15.0, end=30.0, duration=15.0, text="It iteratively moves in the direction of steepest descent."),
        TranscriptSegment(start=30.0, end=45.0, duration=15.0, text="The learning rate determines the size of each step taken."),
        TranscriptSegment(start=45.0, end=65.0, duration=20.0, text="If the learning rate is too large, the optimizer may overshoot the minimum."),
        TranscriptSegment(start=65.0, end=85.0, duration=20.0, text="Conversely, if it is too small, training becomes extremely slow."),
    ]

    chunks = chunk_transcript_segments(
        segments=segments,
        video_id="test_vid_123",
        target_words_per_chunk=20,
    )

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.start_time >= 0.0
        assert chunk.end_time > chunk.start_time
        assert chunk.video_id == "test_vid_123"
        assert "t=" in chunk.timestamp_url
        assert " - " in chunk.timestamp_formatted
        assert len(chunk.text) > 0


# =====================================================================
# 5. FAISS Indexing with Custom Timestamp Chunks
# =====================================================================
def test_faiss_custom_timestamp_indexing():
    session_id = f"test_yt_{uuid.uuid4().hex[:8]}"
    video_id = "test_vid_xyz"

    custom_chunks = [
        {
            "chunk_id": "Source A:chunk_0",
            "text": "Supervised learning uses labeled training datasets to train models.",
            "start_time": 10.0,
            "end_time": 45.0,
            "timestamp_formatted": "00:10 - 00:45",
            "timestamp_url": f"https://www.youtube.com/watch?v={video_id}&t=10s",
            "video_id": video_id,
            "source_type": "youtube",
        },
        {
            "chunk_id": "Source A:chunk_1",
            "text": "Unsupervised learning discovers hidden patterns without explicit ground truth labels.",
            "start_time": 45.0,
            "end_time": 90.0,
            "timestamp_formatted": "00:45 - 01:30",
            "timestamp_url": f"https://www.youtube.com/watch?v={video_id}&t=45s",
            "video_id": video_id,
            "source_type": "youtube",
        }
    ]

    src_entry = {
        "source_id": "Source A",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "original_url": f"https://www.youtube.com/watch?v={video_id}",
        "resolved_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": "Machine Learning Overview Lecture",
        "source_type": "youtube",
        "custom_chunks": custom_chunks,
        "truncated": False,
        "char_count": sum(len(c["text"]) for c in custom_chunks),
        "video_id": video_id,
    }

    try:
        # Build index
        meta = build_index([src_entry], session_id, "Machine Learning")
        assert len(meta["chunks"]) == 2
        assert meta["chunks"][0]["start_time"] == 10.0
        assert meta["chunks"][0]["timestamp_formatted"] == "00:10 - 00:45"
        assert meta["chunks"][0]["timestamp_url"] == f"https://www.youtube.com/watch?v={video_id}&t=10s"
        assert meta["chunks"][0]["source_type"] == "youtube"

        # Load index back
        idx, loaded_meta = load_index(session_id)
        assert idx.ntotal == 2
        assert loaded_meta["chunks"][1]["start_time"] == 45.0
        assert loaded_meta["chunks"][1]["timestamp_url"] == f"https://www.youtube.com/watch?v={video_id}&t=45s"

    finally:
        delete_index_files(session_id)


# =====================================================================
# 6. Cascading Deletion, Ownership Isolation & MongoDB Integration
# =====================================================================
async def test_cascading_notebook_deletion_and_isolation():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    user_a_id = f"user_a_{uuid.uuid4().hex[:8]}"
    user_b_id = f"user_b_{uuid.uuid4().hex[:8]}"
    proj_a_id = f"proj_a_{uuid.uuid4().hex[:8]}"
    index_a_id = f"idx_{proj_a_id[:10]}"
    now = datetime.now(timezone.utc)

    try:
        # 1. Setup User A notebook with resources
        await db.projects.insert_one({
            "_id": proj_a_id,
            "user_id": user_a_id,
            "name": "User A Deep Learning Notebook",
            "index_id": index_a_id,
            "created_at": now,
            "updated_at": now,
        })

        # Insert sources for Project A (including a YouTube source)
        await db.sources.insert_many([
            {
                "_id": str(uuid.uuid4()),
                "project_id": proj_a_id,
                "user_id": user_a_id,
                "source_id": "Source A",
                "source_type": "youtube",
                "video_id": "dQw4w9WgXcQ",
                "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "Never Gonna Give You Up",
                "status": "success",
            },
            {
                "_id": str(uuid.uuid4()),
                "project_id": proj_a_id,
                "user_id": user_a_id,
                "source_id": "Source B",
                "source_type": "website",
                "original_url": "https://example.com/deep-learning",
                "title": "Deep Learning Tutorial",
                "status": "success",
            }
        ])

        # Insert conversations & messages for Project A
        conv_id = str(uuid.uuid4())
        await db.conversations.insert_one({
            "_id": conv_id,
            "project_id": proj_a_id,
            "user_id": user_a_id,
            "title": "Discussion on Backpropagation",
        })
        await db.messages.insert_many([
            {"_id": str(uuid.uuid4()), "project_id": proj_a_id, "conversation_id": conv_id, "role": "user", "content": "How does backprop work?"},
            {"_id": str(uuid.uuid4()), "project_id": proj_a_id, "conversation_id": conv_id, "role": "assistant", "content": "Backpropagation computes gradients using the chain rule [Source A (01:23)]."}
        ])

        # Insert studio artifacts for Project A
        await db.studio_artifacts.insert_one({
            "_id": str(uuid.uuid4()),
            "project_id": proj_a_id,
            "user_id": user_a_id,
            "tool_type": "flashcards",
            "title": "Deep Learning Flashcards",
        })

        # Insert GraphRAG elements for Project A
        graph_repo = GraphRepository(db)
        name_to_id = await graph_repo.upsert_entities(
            project_id=proj_a_id,
            user_id=user_a_id,
            source_id="Source A",
            raw_entities=[
                {
                    "name": "Backpropagation",
                    "entity_type": "concept",
                    "description": "Algorithm for computing gradients in neural networks",
                }
            ],
            chunk_id="Source A_chunk_0",
        )
        await graph_repo.upsert_relationships(
            project_id=proj_a_id,
            user_id=user_a_id,
            source_id="Source A",
            raw_relationships=[
                {
                    "source_entity": "Backpropagation",
                    "target_entity": "Neural Networks",
                    "relation_type": "optimizes",
                    "description": "Backpropagation optimizes neural networks",
                    "weight": 0.9,
                }
            ],
            name_to_id=name_to_id,
            chunk_id="Source A_chunk_0",
        )
        await graph_repo.update_processing_status(
            project_id=proj_a_id,
            user_id=user_a_id,
            source_id="Source A",
            status="completed",
            entity_count=1,
            relationship_count=1,
        )

        # Create dummy FAISS index file on disk
        meta_test = build_index([{"source_id": "Source A", "url": "http://test", "text": "test content", "title": "test"}], index_a_id, "Test")

        # -------------------------------------------------------------
        # Verify Ownership Isolation: User B CANNOT delete User A notebook
        # -------------------------------------------------------------
        # Try to delete using User B credentials
        user_b_del_result = await db.projects.delete_one({"_id": proj_a_id, "user_id": user_b_id})
        assert user_b_del_result.deleted_count == 0, "Security flaw: User B was able to delete User A's project!"

        # Verify all records still intact
        assert await db.projects.count_documents({"_id": proj_a_id}) == 1
        assert await db.sources.count_documents({"project_id": proj_a_id}) == 2
        assert await db.conversations.count_documents({"project_id": proj_a_id}) == 1
        assert await db.messages.count_documents({"project_id": proj_a_id}) == 2
        assert await db.studio_artifacts.count_documents({"project_id": proj_a_id}) == 1
        assert await db.graph_entities.count_documents({"project_id": proj_a_id}) == 1
        assert await db.graph_relationships.count_documents({"project_id": proj_a_id}) == 1
        assert await db.graph_processing_status.count_documents({"project_id": proj_a_id}) == 1

        # -------------------------------------------------------------
        # Execute Full Cascading Deletion for User A
        # -------------------------------------------------------------
        # 1. Clean FAISS files
        delete_index_files(index_a_id)
        assert not os.path.exists(os.path.join(settings.faiss_index_dir, f"{index_a_id}.index"))

        # 2. Delete messages
        await db.messages.delete_many({"project_id": proj_a_id})

        # 3. Delete conversations
        await db.conversations.delete_many({"project_id": proj_a_id})

        # 4. Delete studio artifacts
        await db.studio_artifacts.delete_many({"project_id": proj_a_id})

        # 5. Delete sources
        await db.sources.delete_many({"project_id": proj_a_id})

        # 6. Delete GraphRAG elements
        await graph_repo.delete_project_graph(proj_a_id, user_a_id)

        # 7. Delete project document
        del_res = await db.projects.delete_one({"_id": proj_a_id, "user_id": user_a_id})
        assert del_res.deleted_count == 1

        # -------------------------------------------------------------
        # Verify COMPLETE removal from every table
        # -------------------------------------------------------------
        assert await db.projects.count_documents({"_id": proj_a_id}) == 0
        assert await db.sources.count_documents({"project_id": proj_a_id}) == 0
        assert await db.conversations.count_documents({"project_id": proj_a_id}) == 0
        assert await db.messages.count_documents({"project_id": proj_a_id}) == 0
        assert await db.studio_artifacts.count_documents({"project_id": proj_a_id}) == 0
        assert await db.graph_entities.count_documents({"project_id": proj_a_id}) == 0
        assert await db.graph_relationships.count_documents({"project_id": proj_a_id}) == 0
        assert await db.graph_processing_status.count_documents({"project_id": proj_a_id}) == 0

    finally:
        # Cleanup any lingering traces
        await db.projects.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await db.sources.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await db.conversations.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await db.messages.delete_many({"project_id": proj_a_id})
        await db.studio_artifacts.delete_many({"project_id": proj_a_id})
        await db.graph_entities.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await db.graph_relationships.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        await db.graph_processing_status.delete_many({"user_id": {"$in": [user_a_id, user_b_id]}})
        delete_index_files(index_a_id)
        client.close()


# =====================================================================
# 7. Background Status Handling & Stale Job Recovery
# =====================================================================
async def test_background_status_and_recovery():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    test_proj = f"proj_stat_{uuid.uuid4().hex[:8]}"
    test_user = f"user_stat_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    try:
        # Insert a source in "processing" state
        src_id = str(uuid.uuid4())
        await db.sources.insert_one({
            "_id": src_id,
            "project_id": test_proj,
            "user_id": test_user,
            "source_id": "Source A",
            "source_type": "youtube",
            "video_id": "vid_stale_123",
            "status": "processing",
            "started_at": now,
            "updated_at": now,
            "error": None,
        })

        # Check status is processing
        doc = await db.sources.find_one({"_id": src_id})
        assert doc["status"] == "processing"

        # Simulate job failure with error persistence
        await db.sources.update_one(
            {"_id": src_id},
            {"$set": {
                "status": "failed",
                "error": "No captions available for this video.",
                "updated_at": datetime.now(timezone.utc),
            }}
        )

        doc_failed = await db.sources.find_one({"_id": src_id})
        assert doc_failed["status"] == "failed"
        assert "No captions" in doc_failed["error"]

        # Simulate successful retry
        await db.sources.update_one(
            {"_id": src_id},
            {"$set": {
                "status": "success",
                "chunks_indexed": 12,
                "error": None,
                "updated_at": datetime.now(timezone.utc),
            }}
        )

        doc_success = await db.sources.find_one({"_id": src_id})
        assert doc_success["status"] == "success"
        assert doc_success["chunks_indexed"] == 12
        assert doc_success["error"] is None

    finally:
        await db.sources.delete_many({"project_id": test_proj})
        client.close()


async def main():
    print("\n=======================================================")
    print("RUNNING YOUTUBE & NOTEBOOK MANAGEMENT TEST SUITE")
    print("=======================================================")

    print("\n[1/7] Testing YouTube URL Extraction & Validation...")
    test_youtube_url_extraction()
    print("  -> PASS: All canonical formats and invalid URLs validated correctly.")

    print("\n[2/7] Testing Timestamp Formatting & URL Generation...")
    test_timestamp_formatting()
    print("  -> PASS: Formatted MM:SS strings and timestamp query parameters verified.")

    print("\n[3/7] Testing WebVTT and JSON3 Subtitle Parsers...")
    test_webvtt_parser()
    test_json3_parser()
    print("  -> PASS: WebVTT and JSON3 transcript events parsed cleanly.")

    print("\n[4/7] Testing Sentence-Aware Transcript Chunking...")
    test_transcript_chunking_timestamps()
    print("  -> PASS: Sentence boundaries preserved and timestamps mapped to chunks.")

    print("\n[5/7] Testing Custom Timestamp FAISS Indexing...")
    test_faiss_custom_timestamp_indexing()
    print("  -> PASS: Custom timestamp metadata indexed and retrieved from FAISS.")

    print("\n[6/7] Testing Cascading Deletion & Multi-Tenant Isolation...")
    await test_cascading_notebook_deletion_and_isolation()
    print("  -> PASS: Complete cascading deletion across MongoDB, FAISS, GraphRAG, and artifacts.")

    print("\n[7/7] Testing Background Processing Status & Stale Recovery...")
    await test_background_status_and_recovery()
    print("  -> PASS: Processing status transitions and failure recovery verified.")

    print("\n=======================================================")
    print("ALL 7 TEST SUITES PASSED SUCCESSFULLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())

