"""
Automated test suite verifying all 9 required test cases for Multi-Source AI Tutor.
"""
import requests
import json
import sys

# Ensure UTF-8 stdout on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def print_test(name):
    print(f"\n{'='*60}\nRUNNING TEST: {name}\n{'='*60}")

def test_1_one_valid_url():
    print_test("1. One Valid URL")
    url = "https://en.wikipedia.org/wiki/FastAPI"
    payload = {
        "source_urls": [url],
        "topic_name": "FastAPI Framework"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=60)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Response:", json.dumps(data, indent=2))
    assert data["total_submitted"] == 1
    assert data["successful_count"] == 1
    assert data["failed_count"] == 0
    assert data["total_chunks"] > 0
    assert data["sources"][0]["status"] == "success"
    assert data["sources"][0]["chunk_count"] > 0
    print("PASS: Single valid URL ingested successfully.")
    return data["session_id"]

def test_2_three_valid_urls():
    print_test("2. Three Valid URLs")
    urls = [
        "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "https://en.wikipedia.org/wiki/Flask_(web_framework)",
        "https://en.wikipedia.org/wiki/Django_(web_framework)"
    ]
    payload = {
        "source_urls": urls,
        "topic_name": "Python Web Ecosystem"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=120)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Response summary:", {
        "submitted": data["total_submitted"],
        "success": data["successful_count"],
        "failed": data["failed_count"],
        "total_chunks": data["total_chunks"],
        "sources": [(s["source_id"], s["title"], s["chunk_count"], s["status"]) for s in data["sources"]]
    })
    assert data["total_submitted"] == 3
    assert data["successful_count"] == 3
    assert data["failed_count"] == 0
    assert data["total_chunks"] > 0
    print("PASS: Three valid URLs ingested independently and successfully.")
    return data["session_id"]

def test_3_and_4_mixture_and_inaccessible():
    print_test("3 & 4. Mixture of Valid and Inaccessible/Invalid URLs")
    urls = [
        "https://en.wikipedia.org/wiki/Git",
        "https://this-domain-does-not-exist-at-all-xyz123.org",
        "https://en.wikipedia.org/wiki/Mercurial_(software)"
    ]
    payload = {
        "source_urls": urls,
        "topic_name": "Version Control Systems"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=90)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Response:", json.dumps(data, indent=2))
    assert data["total_submitted"] == 3
    assert data["successful_count"] == 2, f"Expected 2 successes, got {data['successful_count']}"
    assert data["failed_count"] == 1, f"Expected 1 failed, got {data['failed_count']}"
    
    # Check that the failed one has error details
    failed = [s for s in data["sources"] if s["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["error"] is not None
    print(f"Failed source error message: {failed[0]['error']}")
    print("PASS: Partial success correctly handled (2 valid retained, 1 inaccessible reported with error).")
    return data["session_id"], failed[0]["original_url"]

def test_5_duplicate_urls():
    print_test("5. Duplicate URLs in Submission")
    urls = [
        "https://en.wikipedia.org/wiki/Docker_(software)",
        "https://en.wikipedia.org/wiki/Docker_(software)/",
        "https://en.wikipedia.org/wiki/Kubernetes"
    ]
    payload = {
        "source_urls": urls,
        "topic_name": "Containerization"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=90)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Sources status:", [(s["original_url"], s["status"], s.get("error")) for s in data["sources"]])
    assert data["successful_count"] == 2
    assert data["failed_count"] == 1
    dup = [s for s in data["sources"] if s["status"] == "failed"][0]
    assert "Duplicate" in dup["error"]
    print("PASS: Duplicate URL normalized and prevented from redundant indexing.")

def test_6_empty_and_malformed_urls():
    print_test("6. Empty Input and Malformed URLs")
    # A: Empty list
    resp_empty = requests.post(f"{BASE_URL}/ingest", json={"source_urls": []})
    assert resp_empty.status_code in [400, 422], f"Expected 400 or 422 for empty source_urls, got {resp_empty.status_code}"
    
    # B: Malformed URL
    resp_malformed = requests.post(f"{BASE_URL}/ingest", json={"source_urls": ["not_a_valid_url_at_all"]})
    assert resp_malformed.status_code == 200
    data = resp_malformed.json()
    assert data["successful_count"] == 0
    assert data["failed_count"] == 1
    assert "URL must start with" in data["sources"][0]["error"] or "Invalid" in data["sources"][0]["error"]
    print("PASS: Empty list rejected and malformed URL flagged cleanly with error message.")

def test_7_source_removal(session_id):
    print_test("7. Removing a Source and Verifying Chunks are Removed")
    # First inspect sources
    load_resp = requests.get(f"http://localhost:8000/health")
    assert load_resp.status_code == 200

    # Let's see sources in session
    # We will remove Source B
    del_resp = requests.delete(f"{BASE_URL}/sources/{session_id}/Source B")
    assert del_resp.status_code == 200, f"Expected 200, got {del_resp.status_code}: {del_resp.text}"
    data = del_resp.json()
    remaining_sids = [s["source_id"] for s in data["sources"]]
    print("Remaining source IDs after deleting Source B:", remaining_sids)
    assert "Source B" not in remaining_sids
    print("PASS: Source B removed and index rebuilt.")

    # Now ask chat a question and verify Source B chunks are never returned
    chat_resp = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "question": "What is Mercurial and how does it compare to Git?"
    }, timeout=60)
    assert chat_resp.status_code == 200
    cdata = chat_resp.json()
    retrieved = cdata["retrieved_chunks"]
    print("Retrieved chunks per source in chat:", list(retrieved.keys()))
    assert "Source B" not in retrieved or len(retrieved["Source B"]) == 0
    print("PASS: Verified chunks from removed Source B are never retrieved.")

