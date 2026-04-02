"""
AI Pipeline — LLM-based analysis of call transcripts via OpenAI-compatible API.
Default provider: Cerebras (free tier, llama-3.1-8b).
Produces: summary, SOP rubric scores (0–1 per step), payment type, rejection reason.
"""
import json
import logging
from typing import Dict, Any

from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

# SOP criteria with weights (must sum to 1.0)
SOP_CRITERIA = {
    "greeting_identity_verification": {
        "label": "Greeting & Identity Verification",
        "weight": 0.20,
        "description": "Did the agent properly greet the customer and verify their identity?",
    },
    "loan_product_explanation": {
        "label": "Loan/Product Explanation",
        "weight": 0.20,
        "description": "Did the agent clearly explain the loan or product details?",
    },
    "payment_options_offered": {
        "label": "Payment Options Offered",
        "weight": 0.20,
        "description": "Did the agent present available payment options to the customer?",
    },
    "objection_handling": {
        "label": "Objection Handling",
        "weight": 0.20,
        "description": "How well did the agent handle customer objections or concerns?",
    },
    "closing_next_steps": {
        "label": "Closing & Next Steps",
        "weight": 0.20,
        "description": "Did the agent properly close the call with clear next steps?",
    },
}

ANALYSIS_PROMPT = """You are a call center compliance analyst. Analyze the following call transcript and return a JSON object with these exact keys:

1. "summary": A concise 2-3 sentence summary of the call.

2. "sop_scores": An object with these exact keys, each scored as a decimal between 0 and 1 (e.g. 0.0, 0.25, 0.5, 0.75, 1.0):
   - "greeting_identity_verification": {criteria_desc[greeting_identity_verification]}
   - "loan_product_explanation": {criteria_desc[loan_product_explanation]}
   - "payment_options_offered": {criteria_desc[payment_options_offered]}
   - "objection_handling": {criteria_desc[objection_handling]}
   - "closing_next_steps": {criteria_desc[closing_next_steps]}

3. "payment_type": Classify the payment discussed. Must be one of: "EMI", "Full Payment", "Partial Payment", "Down Payment", or null if no payment was discussed.

4. "rejection_reason": If the customer rejected payment or the call outcome was negative, classify the reason. Must be one of: "Price Too High", "Already Paid", "Wrong Timing", "Disputes Loan", "No Money", "Will Pay Later", "Other", or null if there was no rejection.

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanation, no code fences.
- All sop_scores values must be decimals between 0.0 and 1.0.
- Score 1.0 = fully met, 0.5 = partially met, 0.0 = not met at all.
- If the transcript is in Hindi/Hinglish or Tamil/Tanglish, you should still understand and analyse it.

TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Return only the JSON object:"""


def _build_prompt(transcript: str) -> str:
    """Build the analysis prompt with criteria descriptions."""
    criteria_desc = {k: v["description"] for k, v in SOP_CRITERIA.items()}
    return ANALYSIS_PROMPT.format(
        transcript=transcript,
        criteria_desc=criteria_desc,
    )


def _parse_response(content: str) -> Dict[str, Any]:
    """Parse and validate the LLM response JSON."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    data = json.loads(content)

    result = {
        "summary": str(data.get("summary", "No summary generated.")),
        "sop_scores": {},
        "sop_total": 0.0,
        "payment_type": None,
        "rejection_reason": None,
    }

    # Validate SOP scores (0–1 scale)
    raw_scores = data.get("sop_scores", {})
    weighted_total = 0.0
    for key, meta in SOP_CRITERIA.items():
        score = raw_scores.get(key, 0)
        try:
            score = float(score)
            # If LLM returned 0-100 instead of 0-1, auto-correct
            if score > 1.0:
                score = score / 100.0
            score = max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            score = 0.0
        result["sop_scores"][key] = round(score, 2)
        weighted_total += score * meta["weight"]

    result["sop_total"] = round(weighted_total, 2)

    # Validate payment type
    valid_payments = {"EMI", "Full Payment", "Partial Payment", "Down Payment"}
    pt = data.get("payment_type")
    if pt and str(pt).strip() in valid_payments:
        result["payment_type"] = str(pt).strip()

    # Validate rejection reason
    valid_rejections = {
        "Price Too High", "Already Paid", "Wrong Timing",
        "Disputes Loan", "No Money", "Will Pay Later", "Other",
    }
    rr = data.get("rejection_reason")
    if rr and str(rr).strip() in valid_rejections:
        result["rejection_reason"] = str(rr).strip()

    return result


def analyse_transcript(transcript: str) -> Dict[str, Any]:
    """
    Send transcript to LLM for full analysis via OpenAI-compatible API.
    Returns dict with keys: summary, sop_scores, sop_total, payment_type, rejection_reason.
    """
    if not settings.LLM_API_KEY:
        raise ValueError("LLM_API_KEY not configured — get a free key at https://cloud.cerebras.ai")

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )
    prompt = _build_prompt(transcript)

    logger.info(f"Sending transcript ({len(transcript)} chars) to {settings.LLM_MODEL} for analysis...")

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a precise call center compliance analyst. Always respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    content = response.choices[0].message.content
    logger.info(f"LLM response received ({len(content)} chars)")

    result = _parse_response(content)
    logger.info(
        f"Analysis complete — SOP: {result['sop_total']}, "
        f"Payment: {result['payment_type']}, Rejection: {result['rejection_reason']}"
    )
    return result


def get_sop_criteria() -> Dict[str, Dict]:
    """Return SOP criteria metadata for the frontend."""
    return SOP_CRITERIA
