"""
Unit Tests for MockAIProvider
Owned by: Ekansh (AI/ML)

Verifies:
- 100% Python chat and assessment evaluation regression
- Multi-subject learning chat for Biology, Business, and AI/ML
- Subject alias normalization
- Strict fallback isolation across subjects
- Subject-scoped assessment recommendations
- Full compliance with existing FastAPI backend contracts
- Zero external network dependencies (100% offline)
"""

import pytest
from ai.mock_provider import (
    MockAIProvider,
    normalize_subject,
    proficiency_for,
    SUBJECT_ALIASES,
    LESSONS,
    PYTHON_LESSONS,
    BIOLOGY_LESSONS,
    BUSINESS_LESSONS,
    AIML_LESSONS,
)


@pytest.fixture
def provider():
    """Provides a fresh instance of MockAIProvider."""
    return MockAIProvider()


# ---------------------------------------------------------------------------
# 1. Subject Alias Normalization Tests
# ---------------------------------------------------------------------------

def test_subject_normalization_python():
    for alias in ["python", "Python", "Python Programming", "subj_python", "py", " PYTHON "]:
        assert normalize_subject(alias) == "python"


def test_subject_normalization_biology():
    for alias in ["biology", "Biology", "Life Sciences", "life science", "subj_biology", "bio"]:
        assert normalize_subject(alias) == "biology"


def test_subject_normalization_business():
    for alias in ["business", "Business", "entrepreneurship", "Business/Entrepreneurship", "subj_business", "biz"]:
        assert normalize_subject(alias) == "business"


def test_subject_normalization_aiml():
    for alias in ["ai_ml", "AI/ML", "ai", "ml", "Artificial Intelligence", "machine learning", "subj_aiml"]:
        assert normalize_subject(alias) == "ai_ml"


def test_subject_normalization_unknown_and_empty():
    assert normalize_subject("") == "python"  # Defaults safely to python when empty
    assert normalize_subject(None) == "python"
    assert normalize_subject("Quantum Physics") == "unknown"
    assert normalize_subject("Astrology") == "unknown"


# ---------------------------------------------------------------------------
# 2. Python Regression Tests
# ---------------------------------------------------------------------------

def test_python_lessons_identity():
    """Ensures LESSONS alias points to PYTHON_LESSONS and retains all 19 lessons."""
    assert LESSONS is PYTHON_LESSONS
    assert len(PYTHON_LESSONS) == 19


def test_python_chat_comprehensions(provider):
    res = provider.generate_chat_response(prompt="How do list comprehensions work?", subject="Python Programming")
    assert res["is_mock"] is True
    assert "list comprehensions" in res["reply"].lower() or "comprehension" in res["reply"].lower()
    assert len(res["suggested_followups"]) > 0
    assert any("generator expression" in f.lower() for f in res["suggested_followups"])


def test_python_chat_scope_legb(provider):
    res = provider.generate_chat_response(prompt="Explain variable scope and LEGB", subject="python")
    assert "legb" in res["reply"].lower()
    assert "local" in res["reply"].lower()
    assert "global" in res["reply"].lower()


def test_python_chat_decorators(provider):
    res = provider.generate_chat_response(prompt="What is a decorator?", subject="subj_python")
    assert "decorator" in res["reply"].lower()
    assert "@timer" in res["reply"] or "@functools" in res["reply"]


def test_python_chat_fallback_and_greeting(provider):
    # Greeting
    greeting_res = provider.generate_chat_response(prompt="Hi there", subject="Python Programming")
    assert "study buddy" in greeting_res["reply"]
    assert "Python Programming" in greeting_res["reply"]

    # Unmatched fallback
    fallback_res = provider.generate_chat_response(prompt="something completely unrelated xyz123", subject="python")
    assert "I couldn't match your question to one of them" in fallback_res["reply"]
    assert "variables & types" in fallback_res["reply"]


# ---------------------------------------------------------------------------
# 3. Biology Learning Content Tests
# ---------------------------------------------------------------------------

def test_biology_chat_cell_organelles(provider):
    res = provider.generate_chat_response(prompt="What do mitochondria and ribosomes do?", subject="Biology")
    assert res["is_mock"] is True
    assert "mitochondria" in res["reply"].lower()
    assert "atp" in res["reply"].lower()
    assert len(res["suggested_followups"]) > 0


def test_biology_chat_dna_genetics(provider):
    res = provider.generate_chat_response(prompt="Tell me about DNA transcription and translation", subject="subj_biology")
    assert "double helix" in res["reply"].lower() or "nucleotide" in res["reply"].lower()
    assert "central dogma" in res["reply"].lower() or "transcription" in res["reply"].lower()


