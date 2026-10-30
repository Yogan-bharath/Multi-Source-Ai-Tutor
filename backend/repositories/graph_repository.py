"""
Graph Repository: MongoDB persistence and isolation for GraphRAG Entities, Relationships, and Ingestion Status.
Strictly scoped by user_id and project_id for multi-tenant data isolation.
"""
import re
import uuid
from typing import List, Dict, Optional, Any, Set
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo
import networkx as nx

from database import get_utc_now


def normalize_entity_name(name: str) -> str:
    """
    Standardize entity name for canonical indexing and deduplication:
    lowercase, remove outer punctuation and normalize multiple spaces.
    """
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s\-\.]", "", name.strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def generate_entity_id(project_id: str, name: str) -> str:
    """Deterministic entity ID within a project scope."""
    norm = normalize_entity_name(name)
    safe_name = re.sub(r"[^a-z0-9_\-]", "_", norm)[:48]
    return f"ent_{project_id}_{safe_name}"


def generate_relationship_id(project_id: str, source_ent_id: str, target_ent_id: str, rel_type: str) -> str:
    """Deterministic relationship ID within a project scope."""
    safe_rel = re.sub(r"[^a-z0-9_]", "_", rel_type.lower())[:32]
    return f"rel_{project_id}_{source_ent_id[-16:]}_{safe_rel}_{target_ent_id[-16:]}"


class GraphRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def update_processing_status(
        self,
        project_id: str,
        user_id: str,
        source_id: str,
        status: str,
        entity_count: int = 0,
        relationship_count: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Record or update graph extraction status for a source."""
        now = get_utc_now()
        status_id = f"{project_id}:{source_id}"
        update_doc = {
            "project_id": project_id,
            "user_id": user_id,
            "source_id": source_id,
            "status": status,
            "entity_count": entity_count,
            "relationship_count": relationship_count,
            "error": error,
            "updated_at": now,
        }
        await self.db.graph_processing_status.update_one(
            {"project_id": project_id, "source_id": source_id},
            {
                "$set": update_doc,
                "$setOnInsert": {"_id": status_id, "created_at": now},
            },
            upsert=True,
        )

    async def get_processing_status(
        self,
        project_id: str,
        user_id: str,
        source_id: str,
    ) -> Optional[dict]:
        """Fetch graph processing status respecting user & project isolation."""
        return await self.db.graph_processing_status.find_one(
            {"project_id": project_id, "user_id": user_id, "source_id": source_id}
        )

    async def upsert_entities(
        self,
        project_id: str,
        user_id: str,
        source_id: str,
        raw_entities: List[dict],
        chunk_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Merge/upsert entities into graph_entities collection.
        Returns a mapping of normalized_name -> entity_id.
        """
        now = get_utc_now()
        name_to_id: Dict[str, str] = {}

        for item in raw_entities:
            name = item.get("name", "").strip()
            if not name:
                continue

            normalized = normalize_entity_name(name)
            if not normalized or len(normalized) < 2:
                continue

            entity_id = generate_entity_id(project_id, normalized)
            name_to_id[normalized] = entity_id

            chunk_ids = [chunk_id] if chunk_id else item.get("chunk_ids", [])
            aliases = [a.strip() for a in item.get("aliases", []) if a.strip() and a.strip().lower() != normalized]

            # Upsert using $addToSet for deduplication of source_ids and chunk_ids
            filter_query = {
                "_id": entity_id,
            }

            update_ops: Dict[str, Any] = {
                "$set": {
                    "name": name,
                    "name_normalized": normalized,
                    "entity_type": item.get("entity_type", "Concept"),
                    "project_id": project_id,
                    "user_id": user_id,
                    "entity_id": entity_id,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "_id": entity_id,
                    "created_at": now,
                },
                "$addToSet": {
                    "source_ids": source_id,
                },
            }

            if item.get("description"):
                # Retain or enrich description
                update_ops["$set"]["description"] = item["description"]

            if chunk_ids:
                update_ops["$addToSet"]["chunk_ids"] = {"$each": chunk_ids}

            if aliases:
                update_ops["$addToSet"]["aliases"] = {"$each": aliases}

            await self.db.graph_entities.update_one(filter_query, update_ops, upsert=True)

        return name_to_id

    async def upsert_relationships(
        self,
        project_id: str,
        user_id: str,
        source_id: str,
        raw_relationships: List[dict],
        name_to_id: Dict[str, str],
        chunk_id: Optional[str] = None,
    ) -> int:
        """
        Merge/upsert relationships into graph_relationships collection.
        Resolves entity IDs using name_to_id or looks up existing entities in project.
        """
        now = get_utc_now()
        inserted_or_updated = 0

        for rel in raw_relationships:
            src_name = rel.get("source_entity", "").strip()
            tgt_name = rel.get("target_entity", "").strip()
            rel_type = rel.get("relation_type", "RELATED_TO").strip().upper().replace(" ", "_")

            if not src_name or not tgt_name or not rel_type:
                continue

            src_norm = normalize_entity_name(src_name)
            tgt_norm = normalize_entity_name(tgt_name)

            if not src_norm or not tgt_norm or src_norm == tgt_norm:
                continue

            # Resolve entity IDs
            src_id = name_to_id.get(src_norm) or generate_entity_id(project_id, src_norm)
            tgt_id = name_to_id.get(tgt_norm) or generate_entity_id(project_id, tgt_norm)

            rel_id = generate_relationship_id(project_id, src_id, tgt_id, rel_type)
            chunk_ids = [chunk_id] if chunk_id else rel.get("chunk_ids", [])

            filter_query = {
                "_id": rel_id,
            }

            update_ops: Dict[str, Any] = {
                "$set": {
                    "source_entity_name": src_name,
                    "target_entity_name": tgt_name,
                    "relation_type": rel_type,
                    "weight": float(rel.get("weight", 1.0)),
                    "description": rel.get("description", ""),
                    "project_id": project_id,
                    "user_id": user_id,
                    "relationship_id": rel_id,
                    "source_entity_id": src_id,
                    "target_entity_id": tgt_id,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "_id": rel_id,
                    "created_at": now,
                },
                "$addToSet": {
                    "source_ids": source_id,
                },
            }

            if chunk_ids:
                update_ops["$addToSet"]["chunk_ids"] = {"$each": chunk_ids}

            await self.db.graph_relationships.update_one(filter_query, update_ops, upsert=True)
            inserted_or_updated += 1

        return inserted_or_updated

    async def upsert_extracted_graph(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
        chunk_ids: List[str],
        entities: List[Any],
        relationships: List[Any],
    ) -> Dict[str, int]:
        """Convenience method to upsert entities and relationships together and track counts."""
        raw_ents = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in entities]
        raw_rels = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in relationships]
        for ent in raw_ents:
            ent["chunk_ids"] = chunk_ids
        for rel in raw_rels:
            rel["chunk_ids"] = chunk_ids

        before_count = await self.db.graph_entities.count_documents({"user_id": user_id, "project_id": project_id})
        name_to_id = await self.upsert_entities(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            raw_entities=raw_ents,
        )
        after_count = await self.db.graph_entities.count_documents({"user_id": user_id, "project_id": project_id})
        created_ents = after_count - before_count
        updated_ents = len(name_to_id) - created_ents

        rel_count = await self.upsert_relationships(
            project_id=project_id,
            user_id=user_id,
            source_id=source_id,
            raw_relationships=raw_rels,
            name_to_id=name_to_id,
        )
        return {
            "entities_created": created_ents,
            "entities_updated": updated_ents,
            "relationships_created": rel_count,
        }

    async def find_entity_by_name(
        self,
        user_id: str,
        project_id: str,
        name: str,
    ) -> Optional[dict]:
        """Find a single entity by name within project."""
        norm = normalize_entity_name(name)
        return await self.db.graph_entities.find_one({
            "project_id": project_id,
            "user_id": user_id,
            "$or": [
                {"name_normalized": norm},
                {"name": name},
                {"aliases": norm},
            ],
        })

    async def search_entities_by_terms(
        self,
        project_id: str,
        user_id: str,
        terms: List[str],
        limit: int = 20,
    ) -> List[dict]:
        """
        Match entities in project by matching terms against normalized name or aliases.
        Guarantees user and project isolation.
        """
        if not terms:
            return []

        cleaned_terms = [normalize_entity_name(t) for t in terms if normalize_entity_name(t)]
        if not cleaned_terms:
            return []

        # Exact match or regex pattern match
        regex_patterns = [re.escape(t) for t in cleaned_terms]
        regex_query = "|".join(regex_patterns)

        query = {
            "project_id": project_id,
            "user_id": user_id,
            "$or": [
                {"name_normalized": {"$in": cleaned_terms}},
                {"name_normalized": {"$regex": regex_query, "$options": "i"}},
                {"aliases": {"$in": cleaned_terms}},
            ],
        }

        cursor = self.db.graph_entities.find(query).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_relationships_for_entities(
        self,
        project_id: str,
        user_id: str,
        entity_ids: List[str],
        limit: int = 50,
    ) -> List[dict]:
        """
        Find all relationships where either source or target entity is in entity_ids.
        Guarantees user and project isolation.
        """
        if not entity_ids:
            return []

        query = {
            "project_id": project_id,
            "user_id": user_id,
            "$or": [
                {"source_entity_id": {"$in": entity_ids}},
                {"target_entity_id": {"$in": entity_ids}},
            ],
        }

        cursor = self.db.graph_relationships.find(query).limit(limit)
        return await cursor.to_list(length=limit)

    async def traverse_subgraph(
        self,
        project_id: str,
        user_id: str,
        seed_entity_ids: List[str],
        max_hops: int = 2,
        max_relationships: int = 30,
        max_entities: int = 25,
    ) -> Dict[str, Any]:
        """
        Bounded multi-hop graph traversal starting from seed entities.
        Constructs an in-memory NetworkX DiGraph from candidate relationships within the project,
        performs BFS/DFS up to max_hops, and returns the connected entities & relationships.
        """
        if not seed_entity_ids:
            return {"entities": [], "relationships": [], "paths": []}

        visited_entity_ids: Set[str] = set(seed_entity_ids)
        current_layer = set(seed_entity_ids)
        collected_rel_docs: Dict[str, dict] = {}

        # Traversal loop up to max_hops
        for hop in range(max_hops):
            if not current_layer or len(collected_rel_docs) >= max_relationships:
                break

            rels = await self.get_relationships_for_entities(
                project_id=project_id,
                user_id=user_id,
                entity_ids=list(current_layer),
                limit=max_relationships * 2,
            )

            next_layer: Set[str] = set()
            for r in rels:
                rid = r.get("relationship_id") or str(r.get("_id"))
                if rid not in collected_rel_docs:
                    collected_rel_docs[rid] = r

                src = r.get("source_entity_id")
                tgt = r.get("target_entity_id")

                if src and src not in visited_entity_ids:
                    next_layer.add(src)
                if tgt and tgt not in visited_entity_ids:
                    next_layer.add(tgt)

            visited_entity_ids.update(next_layer)
            current_layer = next_layer

        # Build in-memory NetworkX graph for path extraction & ranking
        G = nx.DiGraph()
        for r in collected_rel_docs.values():
            s_name = r.get("source_entity_name", r.get("source_entity_id"))
            t_name = r.get("target_entity_name", r.get("target_entity_id"))
            rel_type = r.get("relation_type", "RELATED_TO")
            G.add_edge(s_name, t_name, relation=rel_type, weight=r.get("weight", 1.0))

        # Retrieve full entity objects for all visited entities
        all_entity_ids = list(visited_entity_ids)[:max_entities]
        entities_cursor = self.db.graph_entities.find(
            {"project_id": project_id, "user_id": user_id, "entity_id": {"$in": all_entity_ids}}
        )
        entity_docs = await entities_cursor.to_list(length=max_entities)

        # Generate human-readable traversal paths (e.g., Python -> machine learning -> PyTorch)
        paths = []
        node_list = list(G.nodes())
        if len(node_list) >= 2:
            # Check shortest paths between pairs
            for i in range(min(len(node_list), 4)):
                for j in range(i + 1, min(len(node_list), 5)):
                    u, v = node_list[i], node_list[j]
                    try:
                        if nx.has_path(G, u, v):
                            sp = nx.shortest_path(G, u, v)
                            if len(sp) > 1:
                                paths.append(" -> ".join(sp))
                    except Exception:
                        pass

        return {
            "entities": entity_docs,
            "relationships": list(collected_rel_docs.values())[:max_relationships],
            "paths": paths[:5],
        }

    async def count_graph_elements(
        self,
        user_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Count entities, relationships, and distinct entity types for a project."""
        query = {"project_id": project_id, "user_id": user_id}
        ent_count = await self.db.graph_entities.count_documents(query)
        rel_count = await self.db.graph_relationships.count_documents(query)
        types = await self.db.graph_entities.distinct("entity_type", query)
        return {
            "entity_count": ent_count,
            "relationship_count": rel_count,
            "entity_types": types,
        }

    async def get_entities_by_project(
        self,
        user_id: str,
        project_id: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get entities for a project with optional entity_type filtering."""
        query: Dict[str, Any] = {"project_id": project_id, "user_id": user_id}
        if entity_type:
            query["entity_type"] = entity_type
        cursor = self.db.graph_entities.find(query).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_relationships_for_project(
        self,
        user_id: str,
        project_id: str,
        entity_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get relationships for a project with optional connected entity filtering."""
        query: Dict[str, Any] = {"project_id": project_id, "user_id": user_id}
        if entity_id:
            query["$or"] = [
                {"source_entity_id": entity_id},
                {"target_entity_id": entity_id},
            ]
        cursor = self.db.graph_relationships.find(query).limit(limit)
        return await cursor.to_list(length=limit)

    async def delete_source_graph(
        self,
        project_id: str,
        user_id: str,
        source_id: str,
    ) -> Dict[str, Any]:
        """
        Cascade deletion of graph records when a source is removed:
        1. Remove source_id from entities; if entity has no other sources, delete it.
        2. Remove source_id from relationships; if relationship has no other sources, delete it.
        3. Delete graph processing status.
        """
        # Remove source_id from relationships
        await self.db.graph_relationships.update_many(
            {"project_id": project_id, "user_id": user_id, "source_ids": source_id},
            {"$pull": {"source_ids": source_id}},
        )
        del_rels = await self.db.graph_relationships.delete_many(
            {"project_id": project_id, "user_id": user_id, "source_ids": {"$size": 0}}
        )

        # Remove source_id from entities
        await self.db.graph_entities.update_many(
            {"project_id": project_id, "user_id": user_id, "source_ids": source_id},
            {"$pull": {"source_ids": source_id}},
        )
        del_ents = await self.db.graph_entities.delete_many(
            {"project_id": project_id, "user_id": user_id, "source_ids": {"$size": 0}}
        )

        # Delete processing status
        await self.db.graph_processing_status.delete_one(
            {"project_id": project_id, "user_id": user_id, "source_id": source_id}
        )

        return {
            "entities_deleted": del_ents.deleted_count,
            "relationships_deleted": del_rels.deleted_count,
        }

    async def delete_source_graph_elements(
        self,
        user_id: str,
        project_id: str,
        source_id: str,
    ) -> Dict[str, Any]:
        """Alias for delete_source_graph supporting (user_id, project_id, source_id) order."""
        return await self.delete_source_graph(project_id, user_id, source_id)

    async def delete_project_graph(
        self,
        arg1: str,
        arg2: str,
    ) -> Dict[str, Any]:
        """
        Purge all graph entities, relationships, and processing statuses for a project.
        Supports both (project_id, user_id) and (user_id, project_id) calls.
        """
        # Determine which is project_id and which is user_id using simple heuristic or checking projects
        # In this repository user IDs usually start with "test_user" or uuid format or match user_id
        # We can simply match documents with $or or check both
        query = {
            "$or": [
                {"project_id": arg1, "user_id": arg2},
                {"project_id": arg2, "user_id": arg1},
            ]
        }
        del_ents = await self.db.graph_entities.delete_many(query)
        del_rels = await self.db.graph_relationships.delete_many(query)
        await self.db.graph_processing_status.delete_many(query)
        return {
            "entities_deleted": del_ents.deleted_count,
            "relationships_deleted": del_rels.deleted_count,
        }
