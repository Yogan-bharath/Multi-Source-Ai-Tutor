"""
Learning Studio Service: Source-Grounded AI Generation Tools
Provides Summary, Flashcards, Quiz, Mind Map, Study Notes, and Data Table
using Groq LLM grounded in project FAISS chunks.
"""
import json
import re
from typing import List, Dict, Any, Optional
from groq import Groq
from config import get_settings

settings = get_settings()

def get_groq_client() -> Groq:
    return Groq(api_key=settings.groq_api_key)

def _clean_json_response(raw_text: str) -> str:
    """Strip markdown code fence blocks if LLM surrounds JSON with ```json ... ```"""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

def _build_sources_context(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], max_chars: int = 15000) -> str:
    """Build compact grounded context from project chunks."""
    parts = []
    # Group chunks by source_id
    grouped: Dict[str, List[str]] = {}
    for c in chunks:
        sid = c.get("source_id", "Source A")
        text = c.get("text", "").strip()
        if text:
            grouped.setdefault(sid, []).append(text)

    total_len = 0
    for sid, text_list in grouped.items():
        combined = "\n\n".join(text_list)
        section = f"=== {sid} ===\n{combined}"
        if total_len + len(section) > max_chars:
            remaining = max_chars - total_len
            if remaining > 200:
                parts.append(section[:remaining] + "\n...[truncated]")
            break
        parts.append(section)
        total_len += len(section)

    return "\n\n".join(parts)


def generate_summary(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
    """Generate concise structured overview of the project's sources."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are an elite academic tutor. Analyze the following source material and generate a comprehensive, structured executive summary for a learning notebook.

Source Material:
{context}

Respond with valid JSON using exactly this format:
{{
  "title": "Topic Title",
  "overview": "A 2-3 paragraph thorough overview explaining the core subject matter.",
  "key_takeaways": [
    "Takeaway 1 with citation like [Source A]",
    "Takeaway 2 with citation like [Source B]",
    "Takeaway 3",
    "Takeaway 4",
    "Takeaway 5"
  ],
  "source_breakdown": [
    {{
      "source_id": "Source A",
      "main_contribution": "Key perspective or content contributed by this source"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert educational synthesizer. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(_clean_json_response(raw))
    except Exception:
        return {
            "title": "Project Summary",
            "overview": raw,
            "key_takeaways": [],
            "source_breakdown": [],
        }


def generate_flashcards(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate question-and-answer revision flashcards."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are a master educator. Create 6 high-yield learning flashcards based exclusively on the provided source material.
Each flashcard must have a concise prompt/question on the front and a clear, complete, educational answer on the back with inline provenance citations (e.g. [Source A]).

Source Material:
{context}

Respond with valid JSON using this format:
{{
  "flashcards": [
    {{
      "id": 1,
      "category": "Core Concept",
      "front": "What is...",
      "back": "Detailed explanation citing [Source A]...",
      "source": "[Source A]"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert tutor creating study materials. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(_clean_json_response(raw))
        return data.get("flashcards", [])
    except Exception:
        return []


def generate_quiz(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate an interactive multiple-choice quiz with explanations."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are an educational assessment expert. Create a 5-question multiple-choice conceptual quiz based on the source material.
Each question must test comprehension or comparison across sources, with 4 realistic options, 1 correct answer (0-indexed integer), and a detailed pedagogical explanation citing sources.

Source Material:
{context}

Respond with valid JSON using this format:
{{
  "questions": [
    {{
      "id": 1,
      "question": "Which of the following best describes...?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer_index": 0,
      "explanation": "Option A is correct because [Source A] establishes that..."
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert quiz designer. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(_clean_json_response(raw))
        return data.get("questions", [])
    except Exception:
        return []


def generate_mindmap(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
    """Generate a structured concept hierarchy for mind mapping."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are a knowledge architect. Create a structured hierarchical Mind Map representing the major themes, subtopics, and concepts in the source material.

Source Material:
{context}

Respond with valid JSON using this nested node format:
{{
  "name": "Central Topic",
  "children": [
    {{
      "name": "Major Category 1",
      "children": [
        {{ "name": "Sub-concept A", "detail": "Key definition with [Source A]" }},
        {{ "name": "Sub-concept B", "detail": "Key definition with [Source B]" }}
      ]
    }},
    {{
      "name": "Major Category 2",
      "children": [
        {{ "name": "Sub-concept C", "detail": "Key definition" }}
      ]
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert mind map designer. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(_clean_json_response(raw))
    except Exception:
        return {"name": "Overview", "children": []}


def generate_study_notes(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
    """Generate thorough, organized study notes formatted in Markdown."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are an elite tutor creating study notes for a university-level student. Produce comprehensive, well-structured study notes from the source material.
Format guidelines:
- Use Markdown headers (`##`, `###`)
- Bold important terminology
- Use bullet points and callouts
- Include inline provenance tags `[Source X]` for all claims
- Include a "Common Misconceptions" section
- Include a "Review Checklist"

Source Material:
{context}

Respond with valid JSON using this format:
{{
  "title": "Study Notes: Topic Title",
  "markdown_content": "# Study Notes: Topic Title\\n\\n## 1. Core Principles\\n...\\n\\n## 2. Key Mechanisms\\n...\\n\\n## 3. Common Misconceptions\\n...\\n\\n## 4. Review Checklist\\n..."
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert academic tutor. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(_clean_json_response(raw))
    except Exception:
        return {"title": "Study Notes", "markdown_content": raw}


def generate_datatable(sources: List[Dict[str, Any]], chunks: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
    """Extract and organize facts into a structured comparative data table."""
    client = get_groq_client()
    context = _build_sources_context(sources, chunks)
    model = model or settings.llm_model_primary

    prompt = f"""You are a data analyst and tutor. Extract the key entities, concepts, metrics, or comparisons from the source material and present them in a structured table.

Source Material:
{context}

Respond with valid JSON using this format:
{{
  "title": "Comparative Data Table",
  "description": "Comparison of key concepts across project sources",
  "columns": ["Concept / Entity", "Key Characteristics", "Source Agreement / Perspective", "Applications"],
  "rows": [
    ["Entity 1", "Details with [Source A]", "Supported by Source A & B", "Use case"],
    ["Entity 2", "Details with [Source B]", "Unique to Source B", "Use case"]
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a data extraction expert. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(_clean_json_response(raw))
    except Exception:
        return {
            "title": "Data Table",
            "description": "Extracted Data",
            "columns": ["Item", "Description"],
            "rows": [],
        }