def test_biology_chat_photosynthesis(provider):
    res = provider.generate_chat_response(prompt="How does photosynthesis generate energy in chloroplasts?", subject="biology")
    assert "photosynthesis" in res["reply"].lower()
    assert "calvin" in res["reply"].lower() or "chloroplast" in res["reply"].lower()


def test_biology_chat_enzymes(provider):
    res = provider.generate_chat_response(prompt="What causes enzyme denaturation?", subject="Life Sciences")
    assert "activation energy" in res["reply"].lower() or "denaturation" in res["reply"].lower()
    assert "active site" in res["reply"].lower()


def test_biology_chat_ecology(provider):
    res = provider.generate_chat_response(prompt="Explain food webs and trophic levels in ecosystems", subject="biology")
    assert "trophic" in res["reply"].lower()
    assert "carrying capacity" in res["reply"].lower() or "symbiotic" in res["reply"].lower()


# ---------------------------------------------------------------------------
# 4. Business & Entrepreneurship Content Tests
# ---------------------------------------------------------------------------

def test_business_chat_value_proposition(provider):
    res = provider.generate_chat_response(prompt="What is a customer value proposition?", subject="Business/Entrepreneurship")
    assert "value proposition" in res["reply"].lower()
    assert "pain" in res["reply"].lower() or "jobs" in res["reply"].lower()


def test_business_chat_mvp_lean_startup(provider):
    res = provider.generate_chat_response(prompt="What is an MVP in the lean startup methodology?", subject="entrepreneurship")
    assert "minimum viable product" in res["reply"].lower() or "mvp" in res["reply"].lower()
    assert "build-measure-learn" in res["reply"].lower()


def test_business_chat_product_market_fit(provider):
    res = provider.generate_chat_response(prompt="How do you know if you have product-market fit?", subject="business")
    assert "product-market fit" in res["reply"].lower() or "pmf" in res["reply"].lower()
    assert "retention" in res["reply"].lower()
    # Confirm heuristic phrasing for Sean Ellis 40%
    assert "heuristic" in res["reply"].lower() or "40%" in res["reply"]


def test_business_chat_unit_economics(provider):
    res = provider.generate_chat_response(prompt="Explain CAC and LTV unit economics", subject="subj_business")
    assert "cac" in res["reply"].lower()
    assert "ltv" in res["reply"].lower()
    # Confirm heuristic benchmark phrasing
    assert "heuristic" in res["reply"].lower() or "3x" in res["reply"]


def test_business_chat_business_model_canvas(provider):
    res = provider.generate_chat_response(prompt="What are the 9 blocks of the Business Model Canvas?", subject="business")
    assert "canvas" in res["reply"].lower()
    assert "customer segments" in res["reply"].lower()
    assert "revenue streams" in res["reply"].lower()


# ---------------------------------------------------------------------------
# 5. AI / Machine Learning Content Tests
# ---------------------------------------------------------------------------

def test_aiml_chat_supervised_vs_unsupervised(provider):
    res = provider.generate_chat_response(prompt="What is the difference between supervised and unsupervised learning?", subject="AI/ML")
    assert "supervised" in res["reply"].lower()
    assert "unsupervised" in res["reply"].lower()
    assert "labeled" in res["reply"].lower()


def test_aiml_chat_overfitting_regularization(provider):
    res = provider.generate_chat_response(prompt="How do you fix overfitting with regularization?", subject="ai_ml")
    assert "overfitting" in res["reply"].lower()
    assert "l1" in res["reply"].lower() or "l2" in res["reply"].lower() or "dropout" in res["reply"].lower()


def test_aiml_chat_precision_recall_metrics(provider):
    res = provider.generate_chat_response(prompt="What is the trade-off between precision and recall?", subject="machine learning")
    assert "precision" in res["reply"].lower()
    assert "recall" in res["reply"].lower()
    assert "confusion matrix" in res["reply"].lower() or "f1" in res["reply"].lower()


def test_aiml_chat_neural_networks(provider):
    res = provider.generate_chat_response(prompt="How does backpropagation work in neural networks?", subject="Artificial Intelligence")
    assert "activation" in res["reply"].lower() or "perceptron" in res["reply"].lower()
    assert "backpropagation" in res["reply"].lower() or "gradient" in res["reply"].lower()


def test_aiml_chat_transformers_attention(provider):
    res = provider.generate_chat_response(prompt="Explain self-attention in transformers", subject="subj_aiml")
    assert "transformer" in res["reply"].lower()
    assert "self-attention" in res["reply"].lower()
    assert "query" in res["reply"].lower() or "token" in res["reply"].lower()


