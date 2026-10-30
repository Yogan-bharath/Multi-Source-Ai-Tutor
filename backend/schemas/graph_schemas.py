"""
Pydantic schemas for GraphRAG: Entities, Relationships, Processing Status, and Retrieval Metadata.
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Entity & Relationship Extraction Models (used for LLM structured output)
# -------------------------------------------------------------------------

class ExtractedEntity(BaseModel):
    name: str = Field(..., description="Canonical entity name")
    entity_type: str = Field(..., description="Type of entity (e.g. Concept, Technology, Method, Algorithm, Person, Organization, Product)")
    description: str = Field(default="", description="Concise factual description grounded in the text")
    aliases: List[str] = Field(default_factory=list, description="Alternate names or abbreviations found in text")


class ExtractedRelationship(BaseModel):
    source_entity: str = Field(..., description="Source entity name")
    target_entity: str = Field(..., description="Target entity name")
    relation_type: str = Field(..., description="Semantic relation type (e.g. USES, DEPENDS_ON, PART_OF, IMPROVES, CATEGORY_OF, RELATED_TO)")
    description: str = Field(default="", description="Concise explanation of the relationship grounded in the text")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence or strength of relationship")


class GraphExtractionPayload(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)


# -------------------------------------------------------------------------
# Database Domain Models
# -------------------------------------------------------------------------

class GraphEntity(BaseModel):
    id: str = Field(default="", alias="_id")
    entity_id: str
    name: str
    name_normalized: str
    entity_type: str
    description: str = ""
    project_id: str
    user_id: str
    source_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class GraphRelationship(BaseModel):
    id: str = Field(default="", alias="_id")
    relationship_id: str
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    relation_type: str
    description: str = ""
    weight: float = 1.0
    project_id: str
    user_id: str
    source_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class GraphProcessingStatus(BaseModel):
    id: str = Field(default="", alias="_id")
    project_id: str
    user_id: str
    source_id: str
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    entity_count: int = 0
    relationship_count: int = 0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


GraphStatusResponse = GraphProcessingStatus


class GraphSummaryResponse(BaseModel):
    project_id: str
    entity_count: int = 0
    relationship_count: int = 0
    entity_types: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------------
# Retrieval & Provenance Schemas
# -------------------------------------------------------------------------

class GraphEntityInfo(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    description: str
    source_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)


class GraphRelationshipInfo(BaseModel):
    relationship_id: str
    source_entity_name: str
    target_entity_name: str
    relation_type: str
    description: str
    source_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)


class RetrievedEvidenceChunk(BaseModel):
    source_id: str
    url: str = ""
    title: str = ""
    text: str
    score: float
    retrieval_method: Literal["vector", "graph", "hybrid"] = "vector"
    chunk_index: Optional[int] = None
    supporting_entities: List[str] = Field(default_factory=list)
    supporting_relationships: List[str] = Field(default_factory=list)


class RetrievalMetadata(BaseModel):
    retrieval_mode: str = "vector"  # "vector" | "hybrid"
    vector_results_count: int = 0
    graph_results_count: int = 0
    final_context_count: int = 0
    graph_entity_ids: List[str] = Field(default_factory=list)
    graph_relationship_ids: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    chunk_ids: List[str] = Field(default_factory=list)
