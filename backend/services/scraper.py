"""
Scrape and clean text content from multiple URLs independently.
Enforces SSRF protection, streaming download size limits, content truncation,
and robust redirect validation.
"""
import re
import time
import random
import hashlib
import socket
import ipaddress
from typing import Optional, Tuple, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup

from config import get_settings

settings = get_settings()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Tracking query parameters to strip during normalization
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "_hsenc", "_hsmi", "mc_cid", "mc_eid"
}

# Dangerous hostnames blocked to reduce SSRF risks
BLOCKED_HOSTNAMES = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0",
    "metadata.google.internal", "metadata", "instance-data",
}


def normalize_url(raw_url: str) -> str:
    """Normalize URL by stripping whitespace, tracking params, and trailing slash."""
    url = raw_url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        clean_query = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        path = parsed.path
        if path and path != "/":
            path = path.rstrip("/")
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            urlencode(clean_query),
            parsed.fragment,
        ))
        return normalized
    except Exception:
        return url


def is_safe_destination(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that the destination URL does not target private, loopback,
    link-local, or cloud metadata IP addresses (SSRF mitigation).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Only HTTP and HTTPS URLs are permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: missing host address."

        host_lower = hostname.lower()
        if host_lower in BLOCKED_HOSTNAMES or host_lower.endswith(".internal") or host_lower.endswith(".local"):
            return False, f"Access to '{hostname}' is blocked for security reasons."

        # Check direct IP string
        try:
            direct_ip = ipaddress.ip_address(host_lower)
            if (
                direct_ip.is_private
                or direct_ip.is_loopback
                or direct_ip.is_link_local
                or direct_ip.is_multicast
                or direct_ip.is_reserved
                or direct_ip.is_unspecified
            ):
                return False, f"Unsafe destination blocked: IP address ({direct_ip}) is private or restricted."
        except ValueError:
            # Not an IP literal, resolve hostname via DNS
            pass

        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for _, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                    or ip.is_unspecified
                ):
                    return False, f"Unsafe destination blocked: resolved IP ({ip_str}) is private or restricted."
        except socket.gaierror:
            return False, "DNS resolution failed: host unreachable."
        except Exception as exc:
            return False, f"Destination address validation error: {str(exc)}"

        return True, None
    except Exception as exc:
        return False, f"Invalid URL structure: {str(exc)}"