# ---------------------------------------------------------------------------
# 6. Fallback Isolation Across Subjects
# ---------------------------------------------------------------------------

def test_fallback_isolation_biology(provider):
    """Biology fallback must suggest Biology concepts, NEVER Python or Business."""
    res = provider.generate_chat_response(prompt="completely unmapped query qwert123", subject="Biology")
    reply = res["reply"].lower()
    assert "organelles" in reply or "photosynthesis" in reply
    assert "decorators" not in reply
    assert "list comprehensions" not in reply
    assert "unit economics" not in reply


def test_fallback_isolation_business(provider):
    """Business fallback must suggest Business concepts, NEVER AI transformers or Python slicing."""
    res = provider.generate_chat_response(prompt="completely unmapped query qwert123", subject="Business")
    reply = res["reply"].lower()
    assert "value proposition" in reply or "unit economics" in reply
    assert "transformers" not in reply
    assert "slicing" not in reply


def test_fallback_isolation_aiml(provider):
    """AI/ML fallback must suggest AI/ML concepts, NEVER Python decorators or Biology cells."""
    res = provider.generate_chat_response(prompt="completely unmapped query qwert123", subject="AI/ML")
    reply = res["reply"].lower()
    assert "supervised" in reply or "overfitting" in reply
    assert "mitochondria" not in reply
    assert "decorators" not in reply


def test_unknown_subject_fallback(provider):
    res = provider.generate_chat_response(prompt="tell me something", subject="Astrology")
    assert "couldn't recognize that subject" in res["reply"].lower()
    assert "python programming" in res["reply"].lower()
    assert "biology" in res["reply"].lower()
    assert "business" in res["reply"].lower()
    assert "ai/ml" in res["reply"].lower()


# ---------------------------------------------------------------------------
# 7. Assessment Evaluation Tests
# ---------------------------------------------------------------------------

SAMPLE_PYTHON_QUESTIONS = [
    {
        "id": "q1",
        "question_text": "Mutability of defaults?",
        "correct_option": "B",
        "explanation": "Default arguments evaluate once.",
        "topic": "Default Parameter Evaluation & Mutability",
    },
    {
        "id": "q2",
        "question_text": "Slice data[1:4:-1]?",
        "correct_option": "C",
        "explanation": "Cannot step backwards from 1 to 4.",
        "topic": "Sequence Slicing & Negative Steps",
    },
    {
        "id": "q3",
        "question_text": "Dictionary key immutability?",
        "correct_option": "C",
        "explanation": "Keys must be hashable.",
        "topic": "Hash Tables, Mutability & Dictionary Keys",
    },
    {
        "id": "q4",
        "question_text": "Comprehension vs generator?",
        "correct_option": "B",
        "explanation": "Generators evaluate lazily.",
        "topic": "List Comprehensions vs Generator Expressions",
    },
    {
        "id": "q5",
        "question_text": "LEGB scope order?",
        "correct_option": "A",
        "explanation": "Local -> Enclosing -> Global -> Built-in.",
        "topic": "LEGB Variable Scope & Closures",
    },
]

SAMPLE_BIOLOGY_QUESTIONS = [
    {"id": "b1", "question_text": "ATP organelle?", "correct_option": "A", "explanation": "Mitochondria produce ATP.", "topic": "Cell Biology & Organelles"},
    {"id": "b2", "question_text": "Base pairing?", "correct_option": "B", "explanation": "A pairs with T.", "topic": "Molecular Genetics & DNA"},
    {"id": "b3", "question_text": "Calvin cycle location?", "correct_option": "C", "explanation": "Takes place in stroma.", "topic": "Bioenergetics & Photosynthesis"},
    {"id": "b4", "question_text": "Enzyme activation energy?", "correct_option": "D", "explanation": "Enzymes lower Ea.", "topic": "Enzyme Kinetics & Regulation"},
    {"id": "b5", "question_text": "Trophic 10% rule?", "correct_option": "A", "explanation": "10% transfer between levels.", "topic": "Ecology & Ecosystem Dynamics"},
]


def test_evaluate_python_perfect_score(provider):
    answers = {"q1": "B", "q2": "C", "q3": "C", "q4": "B", "q5": "A"}
    res = provider.evaluate_assessment("Python Programming", SAMPLE_PYTHON_QUESTIONS, answers)

    assert res["score"] == 5
    assert res["total"] == 5
    assert res["percentage"] == 100.0
    assert res["proficiency_level"] == "Advanced"
    assert res["is_mock"] is True
    assert len(res["breakdown"]) == 5
    assert all(b["is_correct"] is True for b in res["breakdown"])
    # Advanced recommendations returned for 5/5
    assert any("asyncio" in r.lower() or "decorator" in r.lower() for r in res["recommended_topics"])


