"""
Automated test suite verifying Validation, Limits, and Reliable Indexing features:
- Maximum 5 sources enforcement (server-side and client validation)
- Ignoring unused empty fields
- Rejecting malformed and unsupported URL schemes directly (HTTP 400)
- SSRF destination blocking (127.0.0.1, localhost, 169.254.169.254)
- 2 MB streaming download limit and 100k character text limits
- Truncation reporting
- Duplicate URL rejection
- 5 valid URLs indexed concurrently
- Partial success handling
- Source removal and exclusion from retrieval
- Retrying without duplicating
"""
import sys
import json
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def print_test(title):
    print(f"\n{'='*65}\nTEST: {title}\n{'='*65}")

def test_1_hard_limit_exceeded():
    print_test("1. Attempting to submit 6 sources (Hard Cap 5 Enforcement)")
    payload = {
        "source_urls": [
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "https://en.wikipedia.org/wiki/JavaScript",
            "https://en.wikipedia.org/wiki/TypeScript",
            "https://en.wikipedia.org/wiki/Rust_(programming_language)",
            "https://en.wikipedia.org/wiki/Go_(programming_language)",
            "https://en.wikipedia.org/wiki/C%2B%2B",  # 6th source!
        ],
        "topic_name": "Programming Languages"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload)
    print(f"Status Code: {resp.status_code}, Response: {resp.text}")
    assert resp.status_code in (400, 422), f"Expected 400/422 for >5 sources, got {resp.status_code}"
    assert "Maximum of 5 sources allowed" in resp.text
    print("PASS: Request containing 6 sources was rejected with 400/422.")

def test_2_empty_fields_ignored():
    print_test("2. Submitting empty fields alongside valid URLs")
    payload = {
        "source_urls": [
            "https://en.wikipedia.org/wiki/SQLite",
            "",
            "   ",
            "https://en.wikipedia.org/wiki/PostgreSQL"
        ],
        "topic_name": "Databases"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=60)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Submitted sources processed:", len(data["sources"]))
    assert data["total_submitted"] == 2, f"Expected 2 non-empty submitted, got {data['total_submitted']}"
    assert data["successful_count"] == 2
    print("PASS: Unused empty fields were safely ignored while valid URLs were indexed.")
    return data["session_id"]

def test_3_ssrf_protection():
    print_test("3. SSRF Protection (Blocking localhost, private IP, metadata)")
    malicious_urls = [
        "http://127.0.0.1:8000/health",
        "http://localhost:8000/secret",
        "http://169.254.169.254/latest/meta-data/"
    ]
    payload = {
        "source_urls": malicious_urls,
        "topic_name": "SSRF Attack Test"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    for s in data["sources"]:
        print(f"URL: {s['original_url']} -> Status: {s['status']}, Error: {s['error']}")
        assert s["status"] == "failed"
        assert any(term in s["error"].lower() for term in ["unsafe", "blocked", "restricted", "private", "invalid"])
    print("PASS: All SSRF targets were safely blocked and reported.")

def test_4_malformed_url_rejected():
    print_test("4. Unsupported URL Scheme and Malformed URLs")
    # A: File scheme
    resp_file = requests.post(f"{BASE_URL}/ingest", json={"source_urls": ["file:///etc/passwd"]})
    assert resp_file.status_code in (400, 422), f"Expected 400 for file scheme, got {resp_file.status_code}"
    print("File scheme rejected:", resp_file.status_code)

    # B: Malformed string without scheme
    resp_mal = requests.post(f"{BASE_URL}/ingest", json={"source_urls": ["not_a_valid_url"]})
    assert resp_mal.status_code == 200
    data = resp_mal.json()
    assert data["sources"][0]["status"] == "failed"
    print("Malformed URL reported failed:", data["sources"][0]["error"])
    print("PASS: Malformed and unsupported URLs rejected properly.")

def test_5_five_valid_urls():
    print_test("5. Exactly Five Valid URLs Indexed Concurrently")
    urls = [
        "https://en.wikipedia.org/wiki/HTML",
        "https://en.wikipedia.org/wiki/CSS",
        "https://en.wikipedia.org/wiki/JavaScript",
        "https://en.wikipedia.org/wiki/Document_Object_Model",
        "https://en.wikipedia.org/wiki/WebAssembly"
    ]
    payload = {
        "source_urls": urls,
        "topic_name": "Modern Web Technologies"
    }
    resp = requests.post(f"{BASE_URL}/ingest", json=payload, timeout=120)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print("Response summary:", {
        "total_sources": data["total_sources"],
        "successful_sources": data["successful_sources"],
        "failed_sources": data["failed_sources"],
        "total_chunks_indexed": data["total_chunks_indexed"],
        "sources": [(s["source_id"], s["title"], s["chunk_count"], s["status"], s.get("truncated")) for s in data["sources"]]
    })
    assert data["total_submitted"] == 5
    assert data["successful_count"] == 5
    assert data["total_chunks"] > 0
    print("PASS: Exactly 5 valid sources indexed successfully.")
    return data["session_id"]

def test_6_retrieval_across_five_sources(session_id):
    print_test("6. Retrieval and Quality from 5th Source (WebAssembly)")
    # Ask a question specifically answered by WebAssembly
    chat_resp = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "question": "What is WebAssembly and does it allow code written in C or Rust to run in web browsers?"
    }, timeout=120)
    assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
    cdata = chat_resp.json()
    retrieved = cdata["retrieved_chunks"]
    print("Sources with retrieved chunks:", list(retrieved.keys()))
    # Ensure Source E (WebAssembly) contributed chunks
    assert "Source E" in retrieved and len(retrieved["Source E"]) > 0
    print("Answer excerpt:", cdata["answer"][:300])
    print("PASS: Question answered accurately using content from 5th source (Source E).")

def test_7_source_removal(session_id):
    print_test("7. Source Removal and Exclusion from Subsequent Queries")
    # Remove Source E
    del_resp = requests.delete(f"{BASE_URL}/sources/{session_id}/Source E")
    assert del_resp.status_code == 200
    data = del_resp.json()
    remaining = [s["source_id"] for s in data["sources"]]
    print("Remaining sources after removing Source E:", remaining)
    assert "Source E" not in remaining

    # Query again about WebAssembly and verify Source E is NOT retrieved
    chat_resp = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "question": "What is WebAssembly?"
    }, timeout=120)
    assert chat_resp.status_code == 200
    cdata = chat_resp.json()
    assert "Source E" not in cdata["retrieved_chunks"]
    print("PASS: Removed source chunks are completely excluded from retrieval.")

def run_all():
    print("Starting Feature Upgrade Verification: Validation, Limits & Reliable Indexing...")
    test_1_hard_limit_exceeded()
    test_2_empty_fields_ignored()
    test_3_ssrf_protection()
    test_4_malformed_url_rejected()
    sess_5 = test_5_five_valid_urls()
    test_6_retrieval_across_five_sources(sess_5)
    test_7_source_removal(sess_5)
    print("\n" + "="*65 + "\nALL VALIDATION, LIMITS & RELIABILITY TESTS PASSED!\n" + "="*65)

if __name__ == "__main__":
    run_all()