def validate_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate URL syntax and protocol.
    Returns (is_valid, normalized_url, error_message).
    """
    if not url or not url.strip():
        return False, url, "URL cannot be empty."

    norm = normalize_url(url)
    try:
        parsed = urlparse(norm)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            return False, norm, "URL must start with http:// or https://"
        if not parsed.netloc or "." not in parsed.netloc:
            return False, norm, "Invalid domain name in URL."
        return True, norm, None
    except Exception as exc:
        return False, norm, f"Malformed URL: {str(exc)}"


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and normalize text content."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    filtered = []
    for line in lines:
        if not line:
            if filtered and filtered[-1] != "":
                filtered.append("")
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
    """Extract page title using title tag, og:title, or h1."""
    if soup.title and soup.title.string and soup.title.string.strip():
        title = soup.title.string.strip()
        title = re.sub(r"\s+[|\-–—]\s+.*$", "", title).strip() or title
        return title

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text

    parsed = urlparse(fallback_url)
    slug = parsed.path.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
    if slug:
        return f"{slug.title()} ({parsed.netloc.replace('www.', '')})"
    return parsed.netloc.replace("www.", "")


def scrape_single_source(raw_url: str, timeout: Optional[int] = None) -> dict:
    """
    Independently scrape a single URL with:
      - SSRF validation on initial URL and all redirect targets
      - Streaming download with 2 MB hard response limit
      - Content extraction and clean fallback
      - Configurable text truncation (100,000 characters)
    """
    timeout = timeout or settings.scrape_timeout_seconds
    max_download_size = settings.max_download_size_bytes
    max_extracted_chars = settings.max_extracted_chars

    is_valid, norm_url, val_err = validate_url(raw_url)
    if not is_valid:
        return {
            "original_url": raw_url,
            "resolved_url": None,
            "title": raw_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": val_err,
        }

    # Initial SSRF check
    safe, ssrf_err = is_safe_destination(norm_url)
    if not safe:
        return {
            "original_url": raw_url,
            "resolved_url": norm_url,
            "title": norm_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": ssrf_err,
        }

    current_url = norm_url
    resolved_url = norm_url
    max_redirects = 5
    redirect_count = 0
    html_bytes = b""
    content_type = ""

    try:
        with httpx.Client(
            headers=HEADERS,
            follow_redirects=False,  # Manually validate each redirect destination for SSRF
            timeout=timeout,
            verify=True,
        ) as client:
            while redirect_count <= max_redirects:
                # SSRF revalidation on each redirect hop
                safe, hop_err = is_safe_destination(current_url)
                if not safe:
                    return {
                        "original_url": raw_url,
                        "resolved_url": current_url,
                        "title": norm_url,
                        "text": "",
                        "char_count": 0,
                        "truncated": False,
                        "status": "failed",
                        "error": f"Redirect blocked: {hop_err}",
                    }

                # Streaming request to enforce size limits while downloading
                with client.stream("GET", current_url) as resp:
                    resolved_url = str(resp.url)

                    # Handle Redirects
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            return {
                                "original_url": raw_url,
                                "resolved_url": current_url,
                                "title": norm_url,
                                "text": "",
                                "char_count": 0,
                                "truncated": False,
                                "status": "failed",
                                "error": f"HTTP {resp.status_code} redirect missing Location header.",
                            }
                        next_url = urljoin(current_url, location)
                        current_url = normalize_url(next_url)
                        redirect_count += 1
                        continue

                    # Check HTTP status errors
                    if resp.status_code in (401, 403):
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": f"Access restricted (HTTP {resp.status_code}): authentication or paywall required.",
                        }
                    elif resp.status_code == 404:
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": "Page not found (HTTP 404).",
                        }
                    elif resp.status_code == 429:
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": "Rate limit exceeded (HTTP 429). Please try again later.",
                        }
                    elif resp.is_error:
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": f"HTTP {resp.status_code}: {resp.reason_phrase}",
                        }

                    # Check Content-Type
                    content_type = resp.headers.get("content-type", "").lower()
                    if not any(t in content_type for t in ["text/html", "text/plain", "application/xhtml+xml"]):
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": f"Unsupported content type ({content_type.split(';')[0] or 'unknown'}). Only HTML web pages are supported.",
                        }

                    # Check Content-Length header upfront
                    cl_header = resp.headers.get("content-length")
                    if cl_header and cl_header.isdigit() and int(cl_header) > max_download_size:
                        return {
                            "original_url": raw_url,
                            "resolved_url": resolved_url,
                            "title": norm_url,
                            "text": "",
                            "char_count": 0,
                            "truncated": False,
                            "status": "failed",
                            "error": "This page contains too much content and exceeded the configured download limit of 2 MB.",
                        }

                    # Stream bytes while enforcing 2 MB limit
                    chunks = []
                    downloaded = 0
                    for chunk in resp.iter_bytes(chunk_size=16384):
                        downloaded += len(chunk)
                        if downloaded > max_download_size:
                            return {
                                "original_url": raw_url,
                                "resolved_url": resolved_url,
                                "title": norm_url,
                                "text": "",
                                "char_count": 0,
                                "truncated": False,
                                "status": "failed",
                                "error": "This page contains too much content and exceeded the configured download limit of 2 MB.",
                            }
                        chunks.append(chunk)

                    html_bytes = b"".join(chunks)
                    break

            if redirect_count > max_redirects:
                return {
                    "original_url": raw_url,
                    "resolved_url": current_url,
                    "title": norm_url,
                    "text": "",
                    "char_count": 0,
                    "truncated": False,
                    "status": "failed",
                    "error": "Too many redirects (exceeded 5 redirects).",
                }

    except httpx.TimeoutException:
        return {
            "original_url": raw_url,
            "resolved_url": resolved_url,
            "title": norm_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": f"Request timed out after {timeout} seconds.",
        }
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return {
            "original_url": raw_url,
            "resolved_url": None,
            "title": norm_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": "Connection failed: host unreachable or DNS resolution failed.",
        }
    except httpx.RequestError as exc:
        return {
            "original_url": raw_url,
            "resolved_url": None,
            "title": norm_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": f"Network error: {type(exc).__name__}",
        }
    except Exception as exc:
        return {
            "original_url": raw_url,
            "resolved_url": None,
            "title": norm_url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": f"Unexpected error while fetching URL: {str(exc)}",
        }

    # Decode HTML
    try:
        html = html_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html = html_bytes.decode("latin-1")
        except Exception:
            html = str(html_bytes)

    # Parse HTML metadata
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup, resolved_url)

    # Clean HTML noise for extraction
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form", "iframe", "button"]):
        tag.decompose()

    # Strategy A: trafilatura
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )

    cleaned = ""
    if text and len(text) >= 150:
        cleaned = _clean_text(text)
    else:
        # Strategy B: BS4 fallback
        main_el = soup.find(["article", "main"]) or soup.find(id=re.compile("content|main", re.I)) or soup.find(class_=re.compile("content|main|article|post", re.I))
        if main_el:
            body = main_el.get_text(separator="\n")
        else:
            body = soup.get_text(separator="\n")
        cleaned = _clean_text(body)

    if not cleaned or len(cleaned) < 100:
        return {
            "original_url": raw_url,
            "resolved_url": resolved_url,
            "title": title,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "status": "failed",
            "error": "No readable main content could be extracted (page may require JavaScript, login, or be empty).",
        }

    # Content length limitation and truncation
    is_truncated = False
    if len(cleaned) > max_extracted_chars:
        cleaned = cleaned[:max_extracted_chars]
        is_truncated = True

    return {
        "original_url": raw_url,
        "resolved_url": resolved_url,
        "title": title,
        "text": cleaned,
        "char_count": len(cleaned),
        "truncated": is_truncated,
        "status": "success",
        "error": None,
    }


def scrape_multiple_sources(urls: List[str], existing_urls: Optional[List[str]] = None) -> List[dict]:
    """
    Scrape multiple URLs with deduplication, SSRF checks, and polite crawl delays.
    Returns list of source dicts with status, metadata, truncation, and error messages.
    """
    results: List[dict] = []
    seen_urls = set(normalize_url(u) for u in (existing_urls or []))
    content_hashes: Dict[str, str] = {}

    for i, raw_url in enumerate(urls):
        norm = normalize_url(raw_url)
        if not norm:
            results.append({
                "original_url": raw_url,
                "resolved_url": None,
                "title": raw_url or "Empty URL",
                "text": "",
                "char_count": 0,
                "truncated": False,
                "status": "failed",
                "error": "URL cannot be empty.",
            })
            continue

        if norm in seen_urls:
            results.append({
                "original_url": raw_url,
                "resolved_url": norm,
                "title": norm,
                "text": "",
                "char_count": 0,
                "truncated": False,
                "status": "failed",
                "error": "Duplicate URL: this source was already submitted or indexed.",
            })
            continue

        seen_urls.add(norm)

        if i > 0:
            time.sleep(random.uniform(0.3, 0.6))

        res = scrape_single_source(raw_url)

        if res["status"] == "success" and res["text"]:
            text_hash = hashlib.sha256(res["text"].encode("utf-8")).hexdigest()
            if text_hash in content_hashes:
                res["status"] = "failed"
                res["error"] = f"Duplicate content: matches content from {content_hashes[text_hash]}."
                res["text"] = ""
                res["char_count"] = 0
            else:
                content_hashes[text_hash] = res["resolved_url"] or norm

        results.append(res)

    return results


def scrape_sources(sources: list[dict]) -> list[dict]:
    """
    Legacy compatibility function:
    Given a list of {url, title, ...} dicts, scrape each and return list of successful sources.
    """
    urls = [s["url"] for s in sources]
    scraped = scrape_multiple_sources(urls)
    labels = ["A", "B", "C", "D", "E"]

    out = []
    success_idx = 0
    for s in scraped:
        if s["status"] == "success":
            label = labels[success_idx] if success_idx < len(labels) else f"Src{success_idx + 1}"
            success_idx += 1
            out.append({
                "source_id": f"Source {label}",
                "url": s["resolved_url"] or s["original_url"],
                "original_url": s["original_url"],
                "resolved_url": s["resolved_url"],
                "title": s["title"],
                "text": s["text"],
                "char_count": s["char_count"],
                "truncated": s.get("truncated", False),
            })
    return out
