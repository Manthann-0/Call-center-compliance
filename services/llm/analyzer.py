"""
LLM Analysis Service — Cerebras API (OpenAI-compatible) for call transcript analysis.
Strict structured prompt for compliance evaluation.
Features: singleton client, retry on invalid JSON, transcript truncation for long inputs.
"""
import json
import logging
from typing import Dict, Any

from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)

# ── Module-level singleton client ───────────────────────────────
_client = None


def _get_client() -> OpenAI:
    """Get or create the singleton OpenAI client for Cerebras."""
    global _client
    if _client is not None:
        return _client

    if not settings.LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY not configured — get a free key at https://cloud.cerebras.ai"
        )

    _client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )
    logger.info(f"Initialized Cerebras LLM client (model={settings.LLM_MODEL})")
    return _client


# ── Strict Compliance Prompt ────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a precise call center compliance AI. "
    "Always respond with valid JSON only. No markdown, no explanation, no code fences. "
    "Never include ```json or ``` markers. Output raw JSON only."
)

ANALYSIS_PROMPT = """You are a call center compliance AI.
Analyze the following translated English call transcript and return:

1. Summary (2-3 lines describing the call)
2. Payment Type — classify the payment discussed. Must be EXACTLY one of: "EMI", "FULL_PAYMENT", "PARTIAL_PAYMENT", "DOWN_PAYMENT". Use "EMI" as default if unclear.
3. SOP Validation — evaluate each step:
   - greeting: Did the agent greet the customer properly? (true/false)
   - identification: Did the agent verify customer identity? (true/false)
   - problemStatement: Did the agent clearly state the purpose/problem? (true/false)
   - solutionOffering: Did the agent offer solutions or payment options? (true/false)
   - closing: Did the agent close the call professionally? (true/false)
   - complianceScore: Overall compliance score from 0.0 to 1.0
   - adherenceStatus: "FOLLOWED" if complianceScore >= 0.6, otherwise "NOT_FOLLOWED"
   - explanation: Brief explanation of the compliance assessment
4. Rejection Reason — if customer rejected, classify as EXACTLY one of: "HIGH_INTEREST", "BUDGET_CONSTRAINTS", "ALREADY_PAID", "NOT_INTERESTED". Use "NONE" if no rejection.
5. Sentiment — EXACTLY one of: "Positive", "Neutral", "Negative"
6. Keywords — list of important keywords from the call (5-10 keywords)

Return ONLY this JSON structure, nothing else:
{{
  "summary": "...",
  "sop_validation": {{
    "greeting": true,
    "identification": false,
    "problemStatement": true,
    "solutionOffering": true,
    "closing": true,
    "complianceScore": 0.0,
    "adherenceStatus": "FOLLOWED",
    "explanation": "..."
  }},
  "analytics": {{
    "paymentPreference": "EMI",
    "rejectionReason": "NONE",
    "sentiment": "Neutral"
  }},
  "keywords": []
}}

TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Return ONLY the JSON object. No markdown. No explanation."""

# Maximum transcript length to send to LLM (chars) — prevents token limit issues
MAX_TRANSCRIPT_CHARS = 8000


def _parse_llm_response(content: str) -> Dict[str, Any]:
    """
    Parse the LLM response, stripping markdown fences if present.
    Returns the parsed dict or raises ValueError.
    """
    content = content.strip()

    # Strip markdown code fences (multiple formats)
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    # Try to find JSON object in the response
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        content = content[start:end]

    try:
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("LLM returned non-object JSON")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}\nContent: {content[:500]}")
        raise ValueError(f"LLM returned invalid JSON: {e}")


def _call_llm(transcript: str) -> Dict[str, Any]:
    """
    Make a single LLM API call and parse the response.
    Returns parsed dict or raises ValueError/RuntimeError.
    """
    client = _get_client()

    # Truncate very long transcripts to avoid token limits
    truncated = transcript
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        truncated = transcript[:MAX_TRANSCRIPT_CHARS] + "\n... [transcript truncated for analysis]"
        logger.info(f"Transcript truncated from {len(transcript)} to {MAX_TRANSCRIPT_CHARS} chars")

    prompt = ANALYSIS_PROMPT.format(transcript=truncated)

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise RuntimeError(f"LLM analysis failed: {e}")

    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty response")

    logger.info(f"LLM response received ({len(content)} chars)")

    return _parse_llm_response(content)


def analyse_transcript(transcript: str) -> Dict[str, Any]:
    """
    Send transcript to Cerebras LLM for full compliance analysis.
    Includes retry logic: if first attempt returns invalid JSON, retry once.
    Returns raw parsed dict from LLM (to be normalized by SOP validator).
    """
    logger.info(
        f"Sending transcript ({len(transcript)} chars) to {settings.LLM_MODEL} for analysis..."
    )

    # Attempt 1
    try:
        result = _call_llm(transcript)
        logger.info(f"LLM analysis parsed — keys: {list(result.keys())}")
        return result
    except ValueError as e:
        logger.warning(f"LLM attempt 1 failed (invalid JSON): {e} — retrying...")

    # Attempt 2 — retry once on JSON parse failure
    try:
        result = _call_llm(transcript)
        logger.info(f"LLM retry succeeded — keys: {list(result.keys())}")
        return result
    except ValueError as e:
        logger.error(f"LLM attempt 2 also failed: {e}")
        raise

    except RuntimeError:
        raise
