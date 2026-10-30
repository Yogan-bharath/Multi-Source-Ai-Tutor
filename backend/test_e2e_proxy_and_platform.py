"""
End-to-End Verification of Next.js Proxy, Auth Cookies, Project Management, and Chat History.
Hits Next.js on http://localhost:3000/api/ to ensure the frontend proxy and cookies work seamlessly.
"""
import sys
import uuid
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

FRONTEND_PROXY_URL = "http://localhost:3000/api"

def run_e2e_tests():
    print("="*60)
    print("RUNNING END-TO-END PROXY & PLATFORM VERIFICATION")
    print(f"Targeting Next.js Proxy: {FRONTEND_PROXY_URL}")
    print("="*60)

    # 1. Register through Next.js proxy
    session = requests.Session()
    email = f"e2e_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "StrongPassword2026!"
    name = "Dr. Marie Curie"

    print(f"\n[1] Registering {name} via Next.js proxy...")
    reg_resp = session.post(f"{FRONTEND_PROXY_URL}/auth/register", json={
        "name": name,
        "email": email,
        "password": password
    })
    assert reg_resp.status_code == 201, f"Registration failed ({reg_resp.status_code}): {reg_resp.text}"
    user_data = reg_resp.json()
    assert user_data["email"] == email.lower()
    print("  -> User registered successfully through proxy.")
    assert "access_token" in session.cookies, "Auth cookie should be set and preserved by session"
    print("  -> Auth cookie received and preserved.")

    # 2. Check /auth/me through proxy
    print("\n[2] Checking /auth/me through proxy...")
    me_resp = session.get(f"{FRONTEND_PROXY_URL}/auth/me")
    assert me_resp.status_code == 200, f"Auth me failed ({me_resp.status_code}): {me_resp.text}"
    me_data = me_resp.json()
    assert me_data["name"] == name
    print("  -> Identity confirmed:", me_data["name"])

    # 3. Create Learning Project
    print("\n[3] Creating Project 'Quantum Physics' through proxy...")
    proj_resp = session.post(f"{FRONTEND_PROXY_URL}/projects", json={
        "name": "Quantum Physics",
        "description": "Intro to qubits and entanglement"
    })
    assert proj_resp.status_code == 201, f"Create project failed ({proj_resp.status_code}): {proj_resp.text}"
    project = proj_resp.json()
    project_id = project["_id"]
    print(f"  -> Project created with ID: {project_id}")

    # 4. List Projects
    print("\n[4] Listing projects...")
    list_proj = session.get(f"{FRONTEND_PROXY_URL}/projects")
    assert list_proj.status_code == 200
    projects = list_proj.json()
    assert any(p["_id"] == project_id for p in projects)
    print(f"  -> Found {len(projects)} project(s)")

    # 5. Ingest 1 source into project
    print("\n[5] Ingesting source into project via proxy...")
    ingest_resp = session.post(f"{FRONTEND_PROXY_URL}/ingest", json={
        "project_id": project_id,
        "source_urls": ["https://en.wikipedia.org/wiki/Qubit"]
    })
    assert ingest_resp.status_code == 200, f"Ingest failed: {ingest_resp.text}"
    print("  -> Source ingested successfully.")

    # 6. Verify project sources endpoint
    print("\n[6] Fetching project sources...")
    src_resp = session.get(f"{FRONTEND_PROXY_URL}/projects/{project_id}/sources")
    assert src_resp.status_code == 200
    sources = src_resp.json()
    assert len(sources) >= 1
    print(f"  -> Verified {len(sources)} source(s) associated with project.")

    # 7. Create a conversation
    print("\n[7] Creating a conversation thread...")
    conv_resp = session.post(f"{FRONTEND_PROXY_URL}/projects/{project_id}/chats", json={
        "title": "Quantum Computing Fundamentals"
    })
    assert conv_resp.status_code == 201
    chat_id = conv_resp.json()["_id"]
    print(f"  -> Conversation created: {chat_id}")

    # 8. Send a message
    print("\n[8] Sending question to conversation...")
    msg_resp = session.post(f"{FRONTEND_PROXY_URL}/chats/{chat_id}/message", json={
        "question": "What is a superposition in quantum physics?"
    })
    assert msg_resp.status_code == 200, f"Message failed: {msg_resp.text}"
    msg_data = msg_resp.json()
    print("  -> Response generated:")
    print("     Assistant content length:", len(msg_data["assistant_message"]["content"]))
    print("     Citations / Summaries count:", len(msg_data["assistant_message"].get("source_summaries", [])))

    # 9. Verify message history retrieval
    print("\n[9] Retrieving chat history...")
    history_resp = session.get(f"{FRONTEND_PROXY_URL}/chats/{chat_id}/messages")
    assert history_resp.status_code == 200
    messages = history_resp.json()["messages"]
    assert len(messages) == 2  # 1 user + 1 assistant
    print(f"  -> Confirmed {len(messages)} messages stored in persistent MongoDB history.")

    # 10. Logout and verify invalidation
    print("\n[10] Logging out...")
    logout_resp = session.post(f"{FRONTEND_PROXY_URL}/auth/logout")
    assert logout_resp.status_code == 200
    me_after = session.get(f"{FRONTEND_PROXY_URL}/auth/me")
    assert me_after.status_code == 401
    print("  -> Successfully logged out; /auth/me returns 401 Unauthorized.")

    print("\n=== ALL END-TO-END PROXY & PLATFORM TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_e2e_tests()
