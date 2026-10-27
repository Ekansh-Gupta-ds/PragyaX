"""Server-owned grading; the existing AI contract supplies feedback only."""
from copy import deepcopy
from pydantic import BaseModel, ConfigDict


class EvaluationFeedback(BaseModel):
    model_config = ConfigDict(strict=True)
    summary_feedback: str
    recommended_topics: list[str]
    is_mock: bool = True
    provider: str = 'PragyaX AI'


def evaluate_assessment(provider, subject, questions, answers):
    # Compute trusted facts before calling a provider; give it detached inputs.
    breakdown = []
    for question in questions:
        correct = question['correct_option'].strip().upper()
        selected = answers[question['id']]
        breakdown.append({
            'question_id': question['id'],
            'question_text': question['question_text'],
            'selected_option': selected,
            'correct_option': correct,
            'is_correct': selected == correct,
            'explanation': question.get('explanation', ''),
            'topic': question.get('topic', 'Python fundamentals'),
        })
    score = sum(item['is_correct'] for item in breakdown)
    total = len(questions)
    percentage = round(score / total * 100, 1) if total > 0 else 0.0
    level = 'Advanced' if score == total else 'Intermediate' if (score / total if total > 0 else 0) >= .6 else 'Beginner'
    feedback = EvaluationFeedback.model_validate(provider.evaluate_assessment(
        subject=subject, questions=deepcopy(questions), user_answers=dict(answers)
    ))
    return {
        **feedback.model_dump(),
        'score': score,
        'total': total,
        'percentage': percentage,
        'proficiency_level': level,
        'breakdown': breakdown
    }
