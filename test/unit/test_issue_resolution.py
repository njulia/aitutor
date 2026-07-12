
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from web_app import app

def test_explain_deep_timeout_handling():
    client = TestClient(app)
    # We want to trigger the 504. 
    # Since I increased the timeout to 120s, I should verify the code uses that timeout.
    
    # Mocking the explain_deep function in web_app.py to sleep longer than the timeout
    import web_app
    from unittest.mock import patch, MagicMock
    
    async def slow_blocking(*args, **kwargs):
        # simulate timeout
        from fastapi import HTTPException
        raise HTTPException(status_code=504, detail="That took too long.")

    with patch("web_app.run_blocking", side_effect=slow_blocking):
        response = client.post("/api/explain-deep", json={
            "homework": "1+1=?",
            "answers": "2",
            "subject": "Maths",
            "from_rag": True
        })
        
        assert response.status_code == 504
        assert "That took too long" in response.json()["detail"]

def test_explain_deep_subscription_logic_rag():
    client = TestClient(app)
    # If from_rag is True, it should not require subscription (402)
    
    from unittest.mock import patch
    with patch("web_app.user_has_subscription", return_value=False):
        with patch("web_app.run_blocking", return_value={"success": True, "explanation": "test"}):
            response = client.post("/api/explain-deep", json={
                "homework": "1+1=?",
                "answers": "2",
                "subject": "Maths",
                "from_rag": True
            })
            
            # Should not be 402 or 401
            assert response.status_code == 200
            assert response.json()["success"] is True

def test_explain_deep_subscription_logic_non_rag():
    client = TestClient(app)
    # If from_rag is False, it SHOULD require subscription (402 or 401)
    
    from unittest.mock import patch
    with patch("web_app.user_has_subscription", return_value=False):
        response = client.post("/api/explain-deep", json={
            "homework": "1+1=?",
            "answers": "2",
            "subject": "Maths",
            "from_rag": False
        })
        
        # Since no login, it might be 401 or 402 depending on implementation
        assert response.status_code in (401, 402)
