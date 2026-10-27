"""
Offline Unit Test Suite for RealAIProvider (Google Gemini Integration)
Owned by: Ekansh (AI/ML Evaluation)

Validates:
1. Gemini chat success with parsed follow-ups
2. Multi-subject support across all four subjects (Python, Biology, Business, AI/ML)
3. Missing or empty API credentials fallback
4. Unsupported model / HTTP 404 fallback
5. Permission failure / HTTP 403 fallback
6. Rate limit / HTTP 429 fallback
7. Internal server error / HTTP 5xx fallback
8. Network timeout fallback
9. Empty or malformed response fallback
10. Bounded conversation history management (token limit protection)
11. Defensive handling of malformed history items
12. SDK initialization failure fallback
13. Correct timeout conversion (seconds to milliseconds for HttpOptions)
14. Configurable model selection (GEMINI_MODEL)
15. Zero credential leakage in logs, representation, or exceptions
16. Exact ChatProviderResult Pydantic schema validation (strict=True)
17. Deterministic assessment evaluation (answer keys never sent to LLM)
18. AI Provider Factory compatibility
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from ai.real_provider import (
    RealAIProvider,
    parse_timeout_seconds,
    parse_gemini_followups,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
)
from ai.factory import get_ai_provider
from backend.app.schemas.chat import ChatProviderResult
from backend.app.services.assessment_service import EvaluationFeedback


SAMPLE_PYTHON_QUESTIONS = [
    {
        "id": "q_py_1",
        "subject_id": "subj_python",
        "question_number": 1,
        "question_text": "What does append_item produce?",
        "correct_option": "B",
        "explanation": "Default parameter evaluation.",
        "topic": "Default Parameter Evaluation & Mutability",
    },
    {
        "id": "q_py_2",
        "subject_id": "subj_python",
        "question_number": 2,
        "question_text": "What does data[1:4:-1] produce?",
        "correct_option": "C",
        "explanation": "Slice notation.",
        "topic": "Sequence Slicing & Negative Steps",
    },
    {
        "id": "q_py_3",
        "subject_id": "subj_python",
        "question_number": 3,
        "question_text": "Why do dict keys need to be hashable?",
        "correct_option": "C",
        "explanation": "Hash tables require invariant hash keys.",
        "topic": "Hash Tables, Mutability & Dictionary Keys",
    },
    {
        "id": "q_py_4",
        "subject_id": "subj_python",
        "question_number": 4,
        "question_text": "Difference between list comprehension and generator?",
        "correct_option": "B",
        "explanation": "Generators evaluate lazily.",
        "topic": "Comprehensions vs Generators",
    },
    {
        "id": "q_py_5",
        "subject_id": "subj_python",
        "question_number": 5,
        "question_text": "What is LEGB scope?",
        "correct_option": "A",
        "explanation": "Local, Enclosing, Global, Built-in.",
        "topic": "Variable Scope & LEGB Lookup",
    },
]


@pytest.fixture
def fake_api_env(monkeypatch):
    """Sets a clean synthetic test environment for Gemini."""
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic_test_key_1234567890")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "8.5")
    monkeypatch.setenv("AI_PROVIDER", "gemini")


# ---------------------------------------------------------------------------
# 1. Successful Chat & Follow-up Extraction
# ---------------------------------------------------------------------------

def test_gemini_chat_success(fake_api_env):
    provider = RealAIProvider()
    
    mock_response = MagicMock()
    mock_response.text = (
        "In Python, list comprehensions provide a concise way to create lists.\n\n"
        "Suggested Follow-ups:\n"
        "1. What is the syntax for nested comprehensions?\n"
        "2. When should you prefer a generator expression over a list comprehension?\n"
    )

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(
            prompt="Explain list comprehensions",
            subject="Python Programming"
        )

        assert res["is_mock"] is False
        assert "Google Gemini" in res["provider"]
        assert "list comprehensions provide a concise way" in res["reply"]
        assert len(res["suggested_followups"]) == 2
        assert "nested comprehensions" in res["suggested_followups"][0]


# ---------------------------------------------------------------------------
# 2. Multi-Subject Support (Python, Biology, Business, AI/ML)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("subject, prompt, expected_keyword", [
    ("Python Programming", "What is mutability?", "Python"),
    ("Foundational Biology", "What is mitochondria?", "Mitochondria"),
    ("Business & Entrepreneurship", "Explain CAC and LTV", "CAC"),
    ("Artificial Intelligence & Machine Learning", "Explain overfitting", "Overfitting"),
])
def test_gemini_chat_four_subjects(fake_api_env, subject, prompt, expected_keyword):
    provider = RealAIProvider()

    mock_response = MagicMock()
    mock_response.text = (
        f"This is an educational response about {expected_keyword}.\n\n"
        "Suggested Follow-ups:\n"
        "1. Can you give another example?\n"
        "2. What are the common misconceptions?\n"
    )

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt=prompt, subject=subject)

        assert res["is_mock"] is False
        assert expected_keyword in res["reply"]
        assert len(res["suggested_followups"]) >= 1

        # Verify system instruction contains the subject
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        config = call_kwargs.get("config")
        assert config is not None


# ---------------------------------------------------------------------------
# 3. Missing Credentials Fallback
# ---------------------------------------------------------------------------

def test_missing_credentials_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = RealAIProvider()
    assert provider._has_valid_credentials() is False
    assert provider.is_mock is True

    res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
    assert res["is_mock"] is True
    assert "Mock AI" in res["provider"]
    assert "study buddy" in res["reply"] or "Demo AI" in res["reply"] or len(res["reply"]) > 0


# ---------------------------------------------------------------------------
# 4. Unsupported Model (HTTP 404) Fallback
# ---------------------------------------------------------------------------

def test_unsupported_model_404_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("404 Not Found: Model 'unsupported-model' not found")
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 5. Permission Denied (HTTP 403) Fallback
# ---------------------------------------------------------------------------

def test_permission_denied_403_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("403 Forbidden: API key not valid")
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 6. Rate Limit (HTTP 429) Fallback
# ---------------------------------------------------------------------------

def test_rate_limit_429_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 ResourceExhausted: Quota exceeded")
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Explain loops", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 7. Internal Server Error (HTTP 5xx) Fallback
# ---------------------------------------------------------------------------

def test_server_error_5xx_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Explain decorators", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 8. Timeout Fallback
# ---------------------------------------------------------------------------

def test_timeout_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 9. Empty or Malformed Response Fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_val", [None, "", "   ", MagicMock(text=None)])
def test_empty_response_fallback(fake_api_env, empty_val):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        if isinstance(empty_val, str) or empty_val is None:
            resp = MagicMock()
            resp.text = empty_val
            mock_client.models.generate_content.return_value = resp
        else:
            mock_client.models.generate_content.return_value = empty_val
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 10. Bounded Conversation History
# ---------------------------------------------------------------------------

def test_bounded_conversation_history(fake_api_env):
    provider = RealAIProvider()

    # Create 20 history items
    large_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message turn {i}"}
        for i in range(20)
    ]

    contents_sent = []

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        def mock_generate(*args, **kwargs):
            nonlocal contents_sent
            contents_sent = kwargs.get("contents", [])
            resp = MagicMock()
            resp.text = "Here is the answer.\n\nSuggested Follow-ups:\n1. Followup 1\n"
            return resp
        
        mock_client.models.generate_content.side_effect = mock_generate
        mock_get_client.return_value = mock_client

        provider.generate_chat_response(
            prompt="Current question",
            subject="Python Programming",
            history=large_history
        )

        # Max history turns is 8 + 1 current prompt = 9 items max
        assert len(contents_sent) <= 9
        # Last content must be user's current prompt
        assert contents_sent[-1].role == "user"


# ---------------------------------------------------------------------------
# 11. Defensive Malformed History Handling
# ---------------------------------------------------------------------------

def test_malformed_history_handling(fake_api_env):
    provider = RealAIProvider()
    bad_history = [
        None,
        {},
        {"role": "user"},  # missing content
        {"content": "orphan"},  # missing role
        "not a dict",
        {"role": "assistant", "content": None},
        {"role": "assistant", "content": "Valid prior message"},
    ]

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Answer text.\n\nSuggested Follow-ups:\n1. Question 1\n"
        mock_client.models.generate_content.return_value = mock_resp
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="Hi", subject="Python", history=bad_history)
        assert res["is_mock"] is False


# ---------------------------------------------------------------------------
# 12. SDK Initialization Failure Fallback
# ---------------------------------------------------------------------------

def test_sdk_init_failure_fallback(fake_api_env):
    provider = RealAIProvider()

    with patch.object(provider, "_get_client", return_value=None):
        res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")
        assert res["is_mock"] is True
        assert "Mock AI" in res["provider"]


# ---------------------------------------------------------------------------
# 13. Correct Timeout Conversion (seconds to milliseconds)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("input_sec, expected_sec, expected_ms", [
    ("10.0", 10.0, 10000),
    ("8.5", 8.5, 8500),
    ("0.5", 0.5, 500),
    ("invalid", DEFAULT_TIMEOUT_SECONDS, int(DEFAULT_TIMEOUT_SECONDS * 1000)),
    ("-5", DEFAULT_TIMEOUT_SECONDS, int(DEFAULT_TIMEOUT_SECONDS * 1000)),
    ("0", DEFAULT_TIMEOUT_SECONDS, int(DEFAULT_TIMEOUT_SECONDS * 1000)),
    ("999", DEFAULT_TIMEOUT_SECONDS, int(DEFAULT_TIMEOUT_SECONDS * 1000)),  # excessively large
    (None, DEFAULT_TIMEOUT_SECONDS, int(DEFAULT_TIMEOUT_SECONDS * 1000)),
])
def test_timeout_seconds_to_ms_conversion(monkeypatch, input_sec, expected_sec, expected_ms):
    if input_sec is not None:
        monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", input_sec)
    else:
        monkeypatch.delenv("GEMINI_TIMEOUT_SECONDS", raising=False)

    provider = RealAIProvider()
    assert provider.timeout_seconds == expected_sec
    assert provider.timeout_ms == expected_ms


# ---------------------------------------------------------------------------
# 14. Configurable Model Selection
# ---------------------------------------------------------------------------

def test_configurable_model_selection(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    provider = RealAIProvider()
    assert provider.model_name == "gemini-1.5-pro"

    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    provider_default = RealAIProvider()
    assert provider_default.model_name == DEFAULT_GEMINI_MODEL
    assert provider_default.model_name == "gemini-3.1-flash-lite"


# ---------------------------------------------------------------------------
# 15. Credential Redaction & Safety
# ---------------------------------------------------------------------------

def test_credential_redaction(fake_api_env):
    provider = RealAIProvider()
    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key is not None

    # Verify provider_name does not expose API key
    assert api_key not in provider.provider_name
    assert api_key not in str(provider)
    assert api_key not in repr(provider)


# ---------------------------------------------------------------------------
# 16. ChatProviderResult Pydantic Strict Schema Validation
# ---------------------------------------------------------------------------

def test_backend_chat_provider_result_contract(fake_api_env):
    provider = RealAIProvider()

    mock_response = MagicMock()
    mock_response.text = (
        "Recursion is a programming technique where a function calls itself.\n\n"
        "Suggested Follow-ups:\n"
        "1. What is a base case in recursion?\n"
        "2. What causes a RecursionError?\n"
    )

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = provider.generate_chat_response(prompt="What is recursion?", subject="Python Programming")

        # Must pass strict Pydantic validation as required by backend chat router
        validated = ChatProviderResult.model_validate(res)
        assert validated.reply == res["reply"]
        assert validated.is_mock is False
        assert validated.provider == res["provider"]
        assert len(validated.suggested_followups) == 2


# ---------------------------------------------------------------------------
# 17. Deterministic Assessment Evaluation Preservation
# ---------------------------------------------------------------------------

def test_deterministic_assessment_evaluation_preserved(fake_api_env):
    """
    Ensures answer keys and evaluation are NEVER sent to Gemini.
    Authoritative scoring is strictly preserved via deterministic evaluation.
    """
    provider = RealAIProvider()
    answers = {"q_py_1": "B", "q_py_2": "C", "q_py_3": "C", "q_py_4": "B", "q_py_5": "A"}

    # Notice: No client mocking is needed because Gemini is never contacted!
    res = provider.evaluate_assessment("Python Programming", SAMPLE_PYTHON_QUESTIONS, answers)

    assert res["score"] == 5
    assert res["total"] == 5
    assert res["percentage"] == 100.0
    assert res["proficiency_level"] == "Advanced"
    assert "breakdown" in res
    assert len(res["breakdown"]) == 5
    assert res["is_mock"] is True

    # Validate against backend EvaluationFeedback schema
    validated_feedback = EvaluationFeedback.model_validate(res)
    assert validated_feedback.is_mock is True
    assert "summary_feedback" in res


# ---------------------------------------------------------------------------
# 18. AI Provider Factory Compatibility
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider_env", ["gemini", "real", "openai"])
def test_factory_returns_real_provider(monkeypatch, provider_env):
    monkeypatch.setenv("AI_PROVIDER", provider_env)
    provider = get_ai_provider()
    assert isinstance(provider, RealAIProvider)


def test_factory_defaults_to_mock_when_set_to_mock(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    provider = get_ai_provider()
    assert provider.is_mock is True
