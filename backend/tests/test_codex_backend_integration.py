"""
Comprehensive Integration Regression Test Suite
Testing Codex Backend Improvements within PragyaX's Dual-Engine Architecture:
1. Registration, Login, and Password Security
2. Chat stability: subject=null default, prompt deduplication, error masking, zero-orphan persistence
3. Server-owned assessment grading: trusted scoring, forged score prevention, provider 502 error handling
4. Saved assessment persistence, history, and cross-user isolation
5. Dashboard metrics derivation and typed attempt summaries
6. TimestampString serialization (ISO-8601 formatting, null preservation)
7. Unauthorized request protection
8. Daily challenge V1 functionality and duplicate rejection
"""

import os
import tempfile
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import init_db, close_db_pool, get_db
from backend.app.database.repository import Repository
from backend.app.main import app
from backend.app.routers import chat as chat_router, assessments as assessments_router

SAMPLE_ANSWERS = {"q_py_1": "B", "q_py_2": "C", "q_py_3": "C", "q_py_4": "B", "q_py_5": "A"}


@pytest.fixture(autouse=True)
def isolated_sqlite_env(monkeypatch):
    """Provisions a clean, disposable SQLite database in tempdir for each test."""
    temp_dir = tempfile.mkdtemp(prefix="pragya_codex_integ_")
    db_file = os.path.join(temp_dir, "test_integ.db")
    
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setenv("AI_PROVIDER", "mock")
    
    close_db_pool()
    init_db()
    
    yield
    
    close_db_pool()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass


@pytest.fixture
def auth_client():
    """Provides a TestClient with a registered and authenticated user."""
    with TestClient(app) as client:
        reg = client.post("/api/auth/register", json={
            "name": "Integration Learner",
            "email": "learner@pragyax.test",
            "password": "SecurePassword123!"
        })
        assert reg.status_code == 201
        body = reg.json()
        token = body["token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, headers, body["user"]


# ============================================================================
# 1. AUTHENTICATION & SESSION TESTS
# ============================================================================

def test_auth_registration_login_and_validation(auth_client):
    client, _, user = auth_client
    
    # 1. Profile me check
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'learner@pragyax.test', 'password': 'SecurePassword123!'}).json()['token']}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "learner@pragyax.test"

    # 2. Duplicate registration rejected
    dup = client.post("/api/auth/register", json={
        "name": "Duplicate Learner",
        "email": "learner@pragyax.test",
        "password": "Password123456"
    })
    assert dup.status_code == 400
    assert "already exists" in dup.json()["detail"]

    # 3. Bad credentials rejected
    bad_login = client.post("/api/auth/login", json={
        "email": "learner@pragyax.test",
        "password": "WrongPassword!"
    })
    assert bad_login.status_code == 401


def test_unauthorized_endpoints_protected():
    with TestClient(app) as unauthed:
        assert unauthed.get("/api/auth/me").status_code == 401
        assert unauthed.get("/api/subjects").status_code == 401
        assert unauthed.get("/api/chat/history").status_code == 401
        assert unauthed.get("/api/assessments/questions").status_code == 401
        assert unauthed.get("/api/dashboard").status_code == 401
        assert unauthed.get("/api/challenges/daily").status_code == 401


# ============================================================================
# 2. LEARNING CHAT STABILITY TESTS
# ============================================================================

@pytest.mark.parametrize("subject_input", [None, "Python Programming", "Custom Python Track"])
def test_chat_subject_null_handling_and_prompt_deduplication(auth_client, monkeypatch, subject_input):
    client, headers, user = auth_client
    recorded_calls = []

    def mock_generate(**kwargs):
        recorded_calls.append(kwargs)
        return {
            "reply": "Educational response on Python memory model",
            "suggested_followups": ["Tell me about mutable vs immutable"]
        }

    monkeypatch.setattr(chat_router, "get_ai_provider", lambda: SimpleNamespace(
        generate_chat_response=mock_generate,
        provider_name="MockAIProvider",
        is_mock=True
    ))

    # Send first message
    r1 = client.post("/api/chat/message", headers=headers, json={
        "message": "First query about Python",
        "subject": subject_input
    })
    assert r1.status_code == 200
    expected_subject = subject_input if subject_input is not None else "Python Programming"
    assert r1.json()["subject"] == expected_subject

    # Send second message
    r2 = client.post("/api/chat/message", headers=headers, json={
        "message": "Second query about tuples",
        "subject": subject_input
    })
    assert r2.status_code == 200

    # Verification: Call 1 had empty history
    assert recorded_calls[0]["history"] == []
    assert recorded_calls[0]["prompt"] == "First query about Python"

    # Call 2 history contained only first conversation turn; current prompt was NOT duplicated
    assert len(recorded_calls[1]["history"]) == 2
    history_contents = [h["content"] for h in recorded_calls[1]["history"]]
    assert "First query about Python" in history_contents
    assert "Second query about tuples" not in history_contents
    assert recorded_calls[1]["prompt"] == "Second query about tuples"


