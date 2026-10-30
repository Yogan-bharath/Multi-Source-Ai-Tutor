"""
Test Learning Studio endpoints, text ingestion, and file upload ingestion.
"""
import sys
import uuid
import io
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def run_tests():
    print("="*60)
    print("TESTING LEARNING STUDIO & MULTI-FORMAT INGESTION")
    print("="*60)

    # Wait for server ready
    import time
    for _ in range(10):
        try:
            h = requests.get("http://localhost:8000/health", timeout=5)
            if h.status_code == 200:
                print("Server ready:", h.json())
                break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Server not responding")
    time.sleep(1)

    session = requests.Session()
    email = f"studio_{uuid.uuid4().hex[:6]}@example.com"
    reg = session.post(f"{BASE_URL}/auth/register", json={
        "name": "Studio Tester",
        "email": email,
        "password": "Password123!"
    })
    assert reg.status_code == 201


    # Create project
    proj = session.post(f"{BASE_URL}/projects", json={
        "name": "Machine Learning Fundamentals",
        "description": "Supervised, unsupervised and reinforcement learning"
    }).json()
    project_id = proj["_id"]
    print(f"Created project: {project_id}")

    # 1. Test Text Ingestion
    print("\n[1] Testing pasted text ingestion (/api/ingest/text)...")
    text_content = (
        "Supervised learning algorithms build a mathematical model of a set of data that contains both the inputs and the desired outputs. "
        "The data is known as training data, and consists of a set of training examples. Each training example has one or more inputs and the desired output, "
        "also known as a supervisory signal. In supervised learning, the goal is to approximate the mapping function so well that when you have new input data, "
        "you can predict the output variables. Classification and regression are the two major types of supervised learning problems."
    )
    t_resp = session.post(f"{BASE_URL}/ingest/text", json={
        "project_id": project_id,
        "title": "Supervised Learning Notes",
        "text": text_content,
    })
    assert t_resp.status_code == 200, f"Text ingest failed: {t_resp.text}"
    t_data = t_resp.json()
    assert t_data["successful_count"] == 1
    print(f"  -> Ingested pasted text successfully: {t_data['sources'][0]['title']}")

    # 2. Test File Upload Ingestion
    print("\n[2] Testing file upload ingestion (/api/ingest/upload)...")
    file_bytes = io.BytesIO(
        b"Unsupervised learning is a type of algorithm that learns patterns from untagged data. "
        b"The hope is that, through mimicry, the machine is forced to build a compact internal representation of its world. "
        b"Two of the main methods used in unsupervised learning are principal component and cluster analysis. "
        b"Cluster analysis can be used on unsupervised learning to group, or segment, datasets with shared attributes."
    )
    files = {"file": ("unsupervised_learning.txt", file_bytes, "text/plain")}
    data = {"project_id": project_id, "title": "Unsupervised Learning Guide"}
    u_resp = session.post(f"{BASE_URL}/ingest/upload", data=data, files=files)
    assert u_resp.status_code == 200, f"Upload ingest failed: {u_resp.text}"
    u_data = u_resp.json()
    assert u_data["successful_count"] == 1
    print(f"  -> Uploaded and indexed file successfully: {u_data['sources'][0]['title']}")

    # Verify project sources count
    srcs = session.get(f"{BASE_URL}/projects/{project_id}/sources").json()
    assert len(srcs) == 2
    print(f"  -> Total project sources in DB: {len(srcs)}")

    # 3. Test Studio Summary
    print("\n[3] Testing Studio Summary (/api/projects/{id}/studio/summary)...")
    sum_resp = session.get(f"{BASE_URL}/projects/{project_id}/studio/summary")
    assert sum_resp.status_code == 200, f"Studio summary failed: {sum_resp.text}"
    summary = sum_resp.json()
    assert "data" in summary
    print(f"  -> Summary title: {summary['data'].get('title')}")
    print(f"  -> Overview length: {len(summary['data'].get('overview', ''))}")
    assert len(summary['data'].get('overview', '')) > 20

    # 4. Test Studio Flashcards
    print("\n[4] Testing Studio Flashcards (/api/projects/{id}/studio/flashcards)...")
    fc_resp = session.get(f"{BASE_URL}/projects/{project_id}/studio/flashcards")
    assert fc_resp.status_code == 200, f"Studio flashcards failed: {fc_resp.text}"
    cards = fc_resp.json()["data"].get("flashcards", [])
    print(f"  -> Generated {len(cards)} flashcards")
    assert len(cards) > 0

    # 5. Test Studio Quiz
    print("\n[5] Testing Studio Quiz (/api/projects/{id}/studio/quiz)...")
    qz_resp = session.get(f"{BASE_URL}/projects/{project_id}/studio/quiz")
    assert qz_resp.status_code == 200, f"Studio quiz failed: {qz_resp.text}"
    questions = qz_resp.json()["data"].get("questions", [])
    print(f"  -> Generated {len(questions)} quiz questions")
    assert len(questions) > 0

    print("\n=== ALL STUDIO & MULTI-FORMAT TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
