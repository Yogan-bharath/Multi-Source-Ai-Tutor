"""
YouTube Extraction Service: Safe URL validation, metadata extraction,
and available subtitle/caption retrieval using yt-dlp and direct caption parsing.
Strictly metadata and caption retrieval ONLY — no audio/video downloads, no Whisper, no FFmpeg.
"""
import re
import html
import logging
from typing import Optional, List, Dict, Tuple, Any
from urllib.parse import urlparse, parse_qs
import httpx
import yt_dlp

from schemas.youtube_schemas import (
    YouTubeURLValidation,
    YouTubeMetadata,
    TranscriptSegment,
    format_seconds_to_timestamp,
)

logger = logging.getLogger("uvicorn.error")

# Allowed YouTube hostnames
ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

# Standard 11-character YouTube video ID pattern
YOUTUBE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def extract_youtube_video_id(url: str) -> Optional[str]:
    """
    Extract canonical 11-char video ID from various YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    """
    if not url or not isinstance(url, str):
        return None

    clean_url = url.strip()

    # Direct 11-char video ID support
    if YOUTUBE_ID_PATTERN.match(clean_url):
        return clean_url

    try:
        parsed = urlparse(clean_url)
    except Exception:
        return None

    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_HOSTS:
        return None

    # Handle youtu.be/VIDEO_ID
    if "youtu.be" in hostname:
        path = parsed.path.strip("/")
        vid = path.split("/")[0] if path else ""
        if YOUTUBE_ID_PATTERN.match(vid):
            return vid
        return None

    # Handle youtube.com/shorts/VIDEO_ID or /embed/VIDEO_ID
    path = parsed.path.strip("/")
    path_parts = path.split("/")
    if len(path_parts) >= 2 and path_parts[0] in ("shorts", "embed", "v"):
        vid = path_parts[1]
        if YOUTUBE_ID_PATTERN.match(vid):
            return vid

    # Handle youtube.com/watch?v=VIDEO_ID
    query_params = parse_qs(parsed.query)
    if "v" in query_params:
        vid = query_params["v"][0]
        if YOUTUBE_ID_PATTERN.match(vid):
            return vid

    return None


