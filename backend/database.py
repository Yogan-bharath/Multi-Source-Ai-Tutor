"""
MongoDB Connection Lifecycle and Index Management using Motor (AsyncIO).
"""
import logging
from typing import Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pymongo

from config import get_settings

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_manager = DatabaseManager()

def get_utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)

async def connect_to_mongodb():
    """Initialize shared AsyncIOMotorClient and ensure database indexes."""
    if not settings.mongodb_uri:
        logger.warning("[MongoDB] MONGODB_URI is not set. Database operations will fail.")
        return

    try:
        logger.info(f"[MongoDB] Connecting to database: {settings.mongodb_database}...")
        db_manager.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_server_timeout_ms,
            uuidRepresentation="standard",
        )
        # Test connection
        await db_manager.client.admin.command("ping")
        db_manager.db = db_manager.client[settings.mongodb_database]
        logger.info("[MongoDB] Connected successfully to MongoDB Atlas!")

        # Initialize collections and indexes
        await init_db_indexes()
    except Exception as exc:
        logger.error(f"[MongoDB] Connection failed: {exc}")
        db_manager.client = None
        db_manager.db = None

async def close_mongodb_connection():
    """Close the shared AsyncIOMotorClient."""
    if db_manager.client:
        logger.info("[MongoDB] Closing MongoDB client connection...")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None

async def init_db_indexes():
    """Ensure indexes for users, projects, sources, conversations, and messages."""
    db = db_manager.db
    if db is None:
        return

    try:
        # 1. users: unique email (case-insensitive / normalized)
        await db.users.create_index(
            [("email", pymongo.ASCENDING)],
            unique=True,
            name="uniq_user_email"
        )
        await db.users.create_index([("created_at", pymongo.DESCENDING)], name="idx_user_created")

        # 2. projects: user ownership and recent activity
        await db.projects.create_index([("user_id", pymongo.ASCENDING)], name="idx_project_user")
        await db.projects.create_index(
            [("user_id", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)],
            name="idx_project_user_updated"
        )

        # 3. sources: project isolation, ownership, and source_id lookup
        await db.sources.create_index([("project_id", pymongo.ASCENDING)], name="idx_source_project")
        await db.sources.create_index(
            [("project_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
            name="idx_source_project_user"
        )
        await db.sources.create_index(
            [("project_id", pymongo.ASCENDING), ("source_id", pymongo.ASCENDING)],
            name="idx_source_project_source_id"
        )

        # 4. conversations: project history and user recent conversations
        await db.conversations.create_index(
            [("project_id", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)],
            name="idx_conversation_project_updated"
        )
        await db.conversations.create_index(
            [("user_id", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)],
            name="idx_conversation_user_updated"
        )

        # 5. messages: conversation ordering by timestamp
        await db.messages.create_index(
            [("conversation_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)],
            name="idx_message_conversation_created"
        )
        await db.messages.create_index(
            [("user_id", pymongo.ASCENDING), ("project_id", pymongo.ASCENDING)],
            name="idx_message_user_project"
        )

        # 6. graph_entities: project isolation, normalized name lookup, entity_id lookup, and source reference
        await db.graph_entities.create_index(
            [("project_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
            name="idx_graph_entity_project_user"
        )
        await db.graph_entities.create_index(
            [("project_id", pymongo.ASCENDING), ("name_normalized", pymongo.ASCENDING)],
            name="idx_graph_entity_project_normalized"
        )
        await db.graph_entities.create_index(
            [("project_id", pymongo.ASCENDING), ("entity_id", pymongo.ASCENDING)],
            unique=True,
            name="idx_graph_entity_project_entity_id"
        )
        await db.graph_entities.create_index(
            [("project_id", pymongo.ASCENDING), ("source_ids", pymongo.ASCENDING)],
            name="idx_graph_entity_project_sources"
        )

        # 7. graph_relationships: source & target traversal, relationship lookup, project isolation
        await db.graph_relationships.create_index(
            [("project_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
            name="idx_graph_rel_project_user"
        )
        await db.graph_relationships.create_index(
            [("project_id", pymongo.ASCENDING), ("source_entity_id", pymongo.ASCENDING)],
            name="idx_graph_rel_project_source_ent"
        )
        await db.graph_relationships.create_index(
            [("project_id", pymongo.ASCENDING), ("target_entity_id", pymongo.ASCENDING)],
            name="idx_graph_rel_project_target_ent"
        )
        await db.graph_relationships.create_index(
            [("project_id", pymongo.ASCENDING), ("relationship_id", pymongo.ASCENDING)],
            unique=True,
            name="idx_graph_rel_project_rel_id"
        )
        await db.graph_relationships.create_index(
            [("project_id", pymongo.ASCENDING), ("source_ids", pymongo.ASCENDING)],
            name="idx_graph_rel_project_sources"
        )

        # 8. graph_processing_status: track status per project & source
        await db.graph_processing_status.create_index(
            [("project_id", pymongo.ASCENDING), ("source_id", pymongo.ASCENDING)],
            unique=True,
            name="idx_graph_status_project_source"
        )
        await db.graph_processing_status.create_index(
            [("user_id", pymongo.ASCENDING), ("project_id", pymongo.ASCENDING)],
            name="idx_graph_status_user_project"
        )

        logger.info("[MongoDB] All collection indexes initialized successfully.")
    except Exception as exc:
        logger.error(f"[MongoDB] Error initializing indexes: {exc}")

async def get_db() -> AsyncIOMotorDatabase:
    """Dependency that yields the shared MongoDB database instance."""
    if db_manager.db is None:
        raise RuntimeError("MongoDB connection is not established. Check MONGODB_URI and network access.")
    return db_manager.db

async def check_db_health() -> bool:
    """Return True if MongoDB ping succeeds."""
    if db_manager.client is None:
        return False
    try:
        res = await db_manager.client.admin.command("ping")
        return res.get("ok") == 1
    except Exception:
        return False
