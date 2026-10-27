"""
Live AI Provider Integration: Google Gemini SDK
Owned by: Ekansh (AI/ML Evaluation)

Integrates Google Gemini via the official google-genai SDK for real-time educational tutoring.
Features:
- Multi-Subject Pedagogical Tutoring (Python, Biology, Business, AI/ML)
- Bounded Context History Management
- Configurable Model and Timeout Settings
- Zero-Leakage Credential Handling
- Authoritative Server-Owned Assessment Grading Preservation
- Resilient Fallback to Deterministic MockAIProvider (404, 429, 5xx, timeouts, missing keys)
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from .base import BaseAIProvider
from .mock_provider import (
    MockAIProvider,
    normalize_subject,
    SUBJECT_DISPLAY_NAMES,
    STARTER_FOLLOWUPS_BY_SUBJECT,
)

logger = logging.getLogger(__name__)

# Optional SDK import with graceful degradation
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception
    GENAI_AVAILABLE = False


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_HISTORY_TURNS = 8

SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are PragyaX AI, an elite educational tutor specializing in {subject}. "
    "Your mission is to guide learners to deep conceptual understanding through clear explanations, "
    "concise illustrative examples, and pedagogical encouragement.\n\n"
    "Guidelines:\n"
    "1. Keep explanations direct, educational, and easy to follow.\n"
    "2. Use concise code or conceptual snippets where appropriate.\n"
    "3. Conclude with 2 to 4 thought-provoking follow-up questions under the exact header 'Suggested Follow-ups:' "
    "numbered 1 to 4 on individual lines.\n"
    "4. Maintain a supportive, inspiring educational tone."
)


def parse_timeout_seconds(val: Optional[Any], default: float = DEFAULT_TIMEOUT_SECONDS) -> float:
    """Safely parses timeout in seconds; handles non-numeric, negative, zero, or excessively large values."""
    if val is None:
        return default
    try:
        num = float(str(val).strip())
        if num <= 0 or num > 300:
            return default
        return num
    except (ValueError, TypeError, AttributeError):
        return default


def parse_gemini_followups(raw_text: str, canonical_subject: str) -> Tuple[str, List[str]]:
    """
    Parses response text into the core reply and a list of suggested follow-up questions.
    Falls back to curated starter follow-ups if the model output does not contain structured questions.
    """
    pattern = r'(?i)\n(?:#+\s*)?(?:suggested\s+follow-?ups?|follow-?up\s+questions?|suggested\s+questions?):?\s*\n'
    match = re.search(pattern, raw_text)
    
    if match:
        reply = raw_text[:match.start()].strip()
        rest = raw_text[match.end():].strip()
        followups = [
            re.sub(r'^(?:[-*•]|\d+[\.)])\s*', '', line).strip()
            for line in rest.splitlines()
            if line.strip()
        ]
        if followups:
            return reply or raw_text.strip(), followups[:4]

    # Fallback to subject-specific defaults if no follow-ups were parsed
    default_followups = STARTER_FOLLOWUPS_BY_SUBJECT.get(
        canonical_subject, STARTER_FOLLOWUPS_BY_SUBJECT["python"]
    )
    return raw_text.strip(), list(default_followups)


class RealAIProvider(BaseAIProvider):
    """
    Live AI Provider using Google Gemini SDK with automatic fallback to MockAIProvider.
    Ensures high availability, security, and strict contract adherence.
    """

    def __init__(self, provider_type: str = "gemini"):
        self._provider_type = provider_type.lower()
        self._fallback = MockAIProvider()
        self._client: Optional[Any] = None

    @property
    def api_key(self) -> Optional[str]:
        """Retrieves active Gemini API key from environment without logging or exposing it."""
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            # Secondary check for generic API key if provider_type requires it
            key = os.getenv("OPENAI_API_KEY") if self._provider_type == "openai" else None
        return key.strip() if key and key.strip() else None

    @property
    def model_name(self) -> str:
        """Returns the configured or default Gemini model identifier."""
        custom_model = os.getenv("GEMINI_MODEL", "").strip()
        return custom_model if custom_model else DEFAULT_GEMINI_MODEL

    @property
    def timeout_seconds(self) -> float:
        """Returns the configured or default timeout in seconds."""
        return parse_timeout_seconds(os.getenv("GEMINI_TIMEOUT_SECONDS"))

    @property
    def timeout_ms(self) -> int:
        """Returns timeout converted to milliseconds for the Google GenAI SDK."""
        return int(self.timeout_seconds * 1000)

    @property
    def provider_name(self) -> str:
        """User-facing provider identifier. Never exposes credentials."""
        if self._has_valid_credentials() and GENAI_AVAILABLE:
            return f"Google Gemini ({self.model_name})"
        return f"Google Gemini (fallback to {self._fallback.provider_name})"

    @property
    def is_mock(self) -> bool:
        """Indicates if the provider is currently operating in local mock mode."""
        return not (self._has_valid_credentials() and GENAI_AVAILABLE)

    def _has_valid_credentials(self) -> bool:
        """Validates that a non-empty, plausibly structured API key is present."""
        key = self.api_key
        return bool(key and len(key) >= 10)

    def _get_client(self) -> Optional[Any]:
        """Initializes or retrieves the Google GenAI client instance with configured HttpOptions."""
        if not GENAI_AVAILABLE or not self._has_valid_credentials():
            return None
        
        try:
            http_options = types.HttpOptions(timeout=self.timeout_ms)
            return genai.Client(api_key=self.api_key, http_options=http_options)
        except Exception:
            # Never leak initialization details or credentials
            return None

    def _build_contents(self, prompt: str, history: Optional[List[Dict[str, str]]]) -> List[Any]:
        """Constructs bounded, type-safe content messages for the Gemini SDK."""
        contents: List[Any] = []

        if history and isinstance(history, list):
            # Take only the most recent N turns to respect token boundaries
            recent_history = history[-MAX_HISTORY_TURNS:]
            for item in recent_history:
                if not isinstance(item, dict):
                    continue
                role_raw = item.get("role", "")
                content_raw = item.get("content", "")
                if not content_raw or not isinstance(content_raw, str):
                    continue

                # Gemini SDK expects 'user' or 'model' roles
                role = "model" if role_raw in ("assistant", "model") else "user"
                try:
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=content_raw)]
                    ))
                except Exception:
                    continue

        # Append current user prompt
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        ))
        return contents

    def generate_chat_response(
        self, prompt: str, subject: str = "Python Programming", history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generates educational, context-aware responses via Google Gemini.
        Falls back seamlessly to MockAIProvider on any network, quota, auth, or model errors.
        """
        prompt_clean = prompt.strip() if prompt else ""
        canonical_subject = normalize_subject(subject)
        display_subject = SUBJECT_DISPLAY_NAMES.get(canonical_subject, subject or "Python Programming")

        # Fast fallback if credentials or SDK are missing
        if not self._has_valid_credentials() or not GENAI_AVAILABLE:
            return self._fallback.generate_chat_response(prompt_clean, subject, history)

        client = self._get_client()
        if client is None:
            return self._fallback.generate_chat_response(prompt_clean, subject, history)

        try:
            contents = self._build_contents(prompt_clean, history)
            system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(subject=display_subject)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=1000,
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

            # Defensive verification of response text
            raw_text = getattr(response, "text", None)
            if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
                return self._fallback.generate_chat_response(prompt_clean, subject, history)

            reply_text, followups = parse_gemini_followups(raw_text, canonical_subject)

            return {
                "reply": reply_text,
                "provider": f"Google Gemini ({self.model_name})",
                "is_mock": False,
                "suggested_followups": followups,
            }

        except Exception:
            # Fall back reliably on 403, 404, 429, 5xx, timeouts, connection drops
            # Ensure no credentials or raw exception messages leak to callers
            return self._fallback.generate_chat_response(prompt_clean, subject, history)

    def evaluate_assessment(
        self,
        subject: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Evaluates assessment submissions.
        SECURITY INVARIANT:
        Assessment scoring is server-owned and deterministic. Answer keys and questions
        are NEVER transmitted to Gemini. Delegates evaluation directly to MockAIProvider.
        """
        return self._fallback.evaluate_assessment(subject, questions, user_answers)
