from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # LLM & Embedding Settings
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_model_primary: str = "openai/gpt-oss-120b"
    llm_model_fallback: str = "openai/gpt-oss-20b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    
    # MongoDB Settings
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "ai_tutor_dev")
    mongodb_server_timeout_ms: int = int(os.getenv("MONGODB_SERVER_TIMEOUT_MS", "5000"))
    
    # Authentication & Security
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-insecure-jwt-secret-key-32chars-min-replace-in-prod")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    auth_cookie_name: str = os.getenv("AUTH_COOKIE_NAME", "access_token")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    # Request & Content Limits
    max_sources_per_request: int = int(os.getenv("MAX_SOURCES_PER_REQUEST", "5"))
    max_download_size_bytes: int = int(os.getenv("MAX_DOWNLOAD_SIZE_BYTES", str(2 * 1024 * 1024)))  # 2 MB
    max_extracted_chars: int = int(os.getenv("MAX_EXTRACTED_CHARS", "100000"))  # 100,000 chars
    max_chunks_per_source: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "100"))  # 100 chunks
    scrape_timeout_seconds: int = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "20"))
    
    @property
    def max_chars_per_source(self) -> int:
        return self.max_extracted_chars

    # Chunking: ~1,000 characters (200 words) with ~150 characters (30 words) overlap
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "200"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "30"))
    
    top_k_per_source: int = 3
    max_sources: int = 5  # Server-side hard cap per indexing request
    faiss_index_dir: str = "./faiss_indices"

    # GraphRAG & Hybrid Retrieval Settings
    rag_mode: str = os.getenv("RAG_MODE", "vector")
    graph_rag_enabled: bool = os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"
    graph_max_hops: int = int(os.getenv("GRAPH_MAX_HOPS", "2"))
    graph_max_entities: int = int(os.getenv("GRAPH_MAX_ENTITIES", "20"))
    graph_max_relationships: int = int(os.getenv("GRAPH_MAX_RELATIONSHIPS", "30"))
    hybrid_vector_weight: float = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.6"))
    hybrid_graph_weight: float = float(os.getenv("HYBRID_GRAPH_WEIGHT", "0.4"))
    graph_extraction_batch_size: int = int(os.getenv("GRAPH_EXTRACTION_BATCH_SIZE", "5"))
    graph_retrieval_timeout: int = int(os.getenv("GRAPH_RETRIEVAL_TIMEOUT", "5"))


    @property
    def allowed_cors_origins(self) -> List[str]:
        return [orig.strip() for orig in self.cors_origins.split(",") if orig.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