def test_chat_provider_exception_returns_502_and_leaves_no_orphan(auth_client, monkeypatch, caplog):
    client, headers, user = auth_client

    def fail_with_secret(**kwargs):
        raise RuntimeError("CRITICAL_API_SECRET_TOKEN_12345: timeout connecting to upstream provider")

    monkeypatch.setattr(chat_router, "get_ai_provider", lambda: SimpleNamespace(
        generate_chat_response=fail_with_secret,
        provider_name="MockAIProvider",
        is_mock=True
    ))

    res = client.post("/api/chat/message", headers=headers, json={
        "message": "Tell me about generators",
        "subject": "Python Programming"
    })
    
    # Must return controlled 502 Bad Gateway
    assert res.status_code == 502
    assert res.json()["detail"] == "Learning provider is temporarily unavailable."
    
    # Secrets must NEVER leak into response text or logged output
    assert "CRITICAL_API_SECRET" not in res.text
    assert "CRITICAL_API_SECRET" not in caplog.text

    # No orphan user prompt should be persisted in DB
    history = Repository.get_chat_history(user["id"])
    assert len(history) == 0


@pytest.mark.parametrize("bad_reply", [
    None,
    {},
    {"reply": ""},
    {"reply": None},
    {"reply": "Valid", "suggested_followups": [123]}  # invalid followup type
])
def test_chat_malformed_provider_output_returns_502_and_no_persistence(auth_client, monkeypatch, bad_reply):
    client, headers, user = auth_client

    monkeypatch.setattr(chat_router, "get_ai_provider", lambda: SimpleNamespace(
        generate_chat_response=lambda **kw: bad_reply,
        provider_name="MockAIProvider",
        is_mock=True
    ))

    res = client.post("/api/chat/message", headers=headers, json={"message": "Explain dicts"})
    assert res.status_code == 502
    assert len(Repository.get_chat_history(user["id"])) == 0


# ============================================================================
# 3. SERVER-OWNED ASSESSMENT GRADING & INTEGRITY TESTS
# ============================================================================

def test_assessment_questions_hide_answer_keys(auth_client):
    client, headers, _ = auth_client
    res = client.get("/api/assessments/questions?subject_id=subj_python", headers=headers)
    assert res.status_code == 200
    questions = res.json()
    assert len(questions) == 5
    for q in questions:
        assert "option_a" in q
        assert "option_b" in q
        assert "option_c" in q
        assert "option_d" in q
        assert "correct_option" not in q
        assert "explanation" not in q


def test_assessment_server_grading_cannot_be_tampered_by_provider(auth_client, monkeypatch):
    """
    Verify that even if an AI provider attempts to return a manipulated score (e.g. 5/5),
    the server-side assessment service strictly calculates score from reference DB answer keys.
    """
    client, headers, user = auth_client

    def adversarial_provider(**kwargs):
        # Adversarial provider claims score is 5 even though user only got 4 right
        return {
            "score": 5,
            "total": 5,
            "percentage": 100.0,
            "proficiency_level": "Advanced",
            "summary_feedback": "Provider fabricated perfect score",
            "recommended_topics": ["Advanced Concurrency"],
            "is_mock": True,
            "provider": "AdversarialAI"
        }

    monkeypatch.setattr(assessments_router, "get_ai_provider", lambda: SimpleNamespace(
        evaluate_assessment=adversarial_provider,
        provider_name="AdversarialAI",
        is_mock=True
    ))

    # Submit 4 correct answers (q1: B, q2: C, q3: A [WRONG], q4: B, q5: A)
    res = client.post("/api/assessments/submit", headers=headers, json={
        "subject_id": "subj_python",
        "answers": {
            "q_py_1": "B",
            "q_py_2": "C",
            "q_py_3": "A",  # Wrong! Correct is C
            "q_py_4": "B",
            "q_py_5": "A"
        }
    })
    assert res.status_code == 200
    data = res.json()
    
    # Server strictly overrides provider score
    assert data["score"] == 4
    assert data["total"] == 5
    assert data["percentage"] == 80.0
    assert data["proficiency_level"] == "Intermediate"
    assert data["breakdown"][2]["is_correct"] is False


