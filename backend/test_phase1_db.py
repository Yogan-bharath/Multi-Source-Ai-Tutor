"""
Test suite for Phase 1: MongoDB Configuration, Lifecycles, Collections, Indexes, and Models.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
import pymongo.errors

from config import get_settings
from database import connect_to_mongodb, close_mongodb_connection, get_db, db_manager, get_utc_now
from models import UserRegisterRequest, ProjectCreateRequest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

async def run_phase1_tests():
    print("="*60)
    print("RUNNING PHASE 1 TESTS: MongoDB Lifecycle & Indexes")
    print("="*60)

    # 1. Connect
    await connect_to_mongodb()
    assert db_manager.client is not None, "MongoDB client must be initialized"
    assert db_manager.db is not None, "Database instance must be initialized"
    print("PASS: MongoDB Atlas connection established.")

    db = await get_db()

    # 2. Verify collection indexes
    collections = await db.list_collection_names()
    print(f"Collections present: {collections}")

    user_indexes = await db.users.index_information()
    assert "uniq_user_email" in user_indexes, "Users collection must have uniq_user_email index"
    print("PASS: users collection has unique email index.")

    project_indexes = await db.projects.index_information()
    assert "idx_project_user" in project_indexes
    print("PASS: projects collection has user_id index.")

    source_indexes = await db.sources.index_information()
    assert "idx_source_project" in source_indexes
    print("PASS: sources collection has project_id index.")

    conv_indexes = await db.conversations.index_information()
    assert "idx_conversation_project_updated" in conv_indexes
    print("PASS: conversations collection has project index.")

    msg_indexes = await db.messages.index_information()
    assert "idx_message_conversation_created" in msg_indexes
    print("PASS: messages collection has conversation ordering index.")

    # 3. Test unique email constraint
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    user_doc = {
        "_id": str(uuid.uuid4()),
        "name": "Test User",
        "email": test_email,
        "password_hash": "dummy_hash",
        "created_at": get_utc_now(),
        "updated_at": get_utc_now(),
        "is_active": True,
    }
    await db.users.insert_one(user_doc)

    # Attempt inserting duplicate email
    duplicate_doc = {
        "_id": str(uuid.uuid4()),
        "name": "Duplicate User",
        "email": test_email,
        "password_hash": "dummy_hash_2",
        "created_at": get_utc_now(),
        "updated_at": get_utc_now(),
        "is_active": True,
    }
    duplicate_caught = False
    try:
        await db.users.insert_one(duplicate_doc)
    except pymongo.errors.DuplicateKeyError:
        duplicate_caught = True

    assert duplicate_caught, "Inserting duplicate email must raise DuplicateKeyError"
    print("PASS: Duplicate email correctly blocked by MongoDB unique index.")

    # Clean up test user
    await db.users.delete_one({"_id": user_doc["_id"]})

    # 4. Close connection cleanly
    await close_mongodb_connection()
    assert db_manager.client is None
    print("PASS: MongoDB client closed cleanly.")

    print("\n" + "="*60)
    print("ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_phase1_tests())
