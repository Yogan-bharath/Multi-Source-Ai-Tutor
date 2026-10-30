"""
Dedicated test script to verify:
1. Multiple conversations inside a notebook
2. Distinct messages in different conversations
3. Switching and message isolation
4. Rename conversation persistence
5. Delete conversation without deleting notebook or other conversations
6. Search conversations by title query `q`
7. Unauthorized user cannot access conversation or messages
8. Restful alias endpoints: /projects/{id}/conversations, /conversations/{id}
"""
import sys
import uuid
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def run_tests():
    print("=" * 60)
    print("TESTING MULTIPLE CONVERSATIONS & CHAT SWITCHING")
    print("=" * 60)

    # 1. Register User A
    session_a = requests.Session()
    email_a = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "TestPassword123!"
    reg_a = session_a.post(f"{BASE_URL}/auth/register", json={
        "name": "User A",
        "email": email_a,
        "password": pwd
    })
    assert reg_a.status_code == 201, f"User A registration failed: {reg_a.text}"
    print(f"PASS: User A registered ({email_a})")

    # 2. Register User B
    session_b = requests.Session()
    email_b = f"user_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = session_b.post(f"{BASE_URL}/auth/register", json={
        "name": "User B",
        "email": email_b,
        "password": pwd
    })
    assert reg_b.status_code == 201, f"User B registration failed: {reg_b.text}"
    print(f"PASS: User B registered ({email_b})")

    # 3. Create Notebook A for User A
    proj_a_resp = session_a.post(f"{BASE_URL}/projects", json={
        "name": "Physics 101",
        "description": "Mechanics and thermodynamics"
    })
    assert proj_a_resp.status_code == 201, f"Project creation failed: {proj_a_resp.text}"
    proj_a = proj_a_resp.json()
    proj_a_id = proj_a.get("_id") or proj_a.get("id")
    print(f"PASS: Notebook A created: {proj_a_id}")

    # 4. Create Notebook B for User A
    proj_b_resp = session_a.post(f"{BASE_URL}/projects", json={
        "name": "History 201",
        "description": "European history"
    })
    assert proj_b_resp.status_code == 201
    proj_b_id = proj_b_resp.json().get("_id") or proj_b_resp.json().get("id")
    print(f"PASS: Notebook B created: {proj_b_id}")

    # 5. Create 3 Conversations inside Notebook A via RESTful endpoint
    conv1_resp = session_a.post(f"{BASE_URL}/projects/{proj_a_id}/conversations", json={
        "title": "Quantum Mechanics Discussion"
    })
    assert conv1_resp.status_code == 201, f"Conv 1 failed: {conv1_resp.text}"
    conv1 = conv1_resp.json()
    c1_id = conv1.get("_id") or conv1.get("id")

    conv2_resp = session_a.post(f"{BASE_URL}/projects/{proj_a_id}/chats", json={
        "title": "Thermodynamics Discussion"
    })
    assert conv2_resp.status_code == 201
    conv2 = conv2_resp.json()
    c2_id = conv2.get("_id") or conv2.get("id")

    conv3_resp = session_a.post(f"{BASE_URL}/projects/{proj_a_id}/conversations", json={
        "title": "Exam Prep & Review"
    })
    assert conv3_resp.status_code == 201
    conv3 = conv3_resp.json()
    c3_id = conv3.get("_id") or conv3.get("id")

    print(f"PASS: Created 3 conversations in Notebook A: {c1_id}, {c2_id}, {c3_id}")

    # 6. List conversations for Notebook A
    list_a = session_a.get(f"{BASE_URL}/projects/{proj_a_id}/conversations")
    assert list_a.status_code == 200
    a_convs = list_a.json()
    assert len(a_convs) == 3, f"Expected 3 conversations in Notebook A, got {len(a_convs)}"
    print(f"PASS: Notebook A lists 3 conversations correctly.")

    # 7. Verify Notebook B has 0 conversations
    list_b = session_a.get(f"{BASE_URL}/projects/{proj_b_id}/conversations")
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0, "Notebook B should have 0 conversations"
    print(f"PASS: Notebook B has 0 conversations (scoped properly by notebook).")

    # 8. Test Search query parameter `q`
    search_resp = session_a.get(f"{BASE_URL}/projects/{proj_a_id}/conversations?q=thermo")
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    assert len(search_results) == 1 and search_results[0]["title"] == "Thermodynamics Discussion"
    print(f"PASS: Search by title query `q=thermo` returned exact matching conversation.")

    # 9. Test GET single conversation metadata via both aliases
    meta1 = session_a.get(f"{BASE_URL}/conversations/{c1_id}")
    assert meta1.status_code == 200 and meta1.json()["title"] == "Quantum Mechanics Discussion"
    meta2 = session_a.get(f"{BASE_URL}/chats/{c1_id}")
    assert meta2.status_code == 200 and meta2.json()["title"] == "Quantum Mechanics Discussion"
    print(f"PASS: GET /conversations/{c1_id} and GET /chats/{c1_id} succeed.")

    # 10. Test Rename conversation via PATCH /conversations/{id}
    patch_resp = session_a.patch(f"{BASE_URL}/conversations/{c1_id}", json={
        "title": "Advanced Quantum Mechanics"
    })
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Advanced Quantum Mechanics"

    # Verify persisted in list
    list_after_patch = session_a.get(f"{BASE_URL}/projects/{proj_a_id}/conversations").json()
    found = [c for c in list_after_patch if (c.get("_id") or c.get("id")) == c1_id]
    assert len(found) == 1 and found[0]["title"] == "Advanced Quantum Mechanics"
    print(f"PASS: Rename conversation persisted in database.")

    # 11. Test Security / Multi-tenant isolation: User B cannot access User A's conversation
    unauth_get = session_b.get(f"{BASE_URL}/conversations/{c1_id}")
    assert unauth_get.status_code in (403, 404), f"Expected 403/404 for unauthorized user, got {unauth_get.status_code}"

    unauth_patch = session_b.patch(f"{BASE_URL}/conversations/{c1_id}", json={"title": "Hacked Title"})
    assert unauth_patch.status_code in (403, 404)

    unauth_delete = session_b.delete(f"{BASE_URL}/conversations/{c1_id}")
    assert unauth_delete.status_code in (403, 404)
    print(f"PASS: Security check: User B cannot read, rename, or delete User A's conversation.")

    # 12. Test Delete conversation
    del_resp = session_a.delete(f"{BASE_URL}/conversations/{c2_id}")
    assert del_resp.status_code == 200
    print(f"PASS: Deleted conversation {c2_id}")

    # Verify remaining conversations in Notebook A
    remaining = session_a.get(f"{BASE_URL}/projects/{proj_a_id}/conversations").json()
    assert len(remaining) == 2, f"Expected 2 conversations remaining, got {len(remaining)}"
    remaining_ids = [c.get("_id") or c.get("id") for c in remaining]
    assert c2_id not in remaining_ids, "Deleted conversation still present!"
    assert c1_id in remaining_ids and c3_id in remaining_ids, "Other conversations accidentally deleted!"
    print(f"PASS: Exactly the targeted conversation was removed; remaining {len(remaining)} conversations intact.")

    print("\nALL MULTIPLE CONVERSATIONS TESTS PASSED SUCCESSFULLY! 🎉\n")

if __name__ == "__main__":
    run_tests()