def validate_youtube_url(url: str) -> YouTubeURLValidation:
    """Validate a YouTube URL and return normalized canonical URL."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return YouTubeURLValidation(
            is_valid=False,
            video_id=None,
            normalized_url=None,
            error="Invalid YouTube URL. Supported formats: watch?v=, youtu.be/, shorts/, embed/.",
        )

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return YouTubeURLValidation(
        is_valid=True,
        video_id=video_id,
        normalized_url=canonical_url,
        error=None,
    )


validate_and_extract_youtube_id = validate_youtube_url


def _get_ydl_options() -> dict:
    """Safe yt-dlp options: metadata-only, no downloads, timeouts."""
    return {
        "skip_download": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 15,
        "noplaylist": True,
        "ignoreerrors": True,
        "check_formats": False,
    }


def sync_fetch_youtube_metadata(url: str) -> YouTubeMetadata:
    """
    Extract video metadata and available subtitle tracks using yt-dlp.
    Raises ValueError on extraction failure or unavailable video.
    """
    val = validate_youtube_url(url)
    if not val.is_valid or not val.video_id:
        raise ValueError(val.error or "Invalid YouTube URL")

    video_id = val.video_id
    canonical_url = val.normalized_url or f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = _get_ydl_options()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(canonical_url, download=False)
    except Exception as exc:
        logger.error(f"[youtube_extraction] yt-dlp error for {video_id}: {exc}")
        raise ValueError(f"Failed to fetch YouTube video information: {str(exc)}")

    if not info:
        raise ValueError("Video unavailable or could not be retrieved from YouTube.")

    # Check if video is live stream or has restriction
    if info.get("is_live"):
        raise ValueError("Live streams without finished transcripts are not supported.")

    title = info.get("title") or f"YouTube Video {video_id}"
    channel_name = info.get("uploader") or info.get("channel") or "YouTube Channel"
    channel_id = info.get("channel_id")
    duration = int(info.get("duration") or 0)
    thumbnail_url = info.get("thumbnail")
    description = info.get("description") or ""
    if len(description) > 500:
        description = description[:500] + "..."

    # Subtitles discovery
    manual_subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}

    manual_langs = list(manual_subs.keys())
    auto_langs = list(auto_subs.keys())

    caption_type = "none"
    available_languages: List[str] = []

    if manual_langs:
        caption_type = "manual"
        available_languages = manual_langs
    elif auto_langs:
        caption_type = "auto"
        available_languages = auto_langs

    has_captions = bool(manual_langs or auto_langs)

    return YouTubeMetadata(
        video_id=video_id,
        title=title.strip(),
        channel_name=channel_name.strip(),
        channel_id=channel_id,
        description=description.strip(),
        duration=duration,
        duration_formatted=format_seconds_to_timestamp(duration),
        thumbnail_url=thumbnail_url,
        original_url=canonical_url,
        available_languages=available_languages,
        caption_type=caption_type,
        has_captions=has_captions,
    )


async def fetch_youtube_metadata(url: str) -> YouTubeMetadata:
    """Async wrapper for non-blocking execution in FastAPI."""
    import asyncio
    return await asyncio.to_thread(sync_fetch_youtube_metadata, url)



def _parse_vtt_timestamp(ts_str: str) -> float:
    """Parse WebVTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) into seconds."""
    parts = ts_str.strip().replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    return float(parts[0])


def parse_vtt_subtitles(vtt_text: str, language: str = "en") -> List[TranscriptSegment]:
    """Parse WebVTT subtitle format into clean TranscriptSegment objects."""
    segments: List[TranscriptSegment] = []
    lines = vtt_text.splitlines()
    i = 0
    time_pattern = re.compile(r"((?:\d+:)?\d+:\d+(?:\.\d+)?)\s*-->\s*((?:\d+:)?\d+:\d+(?:\.\d+)?)")

    seen_texts = set()

    while i < len(lines):
        line = lines[i].strip()
        match = time_pattern.search(line)
        if match:
            start_s = _parse_vtt_timestamp(match.group(1))
            end_s = _parse_vtt_timestamp(match.group(2))
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and not time_pattern.search(lines[i]):
                # Remove WebVTT formatting tags like <c>, </c>, <v Speaker>
                clean_line = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if clean_line:
                    text_lines.append(clean_line)
                i += 1

            raw_text = " ".join(text_lines)
            clean_text = html.unescape(raw_text).strip()
            # Deduplicate consecutive/rolling subtitles
            if clean_text and clean_text not in seen_texts:
                segments.append(TranscriptSegment(
                    text=clean_text,
                    start_time=round(start_s, 2),
                    end_time=round(end_s, 2),
                    language=language,
                ))
                seen_texts.add(clean_text)
        else:
            i += 1

    return segments


parse_webvtt_subtitles = parse_vtt_subtitles


def parse_json3_subtitles(json_data: Any, language: str = "en") -> List[TranscriptSegment]:
    """Parse YouTube JSON3 subtitle format into clean TranscriptSegment objects."""
    if isinstance(json_data, str):
        import json
        try:
            json_data = json.loads(json_data)
        except Exception:
            return []
    if not isinstance(json_data, dict):
        return []

    segments: List[TranscriptSegment] = []
    events = json_data.get("events", [])
    seen_texts = set()

    for ev in events:
        start_ms = ev.get("tStartMs", 0)
        duration_ms = ev.get("dDurationMs", 0)
        segs = ev.get("segs", [])
        text_parts = [s.get("utf8", "") for s in segs if s.get("utf8")]
        raw_text = "".join(text_parts).replace("\n", " ").strip()
        clean_text = html.unescape(raw_text).strip()

        if clean_text and clean_text != "\n" and clean_text not in seen_texts:
            start_s = round(start_ms / 1000.0, 2)
            end_s = round((start_ms + duration_ms) / 1000.0, 2)
            segments.append(TranscriptSegment(
                text=clean_text,
                start_time=start_s,
                end_time=max(end_s, start_s + 0.5),
                language=language,
            ))
            seen_texts.add(clean_text)

    return segments


def sync_fetch_youtube_transcript(
    url: str,
    preferred_language: str = "en",
) -> Tuple[List[TranscriptSegment], str, str]:
    """
    Fetch available captions/subtitles for a YouTube video.
    Preference:
    1. Manual subtitles in preferred language (e.g. 'en')
    2. Any manual subtitles
    3. Auto-generated subtitles in preferred language
    4. Any auto-generated subtitles

    Returns:
        (segments, selected_language, caption_type)
    """
    val = validate_youtube_url(url)
    if not val.is_valid or not val.video_id:
        raise ValueError(val.error or "Invalid YouTube URL")

    canonical_url = val.normalized_url or f"https://www.youtube.com/watch?v={val.video_id}"
    ydl_opts = _get_ydl_options()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(canonical_url, download=False)

    if not info:
        raise ValueError("Video information could not be retrieved.")

    manual_subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}

    if not manual_subs and not auto_subs:
        raise ValueError("No subtitles or captions are available for this YouTube video.")

    target_lang = None
    target_formats = None
    caption_type = "manual"

    # 1. Search manual subtitles
    for lang in [preferred_language, "en", "en-US", "en-GB"]:
        if lang in manual_subs:
            target_lang = lang
            target_formats = manual_subs[lang]
            break

    if not target_formats and manual_subs:
        target_lang = next(iter(manual_subs))
        target_formats = manual_subs[target_lang]

    # 2. Search automatic subtitles if manual not found
    if not target_formats:
        caption_type = "auto"
        for lang in [preferred_language, "en", "en-US", "en-GB"]:
            if lang in auto_subs:
                target_lang = lang
                target_formats = auto_subs[lang]
                break
        if not target_formats and auto_subs:
            target_lang = next(iter(auto_subs))
            target_formats = auto_subs[target_lang]

    if not target_formats or not target_lang:
        raise ValueError("Could not find a compatible subtitle track for this video.")

    # Find preferred format: json3, then vtt
    chosen_url = None
    chosen_fmt = None
    for fmt in ["json3", "vtt", "srv1", "ttml"]:
        matched = next((f for f in target_formats if f.get("ext") == fmt or fmt in f.get("url", "")), None)
        if matched and matched.get("url"):
            chosen_url = matched["url"]
            chosen_fmt = fmt
            break

    if not chosen_url and target_formats:
        chosen_url = target_formats[0].get("url")
        chosen_fmt = target_formats[0].get("ext", "vtt")

    if not chosen_url:
        raise ValueError("No download URL found for subtitle track.")

    # Fetch subtitle track content via HTTP
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(chosen_url)
            resp.raise_for_status()
            content = resp.text
    except Exception as exc:
        logger.error(f"[youtube_extraction] Subtitle download failed: {exc}")
        raise ValueError(f"Failed to download subtitles track: {str(exc)}")

    segments: List[TranscriptSegment] = []
    if chosen_fmt == "json3" or content.strip().startswith("{"):
        try:
            import json
            json_obj = json.loads(content)
            segments = parse_json3_subtitles(json_obj, language=target_lang)
        except Exception:
            segments = parse_vtt_subtitles(content, language=target_lang)
    else:
        segments = parse_vtt_subtitles(content, language=target_lang)

    if not segments:
        raise ValueError("Subtitle track contained no valid transcript text.")

    return segments, target_lang, caption_type


async def fetch_youtube_transcript(
    url: str,
    preferred_language: str = "en",
) -> Tuple[List[TranscriptSegment], str, str]:
    """Async wrapper for non-blocking execution in FastAPI."""
    import asyncio
    return await asyncio.to_thread(sync_fetch_youtube_transcript, url, preferred_language)