def test_assessment_provider_failure_returns_502_and_no_attempt_saved(auth_client, monkeypatch):
    client, headers, user = auth_client

    def fail_eval(**kwargs):
        raise TimeoutError("Upstream model timeout")

    monkeypatch.setattr(assessments_router, "get_ai_provider", lambda: SimpleNamespace(
        evaluate_assessment=fail_eval,
        provider_name="MockAIProvider",
        is_mock=True
    ))

    res = client.post("/api/assessments/submit", headers=headers, json={
        "subject_id": "subj_python",
        "answers": SAMPLE_ANSWERS
    })
    assert res.status_code == 502
    assert res.json()["detail"] == "Assessment provider is temporarily unavailable."

    # No half-completed attempt should be persisted
    history = Repository.get_user_assessment_attempts(user["id"])
    assert len(history) == 0


# ============================================================================
# 4. PERSISTENCE, HISTORY, AND CROSS-USER ISOLATION
# ============================================================================

def test_assessment_persistence_and_user_isolation(auth_client):
    client, headers1, user1 = auth_client

    # 1. User 1 submits assessment
    sub = client.post("/api/assessments/submit", headers=headers1, json={
        "subject_id": "subj_python",
        "answers": SAMPLE_ANSWERS
    })
    assert sub.status_code == 200
    attempt1_id = sub.json()["id"]

    # 2. User 1 can retrieve their own attempt
    get_res = client.get(f"/api/assessments/{attempt1_id}", headers=headers1)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == attempt1_id

    # 3. Register User 2
    reg2 = client.post("/api/auth/register", json={
        "name": "Second Student",
        "email": "student2@pragyax.test",
        "password": "Password123!"
    })
    headers2 = {"Authorization": f"Bearer {reg2.json()['token']}"}

    # 4. User 2 cannot access User 1's attempt (must return 404)
    iso_res = client.get(f"/api/assessments/{attempt1_id}", headers=headers2)
    assert iso_res.status_code == 404


# ============================================================================
# 5. DASHBOARD REAL METRICS & TYPING TESTS
# ============================================================================

def test_dashboard_metrics_and_attempt_summaries(auth_client):
    client, headers, user = auth_client

    # Before assessment: completed count is 0
    d1 = client.get("/api/dashboard", headers=headers).json()
    assert d1["metrics"]["total_assessments_completed"] == 0
    assert d1["metrics"]["latest_score"] is None
    assert d1["recent_attempts"] == []

    # Complete an assessment
    client.post("/api/assessments/submit", headers=headers, json={
        "subject_id": "subj_python",
        "answers": SAMPLE_ANSWERS
    })

    # After assessment: metrics reflect real DB records
    d2 = client.get("/api/dashboard", headers=headers).json()
    assert d2["metrics"]["total_assessments_completed"] == 1
    assert d2["metrics"]["latest_score"] == 5
    assert d2["metrics"]["average_percentage"] == 100.0
    assert len(d2["recent_attempts"]) == 1
    
    # Check typed attempt fields
    recent = d2["recent_attempts"][0]
    assert recent["score"] == 5
    assert recent["total"] == 5
    assert recent["subject_id"] == "subj_python"
    assert "user_id" in recent
    assert "summary_feedback" in recent
    assert isinstance(recent["recommended_topics"], list)


# ============================================================================
# 6. TIMESTAMP SERIALIZATION TESTS
# ============================================================================

def test_timestamp_serialization_in_models():
    from datetime import datetime
    from backend.app.schemas.timestamps import serialize_timestamp
    
    # 1. Native datetime converts to ISO string
    dt = datetime(2026, 10, 27, 12, 30, 45)
    assert serialize_timestamp(dt) == "2026-10-27T12:30:45"

    # 2. Existing string passes through untouched
    assert serialize_timestamp("2026-10-27 12:30:45") == "2026-10-27 12:30:45"

    # 3. None remains None
    assert serialize_timestamp(None) is None


# ============================================================================
# 7. V1 DAILY CHALLENGE BEHAVIOR PRESERVED
# ============================================================================

def test_daily_challenge_points_and_single_award(auth_client):
    client, headers, user = auth_client

    # Get challenge
    chal_res = client.get("/api/challenges/daily", headers=headers)
    assert chal_res.status_code == 200
    chal = chal_res.json()
    assert chal["id"] == "chal_today_py"
    assert chal["has_completed"] is False
    assert chal["correct_option"] is None  # hidden before completion

    # Submit correct answer ('B')
    sub_res = client.post("/api/challenges/submit", headers=headers, json={
        "challenge_id": "chal_today_py",
        "selected_option": "B"
    })
    assert sub_res.status_code == 200
    assert sub_res.json()["is_correct"] is True
    assert sub_res.json()["points_awarded"] == 50

    # Duplicate submission rejected
    dup_res = client.post("/api/challenges/submit", headers=headers, json={
        "challenge_id": "chal_today_py",
        "selected_option": "B"
    })
    assert dup_res.status_code == 400
    assert "already completed" in dup_res.json()["detail"]
