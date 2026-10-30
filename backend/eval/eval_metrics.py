"""
Deterministic and probabilistic evaluation metrics for RAG and GraphRAG architectures.

Implements standard benchmark calculations:
1. Context Precision: fraction of retrieved chunks that contain relevant evidence or target sources.
2. Context Recall: fraction of expected key evidence items present in the retrieved context.
3. Citation Precision: fraction of cited sources [Source X] in the generated answer that match true supporting sources.
4. Citation Completeness: fraction of true supporting sources that are explicitly cited in the answer.
5. Answer Correctness (Deterministic + Lexical/Semantic): Token overlap, key fact inclusion, and unanswerability compliance.
6. Hallucination Indicator: proportion of claims/named entities in the answer not supported by retrieved context.
7. YouTube Timestamp Precision & Recall: verification of MM:SS timestamps matching gold video markers.
8. Latency & Token consumption accounting.
"""
import re
from typing import List, Dict, Any, Set, Tuple, Optional


def clean_text_tokens(text: str) -> Set[str]:
    """Tokenize and normalize text to a set of lower-case alphanumeric tokens."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 2]
    # Filter common stopwords
    stopwords = {
        "the", "and", "that", "this", "with", "from", "for", "are", "was",
        "were", "which", "into", "their", "then", "have", "has", "had"
    }
    return {t for t in tokens if t not in stopwords}


def compute_context_precision(
    retrieved_chunks: List[Dict[str, Any]],
    supporting_source_ids: List[str],
    expected_evidence: List[str],
) -> float:
    """
    Precision = (Retrieved chunks containing relevant evidence or belonging to supporting sources) / total retrieved chunks.
    If no supporting sources (unanswerable question) and no chunks retrieved or non-relevant, returns 1.0.
    """
    if not retrieved_chunks:
        return 1.0 if not supporting_source_ids else 0.0

    relevant_count = 0
    supp_set = set(supporting_source_ids)

    for chunk in retrieved_chunks:
        text = chunk.get("text", "").lower()
        source_id = chunk.get("source_id", "")
        # Relevant if it belongs to gold source or contains any key evidence snippet
        source_match = source_id in supp_set
        evidence_match = any(ev.lower() in text for ev in expected_evidence) if expected_evidence else False

        if source_match or evidence_match:
            relevant_count += 1

    return round(relevant_count / len(retrieved_chunks), 4)


def compute_context_recall(
    retrieved_chunks: List[Dict[str, Any]],
    expected_evidence: List[str],
) -> float:
    """
    Recall = (Number of expected evidence items covered in retrieved context) / (Total expected evidence items).
    For unanswerable queries (0 expected evidence items), returns 1.0.
    """
    if not expected_evidence:
        return 1.0

    combined_context = " ".join(c.get("text", "") for c in retrieved_chunks).lower()
    covered = 0
    for ev in expected_evidence:
        if ev.lower() in combined_context:
            covered += 1

    return round(covered / len(expected_evidence), 4)


def extract_citations(answer: str) -> List[str]:
    """Extract inline source citation identifiers like [Source A], [Source B], [src_wiki_transformers]."""
    if not answer:
        return []
    # Match patterns like [Source A], [Source 1], [src_wiki_transformers], [Source A (02:15)]
    raw_matches = re.findall(r"\[([^\]]+)\]", answer)
    citations = []
    for m in raw_matches:
        # Ignore markdown links target e.g. [text](url) where m is text
        # Filter for citations
        if any(keyword in m.lower() for keyword in ["source", "src_", "wiki", "paper", "notes", "yt"]):
            # Normalize e.g. "Source A (02:15)" -> extract source identifier
            parts = re.split(r"[,;]|\band\b", m)
            for p in parts:
                cleaned = p.strip()
                # Remove timestamp part if embedded inside brackets
                cleaned = re.sub(r"\(.*?\)", "", cleaned).strip()
                cleaned = re.sub(r"@.*", "", cleaned).strip()
                if cleaned:
                    citations.append(cleaned)
    return citations


def extract_timestamps(text: str) -> List[str]:
    """Extract timestamps formatted like 02:15 or 14:20 or [08:40]."""
    if not text:
        return []
    matches = re.findall(r"\b(\d{1,2}:\d{2})\b", text)
    return list(dict.fromkeys(matches))


def compute_citation_metrics(
    answer: str,
    supporting_source_ids: List[str],
    source_id_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[float, float, List[str]]:
    """
    Calculate:
    - Citation Precision: Fraction of cited sources in answer that are true supporting sources.
    - Citation Completeness (Recall): Fraction of true supporting sources that appear in answer citations.
    """
    citations = extract_citations(answer)
    source_map = source_id_mapping or {}

    # Normalize citations using mapping e.g. "Source A" -> "src_wiki_transformers"
    normalized_citations = []
    for c in citations:
        resolved = source_map.get(c, c)
        normalized_citations.append(resolved)

    gold_set = set(supporting_source_ids)

    # For unanswerable queries: if no citations and gold_set is empty -> perfect 1.0
    if not gold_set:
        precision = 1.0 if not normalized_citations else 0.0
        recall = 1.0
        return precision, recall, normalized_citations

    if not normalized_citations:
        return 0.0, 0.0, []

    valid_citations = 0
    for c in normalized_citations:
        # Check direct match or substring match with gold sources
        if any(g.lower() in c.lower() or c.lower() in g.lower() for g in gold_set):
            valid_citations += 1

    precision = round(valid_citations / len(normalized_citations), 4)

    # Check how many gold sources were cited
    covered_gold = 0
    for g in gold_set:
        if any(g.lower() in c.lower() or c.lower() in g.lower() for c in normalized_citations):
            covered_gold += 1

    completeness = round(covered_gold / len(gold_set), 4)

    return precision, completeness, normalized_citations


def compute_timestamp_metrics(
    answer: str,
    expected_timestamps: List[str],
    requires_timestamps: bool,
) -> Tuple[float, float, List[str]]:
    """
    Calculate timestamp precision and recall for video/YouTube answers.
    """
    extracted = extract_timestamps(answer)
    if not requires_timestamps or not expected_timestamps:
        return (1.0, 1.0, extracted) if not extracted else (1.0, 1.0, extracted)

    if not extracted:
        return (0.0, 0.0, [])

    gold_set = set(expected_timestamps)
    valid_extracted = sum(1 for ts in extracted if ts in gold_set)
    precision = round(valid_extracted / len(extracted), 4)

    covered_gold = sum(1 for ts in gold_set if ts in extracted)
    recall = round(covered_gold / len(gold_set), 4)

    return precision, recall, extracted


def compute_hallucination_indicator(
    answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    is_answerable: bool = True,
) -> float:
    """
    Measures the hallucination risk index (0.0 = completely grounded, 1.0 = highly unsupported).
    Calculated as the fraction of key content tokens in the generated answer that do NOT appear
    anywhere in the retrieved context.
    """
    if not is_answerable:
        # For unanswerable questions, if the model refuses or notes absence, score is 0.0
        refusal_phrases = ["not contain", "does not state", "not mentioned", "no information", "cannot be answered", "unanswerable"]
        if any(p in answer.lower() for p in refusal_phrases):
            return 0.0
        # If the model fabricated an elaborate answer for an unanswerable query, high hallucination
        return 1.0

    ans_tokens = clean_text_tokens(answer)
    if not ans_tokens:
        return 0.0

    context_str = " ".join(c.get("text", "") for c in retrieved_chunks)
    context_tokens = clean_text_tokens(context_str)

    unsupported_tokens = ans_tokens - context_tokens
    # Score is ratio of unsupported tokens to total tokens
    hallucination_score = len(unsupported_tokens) / len(ans_tokens)
    return round(min(1.0, max(0.0, hallucination_score)), 4)


def compute_answer_correctness(
    answer: str,
    expected_answer: str,
    expected_evidence: List[str],
    is_answerable: bool = True,
) -> float:
    """
    Deterministic score of answer correctness combining:
    1. Key evidence presence (50%)
    2. Overlap with ground truth key tokens (50%)
    3. Proper handling of unanswerable queries.
    """
    if not is_answerable:
        refusal_phrases = [
            "do not contain", "does not contain", "no information", "not found",
            "not mentioned", "cannot be determined", "unanswerable", "no source"
        ]
        if any(phrase in answer.lower() for phrase in refusal_phrases):
            return 1.0
        return 0.0

    # 1. Evidence coverage
    ev_score = 0.0
    if expected_evidence:
        found_ev = sum(1 for ev in expected_evidence if ev.lower() in answer.lower())
        ev_score = found_ev / len(expected_evidence)
    else:
        ev_score = 1.0

    # 2. Token overlap with expected answer
    ans_tokens = clean_text_tokens(answer)
    gold_tokens = clean_text_tokens(expected_answer)
    token_score = 0.0
    if gold_tokens:
        overlap = ans_tokens.intersection(gold_tokens)
        token_score = len(overlap) / len(gold_tokens)

    # Combined composite
    composite = (0.5 * ev_score) + (0.5 * min(1.0, token_score * 1.2))
    return round(min(1.0, max(0.0, composite)), 4)


def estimate_token_consumption(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    answer: str,
) -> Dict[str, int]:
    """
    Estimate prompt and generation tokens based on characters (approx 4 chars per token).
    """
    context_chars = sum(len(c.get("text", "")) for c in retrieved_chunks)
    prompt_chars = len(question) + context_chars + 1200  # including system instructions
    gen_chars = len(answer)

    prompt_tokens = max(1, prompt_chars // 4)
    completion_tokens = max(1, gen_chars // 4)
    total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
