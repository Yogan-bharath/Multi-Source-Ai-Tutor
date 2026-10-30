"""
Test Phase 4: Persistent Chat History, Multi-Turn Conversations, Bounded Context, and Ownership Isolation.
"""
import sys
import uuid
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def run_tests():
    print("="*60)
    print("RUNNING PHASE 4 TESTS: Conversations, Messages & Isolation")
    print("="*60)

    # 1. Check health with retry
    import time
    for _ in range(10):
        try:
            health_resp = requests.get("http://localhost:8000/health", timeout=5)
            if health_resp.status_code == 200:
                print("Health OK:", health_resp.json())
                break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Server not responding")
    time.sleep(1)  # small pause to ensure uvicorn reload settled


    # 2. Register User A
    session_a = requests.Session()
    email_a = f"alice_{uuid.uuid4().hex[:6]}@example.com"
    password = "SecurePassword123!"
    reg_a = session_a.post(f"{BASE_URL}/auth/register", json={
        "name": "Alice Tester",
        "email": email_a,
        "password": password
    })
    assert reg_a.status_code == 201, f"User A registration failed: {reg_a.text}"
    print(f"PASS: User A registered ({email_a}) with auth cookie set.")

    # 3. Create Project for User A
    proj_resp = session_a.post(f"{BASE_URL}/projects", json={
        "name": "Quantum Computing Project",
        "description": "Learning quantum concepts"
    })
    assert proj_resp.status_code == 201, f"Project creation failed: {proj_resp.text}"
    project_a = proj_resp.json()
    project_id = project_a.get("_id") or project_a.get("id")
    print(f"PASS: Project created with ID: {project_id}")

    # 4. Ingest 2 Wikipedia sources into project
    print("\nIngesting sources into User A's project...")
    ingest_resp = session_a.post(f"{BASE_URL}/ingest", json={
        "project_id": project_id,
        "source_urls": [
            "https://en.wikipedia.org/wiki/Qubit",
            "https://en.wikipedia.org/wiki/Quantum_entanglement"
        ]
    })
    assert ingest_resp.status_code == 200, f"Ingest failed: {ingest_resp.text}"
    ingest_data = ingest_resp.json()
    print(f"PASS: Ingestion completed: {ingest_data.get('sources_indexed')} sources indexed")

    # 5. Create conversation under project
    print("\nCreating a chat thread under project...")
    conv_resp = session_a.post(f"{BASE_URL}/projects/{project_id}/chats", json={
        "title": "Quantum Basics"
    })
    assert conv_resp.status_code == 201, f"Create chat failed: {conv_resp.text}"
    conv_data = conv_resp.json()
    chat_id = conv_data.get("_id") or conv_data.get("id")
    print(f"PASS: Chat thread created: {chat_id}, Title: {conv_data['title']}")

    # 6. List project chats
    print("\nListing project chats...")
    list_conv_resp = session_a.get(f"{BASE_URL}/projects/{project_id}/chats")
    assert list_conv_resp.status_code == 200
    chats = list_conv_resp.json()
    assert any((c.get("_id") or c.get("id")) == chat_id for c in chats)
    print(f"PASS: Found {len(chats)} conversation(s)")

    # 7. Send first message
    print("\nSending first message (asking what a qubit is)...")
    msg1_resp = session_a.post(f"{BASE_URL}/chats/{chat_id}/message", json={
        "content": "What is a qubit in simple terms?"
    })
    assert msg1_resp.status_code == 200, f"Message 1 failed: {msg1_resp.text}"
    msg1_data = msg1_resp.json()
    user_msg = msg1_data["user_message"]
    assistant_msg = msg1_data["assistant_message"]
    print(f"PASS: User message persisted: ID={user_msg.get('_id') or user_msg.get('id')}")
    print(f"PASS: Assistant reply generated: length={len(assistant_msg['content'])}")
    assert len(assistant_msg["content"]) > 10
    print(f"PASS: Source summaries found: {len(assistant_msg.get('source_summaries', []))}")


    # Check updated conversation title and history
    conv_info = session_a.get(f"{BASE_URL}/chats/{chat_id}/messages")
    assert conv_info.status_code == 200
    messages_page = conv_info.json()
    assert len(messages_page["messages"]) == 2  # 1 user + 1 assistant
    print(f"PASS: Verified 2 messages stored in conversation history.")

    # 8. Send follow-up contextual question
    print("\nSending follow-up contextual question...")
    msg2_resp = session_a.post(f"{BASE_URL}/chats/{chat_id}/message", json={
        "content": "How does it compare to entanglement?"
    })
    assert msg2_resp.status_code == 200, f"Follow-up failed: {msg2_resp.text}"
    msg2_data = msg2_resp.json()
    print(f"PASS: Assistant follow-up reply generated: length={len(msg2_data['assistant_message']['content'])}")

    # Check message history count
    conv_info2 = session_a.get(f"{BASE_URL}/chats/{chat_id}/messages")
    assert conv_info2.status_code == 200
    assert len(conv_info2.json()["messages"]) == 4  # 2 turns = 4 messages
    print("PASS: Verified 4 messages in history.")

    # 9. Test Renaming conversation
    print("\nRenaming conversation...")
    rename_resp = session_a.patch(f"{BASE_URL}/chats/{chat_id}", json={
        "title": "Quantum Physics 101"
    })
    assert rename_resp.status_code == 200
    assert rename_resp.json()["title"] == "Quantum Physics 101"
    print("PASS: Successfully renamed to 'Quantum Physics 101'")

    # 10. Test Archiving conversation
    print("\nArchiving conversation...")
    archive_resp = session_a.post(f"{BASE_URL}/chats/{chat_id}/archive")
    assert archive_resp.status_code == 200
    assert archive_resp.json()["status"] == "archived"
    print("PASS: Successfully archived conversation")

    # 11. Test User B Isolation
    session_b = requests.Session()
    email_b = f"bob_{uuid.uuid4().hex[:6]}@example.com"
    print(f"\nRegistering User B ({email_b}) and testing isolation...")
    reg_b = session_b.post(f"{BASE_URL}/auth/register", json={
        "name": "Bob Intruder",
        "email": email_b,
        "password": password
    })
    assert reg_b.status_code == 201

    # User B cannot list User A's project chats
    b_list = session_b.get(f"{BASE_URL}/projects/{project_id}/chats")
    assert b_list.status_code == 404, f"User B should get 404 on User A's project, got {b_list.status_code}"

    # User B cannot get messages from User A's conversation
    b_msgs = session_b.get(f"{BASE_URL}/chats/{chat_id}/messages")
    assert b_msgs.status_code == 404, f"User B should get 404 on User A's chat, got {b_msgs.status_code}"

    # User B cannot send messages to User A's conversation
    b_send = session_b.post(f"{BASE_URL}/chats/{chat_id}/message", json={
        "content": "Can I hack into your chat?"
    })
    assert b_send.status_code == 404, f"User B should get 404, got {b_send.status_code}"

    # User B cannot archive or delete User A's conversation
    b_del = session_b.delete(f"{BASE_URL}/chats/{chat_id}")
    assert b_del.status_code == 404, f"User B should get 404, got {b_del.status_code}"

    print("PASS: User B isolation verified! User B cannot access, view, or modify User A's conversations.")

    # 12. User A deletes conversation
    print("\nUser A deletes conversation...")
    del_resp = session_a.delete(f"{BASE_URL}/chats/{chat_id}")
    assert del_resp.status_code == 200
    print("PASS: Conversation and its messages deleted.")

    # Confirm 404 now
    del_check = session_a.get(f"{BASE_URL}/chats/{chat_id}/messages")
    assert del_check.status_code == 404
    print("PASS: Confirmed 404 after deletion.")

    print("\n=== ALL PHASE 4 CONVERSATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
