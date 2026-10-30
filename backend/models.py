"""
Pydantic schemas and database models for Multi-Source AI Tutor.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

# ---------------------------------------------------------
# User Models
# ---------------------------------------------------------

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    email: str
    created_at: datetime
    is_active: bool

    class Config:
        populate_by_name = True

# ---------------------------------------------------------
# Project Models
# ---------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(default="", max_length=500)

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)

class ProjectResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    name: str
    description: str = ""
    index_id: str
    created_at: datetime
    updated_at: datetime
    source_count: Optional[int] = 0
    conversation_count: Optional[int] = 0

    class Config:
        populate_by_name = True

# ---------------------------------------------------------
# Source Models
# ---------------------------------------------------------

class SourceResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    project_id: str
    source_id: str
    original_url: str
    resolved_url: Optional[str] = None
    title: str = ""
    status: str
    chunks_indexed: int = 0
    truncated: bool = False
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True

# ---------------------------------------------------------
# Conversation & Message Models
# ---------------------------------------------------------

class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(default="New Conversation", max_length=200)

class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|archived)$")

class ConversationResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    project_id: str
    title: str
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    message_count: Optional[int] = 0

    class Config:
        populate_by_name = True

class SendMessageRequest(BaseModel):
    question: Optional[str] = None
    content: Optional[str] = None
    retrieval_mode: Optional[str] = None

    @property
    def text(self) -> str:
        return (self.question or self.content or "").strip()


class MessageResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    project_id: str
    conversation_id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime
    classification: Optional[Dict[str, Any]] = None
    source_summaries: Optional[List[Dict[str, Any]]] = None
    retrieved_chunks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    retrieval_metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True

class PaginatedMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    conversation_id: str

class SendChatMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse

