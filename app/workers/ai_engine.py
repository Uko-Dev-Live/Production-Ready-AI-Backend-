"""
app/workers/ai_engine.py
─────────────────────────
AI Engine — the core AI integration layer.

This module wraps the OpenAI API (or any LLM provider) and exposes
clean job-type-specific methods that the Celery tasks call.

Why a separate module?
  • Keeps AI logic isolated and easily swappable (swap OpenAI for Anthropic
    or a local Ollama model without touching any task code).
  • Makes it easy to mock in tests.
  • Handles retries, rate limits, and prompt engineering in one place.

If OPENAI_API_KEY is missing or invalid, the engine falls back to a
built-in mock so the project runs without any API key during development.
"""

import json
import os
import re
import time

import structlog

logger = structlog.get_logger(__name__)


class AIEngine:
    """Thin wrapper around OpenAI chat completions."""

    SYSTEM_PROMPTS = {
        "summarise": (
            "You are a professional summarisation assistant. "
            "Return a JSON object: {\"summary\": \"...\", \"key_points\": [...], \"word_count\": N}. "
            "JSON only, no markdown fences."
        ),
        "sentiment": (
            "You are a sentiment analysis engine. "
            "Return JSON: {\"sentiment\": \"positive|negative|neutral\", "
            "\"confidence\": 0.0-1.0, \"reasoning\": \"...\"}. JSON only."
        ),
        "classify": (
            "You are a content classifier. Classify into one of: "
            "technology, finance, health, sports, entertainment, politics, other. "
            "Return JSON: {\"category\": \"...\", \"confidence\": 0.0-1.0, "
            "\"sub_topics\": [...]}. JSON only."
        ),
        "generate": (
            "You are a creative writing assistant. "
            "Return JSON: {\"generated_text\": \"...\", \"tokens_used\": N}. JSON only."
        ),
    }

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "1024"))
        self._client = None

        if self.api_key and not self.api_key.startswith("sk-your"):
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialised", model=self.model)
            except ImportError:
                logger.warning("openai package not installed — using mock")
        else:
            logger.warning("No valid OPENAI_API_KEY — using mock AI responses")

    def run(self, job_type: str, input_text: str) -> dict:
        """
        Execute an AI job and return a structured result dict.
        Falls back to mock if no API key is configured.
        """
        if job_type not in self.SYSTEM_PROMPTS:
            raise ValueError(
                f"Unknown job_type '{job_type}'. "
                f"Valid types: {list(self.SYSTEM_PROMPTS.keys())}"
            )

        if self._client:
            return self._call_openai(job_type, input_text)
        else:
            return self._mock_response(job_type, input_text)

    def _call_openai(self, job_type: str, input_text: str) -> dict:
        """Real OpenAI API call with structured JSON output."""
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
        def _call():
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPTS[job_type]},
                    {"role": "user", "content": input_text},
                ],
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)
            result["_meta"] = {
                "model": self.model,
                "job_type": job_type,
                "tokens": response.usage.total_tokens,
            }
            return result

        return _call()

    def _mock_response(self, job_type: str, input_text: str) -> dict:
        """
        Deterministic mock responses for local development without an API key.
        Simulates a short processing delay so the async/worker flow is realistic.
        """
        time.sleep(2)   # simulate LLM latency

        word_count = len(input_text.split())
        mocks = {
            "summarise": {
                "summary": f"[MOCK] This text discusses: {input_text[:120]}...",
                "key_points": [
                    "Key point extracted from the text",
                    "Another important observation",
                    "Final summary note",
                ],
                "word_count": word_count,
                "_meta": {"model": "mock", "job_type": "summarise", "tokens": 0},
            },
            "sentiment": {
                "sentiment": "positive",
                "confidence": 0.87,
                "reasoning": "[MOCK] The text has a generally optimistic tone.",
                "_meta": {"model": "mock", "job_type": "sentiment", "tokens": 0},
            },
            "classify": {
                "category": "technology",
                "confidence": 0.91,
                "sub_topics": ["AI", "machine learning", "automation"],
                "_meta": {"model": "mock", "job_type": "classify", "tokens": 0},
            },
            "generate": {
                "generated_text": (
                    "[MOCK] Once upon a time in a world powered by artificial intelligence, "
                    "engineers built systems that could understand and generate human language "
                    "with remarkable fluency. The future was bright."
                ),
                "tokens_used": 0,
                "_meta": {"model": "mock", "job_type": "generate", "tokens": 0},
            },
        }
        return mocks[job_type]
