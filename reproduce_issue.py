
import asyncio
import json
import os
import sys
from fastapi.testclient import TestClient

# Ensure we can import web_app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from web_app import app
from src.progress_db import create_user, verify_user_credentials
from src.webapp.account_store import ensure_account, ensure_default_student

def test_access_denied_repro():
    client = TestClient(app)
    
    # 1. Setup a test user
    email = "test_user_progress@example.com"
    password = "password123"
    
    # Clean up / Ensure user exists
    from src.progress_db import auth_users, _engine
    from sqlalchemy import delete
    with _engine.begin() as conn:
        conn.execute(delete(auth_users).where(auth_users.c.username == email))
    
    create_user(email, password)
    
    # 2. Login to get a session cookie
    login_resp = client.post("/api/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    assert login_resp.json()["success"] is True
    
    # 3. Simulate the frontend behavior: using email as student_id
    # The frontend does: localStorage.setItem('student_id', data.username || email)
    student_id_from_frontend = email 
    
    # 4. Call progress API with the email as student_id
    progress_resp = client.get(f"/api/progress/{student_id_from_frontend}")
    
    print(f"Status Code: {progress_resp.status_code}")
    print(f"Response: {progress_resp.json()}")
    
    # This should fail with 403 "Access denied to this learner's progress" 
    # if our hypothesis is correct.
    if progress_resp.status_code == 403 and "Access denied" in progress_resp.json()["error"]:
        print("SUCCESS: Reproduced the 403 Access Denied error!")
    else:
        print("FAILED: Did not reproduce the expected error.")

if __name__ == "__main__":
    test_access_denied_repro()
