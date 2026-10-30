"""
Unit test suite for the RAG and GraphRAG evaluation metrics module.
Verifies all deterministic metrics:
- Context precision & recall
- Citation precision & completeness
- YouTube timestamp extraction & recall
- Hallucination index calculation
- Correctness & unanswerable query refusal detection
"""
import sys
from pathlib import Path
import unittest

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.eval_metrics import (
    clean_text_tokens,
    compute_context_precision,
    compute_context_recall,
    extract_citations,
    extract_timestamps,
    compute_citation_metrics,
    compute_timestamp_metrics,
    compute_hallucination_indicator,
    compute_answer_correctness,
    estimate_token_consumption,
)


def test_clean_text_tokens():
    tokens = clean_text_tokens("The Transformer's self-attention runs with O(N^2) complexity!")
    assert "transformer" in tokens
    assert "complexity" in tokens
    # stopword removed
    assert "the" not in tokens
    assert "with" not in tokens


def test_context_precision_and_recall():
    chunks = [
        {"source_id": "src_wiki", "text": "Self-attention computes O(N^2) quadratic complexity."},
        {"source_id": "src_paper", "text": "RAG reduces hallucinations by retrieving passages."},
        {"source_id": "src_random", "text": "Unrelated text about weather in London."},
    ]
    supporting_sids = ["src_wiki", "src_paper"]
    expected_evidence = ["quadratic", "hallucinations"]

    # 2 out of 3 chunks are relevant
    precision = compute_context_precision(chunks, supporting_sids, expected_evidence)
    assert precision == round(2 / 3, 4)

    # Both evidence items ("quadratic" and "hallucinations") are present
    recall = compute_context_recall(chunks, expected_evidence)
    assert recall == 1.0

    # Test partial recall
    partial_recall = compute_context_recall(chunks[:1], expected_evidence)
    assert partial_recall == 0.5


def test_citation_metrics():
    answer = (
        "Self-attention has quadratic complexity [Source A]. "
        "RAG grounds the model in documents [Source B]. "
        "Also check [Source X] for unrelated claims."
    )
    source_map = {"Source A": "src_wiki", "Source B": "src_paper", "Source X": "src_unrelated"}
    gold_sources = ["src_wiki", "src_paper"]

    prec, comp, norm_cites = compute_citation_metrics(answer, gold_sources, source_map)
    # 2 out of 3 citations are gold
    assert prec == round(2 / 3, 4)
    # Both gold sources were cited
    assert comp == 1.0
    assert len(norm_cites) == 3


def test_timestamp_metrics():
    answer = "The video explains multi-hop retrieval failure at [08:40] and shows graph fusion at [14:20]."
    expected_ts = ["08:40", "14:20"]

    prec, recall, extracted = compute_timestamp_metrics(answer, expected_ts, requires_timestamps=True)
    assert extracted == ["08:40", "14:20"]
    assert prec == 1.0
    assert recall == 1.0

    # Missed timestamp
    partial_answer = "Check the video at [08:40]."
    p2, r2, ext2 = compute_timestamp_metrics(partial_answer, expected_ts, requires_timestamps=True)
    assert p2 == 1.0
    assert r2 == 0.5


def test_hallucination_indicator():
    chunks = [{"text": "Transformers were introduced by Google in 2017 using self-attention mechanisms."}]
    
    # Grounded answer
    grounded_ans = "Google introduced Transformers in 2017 utilizing self-attention mechanisms."
    score_grounded = compute_hallucination_indicator(grounded_ans, chunks, is_answerable=True)
    assert score_grounded < 0.2

    # Heavily fabricated answer
    fabricated_ans = "Albert Einstein invented quantum transformers in 1905 while working at CERN in Geneva Switzerland."
    score_fabricated = compute_hallucination_indicator(fabricated_ans, chunks, is_answerable=True)
    assert score_fabricated > 0.7


def test_unanswerable_metrics():
    # If question is unanswerable, refusal should receive 1.0 correctness and 0.0 hallucination
    refusal_answer = "The indexed sources do not contain information regarding Roman agricultural subsidies under Emperor Trajan."
    corr = compute_answer_correctness(refusal_answer, "", [], is_answerable=False)
    assert corr == 1.0

    hal = compute_hallucination_indicator(refusal_answer, [], is_answerable=False)
    assert hal == 0.0

    # If model hallucinates an answer to unanswerable question
    bad_answer = "Emperor Trajan provided 500 sesterces per acre of farmland in 112 AD."
    bad_corr = compute_answer_correctness(bad_answer, "", [], is_answerable=False)
    assert bad_corr == 0.0

    bad_hal = compute_hallucination_indicator(bad_answer, [], is_answerable=False)
    assert bad_hal == 1.0


def test_token_estimation():
    tokens = estimate_token_consumption("What is RAG?", [{"text": "Retrieval Augmented Generation"}], "RAG combines search.")
    assert tokens["prompt_tokens"] > 0
    assert tokens["completion_tokens"] > 0
    assert tokens["total_tokens"] == tokens["prompt_tokens"] + tokens["completion_tokens"]


if __name__ == "__main__":
    test_clean_text_tokens()
    test_context_precision_and_recall()
    test_citation_metrics()
    test_timestamp_metrics()
    test_hallucination_indicator()
    test_unanswerable_metrics()
    test_token_estimation()
    print("ALL EVALUATION METRIC UNIT TESTS PASSED!")