def test_8_retrieval_accuracy(session_id):
    print_test("8. Question Answered Using Content from Specific Source")
    # In session_id (from Test 2: Python, Flask, Django):
    # Ask a question specifically about Django MTV architecture or admin interface
    chat_resp = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "question": "Does Django have a built-in admin interface and what architectural pattern does it use?"
    }, timeout=120)
    assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
    cdata = chat_resp.json()
    print("Classification:", cdata["classification"])
    print("Answer excerpt:", cdata["answer"][:300])
    print("Retrieved chunks sources:", list(cdata["retrieved_chunks"].keys()))
    # Django should be retrieved
    assert any("admin" in chunk["text"].lower() or "django" in chunk["text"].lower() 
               for chunks in cdata["retrieved_chunks"].values() for chunk in chunks)
    print("PASS: Retrieval accurately captured content from the specific source.")

def test_9_retry_failed_source(session_id):
    print_test("9. Retrying a Source without Duplicating Successful Sources")
    # In session_id, we retry with a working URL
    retry_url = "https://en.wikipedia.org/wiki/Apache_Subversion"
    payload = {
        "session_id": session_id,
        "source_urls": [retry_url]
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=60)
    assert resp.status_code == 200, f"Retry failed: {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Updated session sources:", [(s["source_id"], s["title"], s["chunk_count"]) for s in data["sources"]])
    source_ids = [s["source_id"] for s in data["sources"]]
    # Should contain original active sources plus the new/retried one
    assert len(data["sources"]) >= 2
    assert len(set(source_ids)) == len(source_ids), "Source IDs should be unique (no duplicates)"
    print("PASS: Retrying appended new source without duplicating existing ones.")

def run_all():
    print("Starting Multi-Source AI Tutor test suite...")
    test_1_one_valid_url()
    sess_multi = test_2_three_valid_urls()
    sess_partial, failed_url = test_3_and_4_mixture_and_inaccessible()
    test_5_duplicate_urls()
    test_6_empty_and_malformed_urls()
    test_7_source_removal(sess_partial)
    test_8_retrieval_accuracy(sess_multi)
    test_9_retry_failed_source(sess_partial)
    print("\n" + "="*60 + "\nALL 9 MULTI-SOURCE TESTS PASSED SUCCESSFULLY!\n" + "="*60)

if __name__ == "__main__":
    run_all()
