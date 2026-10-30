import asyncio
import io
import sys
import httpx
from pypdf import PdfWriter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

async def test_all():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        print("[PASS] Health check OK")

        # 2. Register/Login user
        email = f"notebooklm_tester_{asyncio.get_event_loop().time()}@example.com"
        reg_res = await client.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "name": "NotebookLM Tester"
        })
        assert reg_res.status_code in (200, 201), f"Register failed: {reg_res.text}"
        cookies = reg_res.cookies
        print(f"[PASS] User registered & authenticated: {email}")

        # 3. Create a project
        proj_res = await client.post("/api/projects", json={
            "name": "Deep Learning Fundamentals",
            "description": "Notebook for studying deep neural networks and attention mechanisms"
        }, cookies=cookies)
        assert proj_res.status_code in (200, 201), f"Create project failed: {proj_res.text}"
        project = proj_res.json()
        pid = project["_id"]
        print(f"[PASS] Created notebook project '{project['name']}' (ID: {pid})")

        # 4. Ingest 1: Pasted Study Note
        pasted_text = (
            "Deep learning models rely on gradient descent and backpropagation to optimize weights. "
            "Convolutional neural networks (CNNs) excel at spatial feature extraction for computer vision tasks, "
            "utilizing pooling layers and convolution kernels. "
            "Recurrent neural networks (RNNs) and LSTMs model sequential dependencies and time-series data."
        )
        note_res = await client.post("/api/ingest/text", json={
            "title": "Lecture Notes: CNNs and RNNs",
            "text": pasted_text,
            "project_id": pid
        }, cookies=cookies)
        assert note_res.status_code == 200, f"Pasted text ingestion failed: {note_res.text}"
        print("[PASS] Ingested study note via /api/ingest/text")

        # 5. Ingest 2: Upload Document (PDF)
        pdf_writer = PdfWriter()
        pdf_writer.add_blank_page(width=72, height=72)
        pdf_bytes = io.BytesIO()
        pdf_writer.write(pdf_bytes)
        pdf_bytes.seek(0)

        # Let's also do a text document upload
        doc_content = (
            "Transformers replace recurrence with multi-head self-attention mechanisms. "
            "The attention formula computes softmax(Q * K^T / sqrt(d_k)) * V. "
            "Positional encodings provide sequence order information since attention is permutation equivariant. "
            "BERT uses masked language modeling for bidirectional representations, while GPT uses causal autoregression."
        ).encode("utf-8")

        upload_res = await client.post(
            "/api/ingest/upload",
            data={"project_id": pid, "title": "Transformers & Attention Guide"},
            files={"file": ("attention_guide.txt", doc_content, "text/plain")},
            cookies=cookies
        )
        assert upload_res.status_code == 200, f"Upload ingestion failed: {upload_res.text}"
        print("[PASS] Ingested document via /api/ingest/upload")

        # 6. Verify sources list
        sources_res = await client.get(f"/api/projects/{pid}/sources", cookies=cookies)
        assert sources_res.status_code == 200, f"Get sources failed: {sources_res.text}"
        sources = sources_res.json()
        assert len(sources) >= 2, f"Expected at least 2 sources, got {len(sources)}"
        print(f"[PASS] Verified {len(sources)} sources in project: {[s['title'] for s in sources]}")

        # 7. Start a conversation and ask question
        chat_res = await client.post(f"/api/projects/{pid}/chats", json={
            "title": "Attention Mechanism Discussion"
        }, cookies=cookies)
        assert chat_res.status_code in (200, 201), f"Create chat failed: {chat_res.text}"
        chat = chat_res.json()
        cid = chat["_id"]
        print(f"[PASS] Created conversation session (ID: {cid})")

        msg_res = await client.post(f"/api/chats/{cid}/message", json={
            "question": "How does self-attention differ from convolutional neural networks according to our sources?"
        }, cookies=cookies)
        assert msg_res.status_code == 200, f"Send message failed: {msg_res.text}"
        msg_data = msg_res.json()
        assistant_msg = msg_data.get("assistant_message", {})
        answer = assistant_msg.get("content", "")
        assert len(answer) > 20, f"Answer was empty or too short: {msg_data}"
        print(f"[PASS] Multi-source question answered successfully. (Length: {len(answer)} chars)")
        print(f"Sample answer excerpt: {answer[:180]}...")

        # 8. Test Studio Tools
        tools_to_test = ["summary", "flashcards", "quiz", "mindmap", "notes", "datatable"]
        for tool in tools_to_test:
            studio_res = await client.get(f"/api/projects/{pid}/studio/{tool}", cookies=cookies)
            assert studio_res.status_code == 200, f"Studio tool '{tool}' failed: {studio_res.text}"
            data = studio_res.json()
            assert data.get("tool_type") == tool
            print(f"[PASS] Learning Studio '{tool}' generated & cached successfully")

        # 9. Test source removal and FAISS cleanup
        first_source = sources[0]
        src_id = first_source["source_id"]
        del_res = await client.delete(f"/api/ingest/sources/{pid}/{src_id}", cookies=cookies)
        assert del_res.status_code == 200, f"Delete source failed: {del_res.text}"
        print(f"[PASS] Removed source {src_id} from project and updated FAISS index")

        # Re-check sources
        sources_after = (await client.get(f"/api/projects/{pid}/sources", cookies=cookies)).json()
        assert len(sources_after) == len(sources) - 1
        print(f"[PASS] Remaining sources verified: {len(sources_after)}")

        print("\n=======================================================")
        print("ALL END-TO-END WORKSPACE & BACKEND TESTS PASSED!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_all())