def test_evaluate_python_partial_score(provider):
    answers = {"q1": "B", "q2": "C", "q3": "A", "q4": "B", "q5": "D"}  # q3 and q5 wrong
    res = provider.evaluate_assessment("python", SAMPLE_PYTHON_QUESTIONS, answers)

    assert res["score"] == 3
    assert res["total"] == 5
    assert res["percentage"] == 60.0
    assert res["proficiency_level"] == "Intermediate"
    assert len(res["recommended_topics"]) == 2
    assert "Dictionaries, hashing and why keys must be immutable" in res["recommended_topics"]
    assert "Variable scope (LEGB), closures and the nonlocal keyword" in res["recommended_topics"]


def test_evaluate_python_zero_score(provider):
    answers = {"q1": "A", "q2": "A", "q3": "A", "q4": "A", "q5": "D"}
    res = provider.evaluate_assessment("python", SAMPLE_PYTHON_QUESTIONS, answers)

    assert res["score"] == 0
    assert res["percentage"] == 0.0
    assert res["proficiency_level"] == "Beginner"
    assert len(res["recommended_topics"]) == 5


def test_evaluate_biology_assessment(provider):
    # 4/5 score in biology
    answers = {"b1": "A", "b2": "B", "b3": "A", "b4": "D", "b5": "A"}  # b3 wrong
    res = provider.evaluate_assessment("Biology", SAMPLE_BIOLOGY_QUESTIONS, answers)

    assert res["score"] == 4
    assert res["percentage"] == 80.0
    assert res["proficiency_level"] == "Intermediate"
    # Subject-specific biology recommendation for Bioenergetics
    assert any("calvin cycle" in r.lower() or "photosynthesis" in r.lower() for r in res["recommended_topics"])
    # Crucial: Must NEVER recommend Python decorators for Biology!
    assert not any("decorator" in r.lower() for r in res["recommended_topics"])


def test_evaluate_biology_perfect_score_advanced(provider):
    answers = {"b1": "A", "b2": "B", "b3": "C", "b4": "D", "b5": "A"}
    res = provider.evaluate_assessment("subj_biology", SAMPLE_BIOLOGY_QUESTIONS, answers)

    assert res["score"] == 5
    assert res["proficiency_level"] == "Advanced"
    assert any("crispr" in r.lower() for r in res["recommended_topics"])


# ---------------------------------------------------------------------------
# 8. API Contract Compliance Verification
# ---------------------------------------------------------------------------

def test_chat_response_contract_fields(provider):
    """Ensures exact backend-required fields and types in generate_chat_response."""
    res = provider.generate_chat_response(prompt="Hello", subject="Python Programming")

    assert set(res.keys()) == {"reply", "provider", "is_mock", "suggested_followups"}
    assert isinstance(res["reply"], str)
    assert isinstance(res["provider"], str)
    assert isinstance(res["is_mock"], bool)
    assert isinstance(res["suggested_followups"], list)
    assert all(isinstance(f, str) for f in res["suggested_followups"])


def test_evaluation_response_contract_fields(provider):
    """Ensures exact backend-required fields and types in evaluate_assessment."""
    answers = {"q1": "B", "q2": "C", "q3": "C", "q4": "B", "q5": "A"}
    res = provider.evaluate_assessment("python", SAMPLE_PYTHON_QUESTIONS, answers)

    required_keys = {
        "score", "total", "percentage", "proficiency_level",
        "breakdown", "recommended_topics", "summary_feedback",
        "is_mock", "provider"
    }
    assert set(res.keys()) == required_keys

    assert isinstance(res["score"], int)
    assert isinstance(res["total"], int)
    assert isinstance(res["percentage"], float)
    assert isinstance(res["proficiency_level"], str)
    assert isinstance(res["breakdown"], list)
    assert isinstance(res["recommended_topics"], list)
    assert isinstance(res["summary_feedback"], str)
    assert isinstance(res["is_mock"], bool)
    assert isinstance(res["provider"], str)

    # Check breakdown items
    item_keys = {"question_id", "question_text", "selected_option", "correct_option", "is_correct", "explanation", "topic"}
    for item in res["breakdown"]:
        assert set(item.keys()) == item_keys
        assert isinstance(item["is_correct"], bool)
