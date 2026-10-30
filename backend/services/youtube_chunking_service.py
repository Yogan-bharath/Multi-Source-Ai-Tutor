"""
YouTube Chunking Service: Merge transcript segments into sentence-aware,
timestamp-bounded chunks compatible with FastEmbed, FAISS, Groq, and GraphRAG.
"""
from typing import List, Dict, Any, Optional
import re

from schemas.youtube_schemas import (
    TranscriptSegment,
    YouTubeTranscriptChunk,
    format_seconds_to_timestamp,
    build_youtube_timestamp_url,
)


def chunk_transcript_segments(
    segments: List[TranscriptSegment],
    video_id: str,
    title: str = "",
    channel_name: str = "",
    source_id: str = "Source",
    target_words_per_chunk: int = 150,
    max_words_per_chunk: int = 250,
    **kwargs,
) -> List[YouTubeTranscriptChunk]:
    """
    Merge sequential subtitle segments into readable, sentence-aware chunks
    while strictly preserving the earliest start_time and latest end_time of each chunk.
    """
    if not segments:
        return []

    chunks: List[YouTubeTranscriptChunk] = []
    current_words: List[str] = []
    current_start: Optional[float] = None
    current_end: Optional[float] = None
    chunk_index = 0

    sentence_end = re.compile(r"[\.\?\!]$")

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        words = text.split()
        if not words:
            continue

        if current_start is None:
            current_start = seg.start_time

        current_end = max(current_end or seg.end_time, seg.end_time)
        current_words.extend(words)

        is_sentence_boundary = bool(sentence_end.search(text))
        has_enough_words = len(current_words) >= target_words_per_chunk
        is_too_long = len(current_words) >= max_words_per_chunk

        if (has_enough_words and is_sentence_boundary) or is_too_long:
            chunk_text = " ".join(current_words)
            start_sec = current_start or 0.0
            end_sec = current_end or (start_sec + 1.0)
            fmt_time = f"{format_seconds_to_timestamp(start_sec)} - {format_seconds_to_timestamp(end_sec)}"
            t_url = build_youtube_timestamp_url(video_id, start_sec)

            chunks.append(
                YouTubeTranscriptChunk(
                    chunk_id=f"yt_{video_id[:8]}_chunk_{chunk_index}",
                    source_id=source_id,
                    video_id=video_id,
                    title=title,
                    channel_name=channel_name,
                    text=chunk_text,
                    start_time=start_sec,
                    end_time=end_sec,
                    timestamp_formatted=fmt_time,
                    timestamp_url=t_url,
                    language=seg.language,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1
            current_words = []
            current_start = None
            current_end = None

    # Handle remaining words
    if current_words and current_start is not None:
        chunk_text = " ".join(current_words)
        start_sec = current_start
        end_sec = current_end or (start_sec + 1.0)
        fmt_time = f"{format_seconds_to_timestamp(start_sec)} - {format_seconds_to_timestamp(end_sec)}"
        t_url = build_youtube_timestamp_url(video_id, start_sec)

        chunks.append(
            YouTubeTranscriptChunk(
                chunk_id=f"yt_{video_id[:8]}_chunk_{chunk_index}",
                source_id=source_id,
                video_id=video_id,
                title=title,
                channel_name=channel_name,
                text=chunk_text,
                start_time=start_sec,
                end_time=end_sec,
                timestamp_formatted=fmt_time,
                timestamp_url=t_url,
                language=segments[0].language if segments else "en",
                chunk_index=chunk_index,
            )
        )

    return chunks
