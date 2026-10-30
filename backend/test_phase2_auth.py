"""
Test suite for Phase 2: Secure Authentication, Argon2id, JWT, and Protected Routes.
"""
import sys
import uuid
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api"

def run_phase2_tests():
    print("="*60)
    print("RUNNING PHASE 2 TESTS: Authentication & Protected Routes")
    print("="*60)

    test_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "SecurePassword123!"
    test_name = "Alex Johnson"

    session = requests.Session()

    # 1. Register
    reg_resp = session.post(f"{BASE_URL}/auth/register", json={
        "name": test_name,
        "email": test_email,
        "password": test_password,
    })
    assert reg_resp.status_code == 201, f"Expected 201, got {reg_resp.status_code}: {reg_resp.text}"
    user_data = reg_resp.json()
    assert user_data["email"] == test_email.lower()
    assert user_data["name"] == test_name
    assert "password_hash" not in user_data, "Password hash must never be returned in API response"
    assert "access_token" in session.cookies, "HttpOnly auth cookie should be set after registration"
    print("PASS: Registration successful and cookie received.")

    # 2. Duplicate registration rejection
    dup_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "name": "Different Name",
        "email": test_email.upper(),  # test case-insensitivity
        "password": "AnotherPassword123!",
    })
    assert dup_resp.status_code == 409, f"Expected 409 conflict, got {dup_resp.status_code}"
    print("PASS: Duplicate registration blocked with 409 Conflict.")

    # 3. Access /auth/me with cookie session
    me_resp = session.get(f"{BASE_URL}/auth/me")
    assert me_resp.status_code == 200, f"Expected 200, got {me_resp.status_code}: {me_resp.text}"
    assert me_resp.json()["email"] == test_email.lower()
    print("PASS: /auth/me verified successfully via HttpOnly cookie.")

    # 4. Logout
    logout_resp = session.post(f"{BASE_URL}/auth/logout")
    assert logout_resp.status_code == 200

    # 5. Access /auth/me after logout (should fail 401)
    unauth_resp = session.get(f"{BASE_URL}/auth/me")
    assert unauth_resp.status_code == 401, f"Expected 401 after logout, got {unauth_resp.status_code}"
    print("PASS: Logout cleared authentication; unauthenticated request returned 401.")

    # 6. Login with invalid password
    bad_login = requests.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": "WrongPassword123!",
    })
    assert bad_login.status_code == 401
    assert "Invalid email or password" in bad_login.json()["detail"]
    print("PASS: Bad login returned generic 401 error.")

    # 7. Login with valid password and get cookie
    new_session = requests.Session()
    login_resp = new_session.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": test_password,
    })
    assert login_resp.status_code == 200
    assert "access_token" in new_session.cookies
    token_val = new_session.cookies.get("access_token")

    # 8. Test Bearer Header authentication using standalone request
    bearer_resp = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token_val}"}
    )
    assert bearer_resp.status_code == 200
    assert bearer_resp.json()["email"] == test_email.lower()
    print("PASS: Authorization Bearer header successfully authenticated.")

    print("\n" + "="*60)
    print("ALL PHASE 2 TESTS PASSED SUCCESSFULLY!")
    print("="*60)

if __name__ == "__main__":
    run_phase2_tests()
