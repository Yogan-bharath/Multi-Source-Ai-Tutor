"""
Test suite for Phase 3: Project Ownership, Multi-Source Ingestion, and Safe FAISS Storage.
"""
import sys
import uuid
import os
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def run_phase3_tests():
    print("="*60)
    print("RUNNING PHASE 3 TESTS: Projects, Ownership & Safe FAISS")
    print("="*60)

    # 1. Setup User A and User B
    session_a = requests.Session()
    email_a = f"usera_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = session_a.post(f"{BASE_URL}/auth/register", json={
        "name": "User Alpha", "email": email_a, "password": "Password123!"
    })
    assert reg_a.status_code == 201

    session_b = requests.Session()
    email_b = f"userb_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = session_b.post(f"{BASE_URL}/auth/register", json={
        "name": "User Beta", "email": email_b, "password": "Password123!"
    })
    assert reg_b.status_code == 201

    # 2. User A creates a project
    proj_resp = session_a.post(f"{BASE_URL}/projects", json={
        "name": "Cloud Computing Project",
        "description": "Learning AWS and Distributed Storage"
    })
    assert proj_resp.status_code == 201, f"Expected 201, got {proj_resp.status_code}: {proj_resp.text}"
    proj_a = proj_resp.json()
    proj_a_id = proj_a["_id"]
    print("PASS: User A created project with ID:", proj_a_id)

    # 3. User B cannot access or modify User A's project
    b_get = session_b.get(f"{BASE_URL}/projects/{proj_a_id}")
    assert b_get.status_code == 404, f"Expected 404 for unauthorized project access, got {b_get.status_code}"

    b_patch = session_b.patch(f"{BASE_URL}/projects/{proj_a_id}", json={"name": "Hacked Project"})
    assert b_patch.status_code == 404

    b_del = session_b.delete(f"{BASE_URL}/projects/{proj_a_id}")
    assert b_del.status_code == 404
    print("PASS: User B is strictly blocked from accessing/mutating User A's project.")

    # 4. Ingest sources into User A's project
    ingest_resp = session_a.post(f"{BASE_URL}/ingest", json={
        "project_id": proj_a_id,
        "source_urls": [
            "https://en.wikipedia.org/wiki/Cloud_computing",
            "https://en.wikipedia.org/wiki/Serverless_computing"
        ],
        "topic_name": "Cloud Architecture"
    }, timeout=90)
    assert ingest_resp.status_code == 200, f"Expected 200, got {ingest_resp.status_code}: {ingest_resp.text}"
    idata = ingest_resp.json()
    assert idata["successful_count"] == 2
    assert idata["total_chunks"] > 0
    print("PASS: User A ingested sources into project; FAISS index created.")

    # Verify safe JSON metadata file exists (not pkl)
    index_id = proj_a["index_id"]
    json_path = os.path.join("./faiss_indices", f"{index_id}.meta.json")
    assert os.path.exists(json_path), f"JSON metadata file {json_path} must exist"
    print("PASS: Safe JSON metadata file verified (no pickle).")

    # 5. User A deletes a source from project
    del_src_resp = session_a.delete(f"{BASE_URL}/sources/{proj_a_id}/Source B")
    assert del_src_resp.status_code == 200
    updated_sources = del_src_resp.json()["sources"]
    assert "Source B" not in [s["source_id"] for s in updated_sources]
    print("PASS: Source B removed and project index rebuilt.")

    # 6. User A deletes the project
    del_proj = session_a.delete(f"{BASE_URL}/projects/{proj_a_id}")
    assert del_proj.status_code == 200
    assert not os.path.join("./faiss_indices", f"{index_id}.index") or not os.path.exists(os.path.join("./faiss_indices", f"{index_id}.index"))
    print("PASS: Project and associated FAISS index files deleted successfully.")

    print("\n" + "="*60)
    print("ALL PHASE 3 TESTS PASSED SUCCESSFULLY!")
    print("="*60)

if __name__ == "__main__":
    run_phase3_tests()
