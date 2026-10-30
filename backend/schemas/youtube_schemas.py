"""
Pydantic schemas for YouTube Video Transcript Ingestion:
Validation, Metadata, Transcript Segments, and Timestamp-Aware Chunks.
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS string."""
    total_sec = max(0, int(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def build_youtube_timestamp_url(video_id: str, seconds: float) -> str:
    """Standard YouTube URL with start timestamp."""
    start_sec = max(0, int(seconds))
    return f"https://www.youtube.com/watch?v={video_id}&t={start_sec}s"


class YouTubeURLValidation(BaseModel):
    is_valid: bool
    video_id: Optional[str] = None
    normalized_url: Optional[str] = None
    error: Optional[str] = None


class TranscriptSegment(BaseModel):
    text: str = Field(..., description="Cleaned subtitle line/segment text")
    start_time: float = Field(default=0.0, ge=0.0, description="Start offset in seconds")
    end_time: float = Field(default=0.0, ge=0.0, description="End offset in seconds")
    language: str = Field(default="en", description="Transcript language code (e.g. en, es)")

    def __init__(self, **data):
        if "start" in data and "start_time" not in data:
            data["start_time"] = data.pop("start")
        if "end" in data and "end_time" not in data:
            data["end_time"] = data.pop("end")
        super().__init__(**data)

    @property
    def start(self) -> float:
        return self.start_time

    @property
    def end(self) -> float:
        return self.end_time

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)


class YouTubeMetadata(BaseModel):
    video_id: str
    title: str
    channel_name: str
    channel_id: Optional[str] = None
    description: Optional[str] = None
    duration: int = 0  # In seconds
    duration_formatted: str = "00:00"
    thumbnail_url: Optional[str] = None
    original_url: str
    available_languages: List[str] = Field(default_factory=list)
    caption_type: Literal["manual", "auto", "none"] = "none"
    has_captions: bool = False

    @property
    def author(self) -> str:
        return self.channel_name

    @property
    def available_subtitles(self) -> List[str]:
        return self.available_languages

    @property
    def is_available(self) -> bool:
        return self.has_captions


class YouTubeTranscriptChunk(BaseModel):
    chunk_id: str
    source_id: str
    video_id: str
    title: str
    channel_name: str
    text: str
    start_time: float
    end_time: float
    timestamp_formatted: str
    timestamp_url: str
    language: str = "en"
    chunk_index: int


class YouTubeIngestRequest(BaseModel):
    project_id: str
    url: str
    preferred_language: Optional[str] = "en"


class YouTubePreviewRequest(BaseModel):
    url: str


class YouTubePreviewResponse(BaseModel):
    is_valid: bool = True
    video_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    channel_name: Optional[str] = None
    author: Optional[str] = None
    duration: int = 0
    duration_formatted: str = "00:00"
    thumbnail_url: Optional[str] = None
    has_captions: bool = False
    is_available: bool = True
    caption_type: str = "none"
    available_languages: List[str] = Field(default_factory=list)
    available_subtitles: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    def __init__(self, **data):
        if "channel_name" in data and "author" not in data:
            data["author"] = data["channel_name"]
        elif "author" in data and "channel_name" not in data:
            data["channel_name"] = data["author"]

        if "available_languages" in data and "available_subtitles" not in data:
            data["available_subtitles"] = data["available_languages"]
        elif "available_subtitles" in data and "available_languages" not in data:
            data["available_languages"] = data["available_subtitles"]

        if "has_captions" in data and "is_available" not in data:
            data["is_available"] = data["has_captions"]
        elif "is_available" in data and "has_captions" not in data:
            data["has_captions"] = data["is_available"]

        super().__init__(**data)
