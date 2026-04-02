"""
SOP Validator — normalizes and validates LLM output to match strict API response format.
Ensures ALL required fields exist and conform to allowed values.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# ── Allowed enum values ─────────────────────────────────────────
VALID_PAYMENT_TYPES = {"EMI", "FULL_PAYMENT", "PARTIAL_PAYMENT", "DOWN_PAYMENT"}
VALID_REJECTION_REASONS = {"HIGH_INTEREST", "BUDGET_CONSTRAINTS", "ALREADY_PAID", "NOT_INTERESTED", "NONE"}
VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}
VALID_ADHERENCE = {"FOLLOWED", "NOT_FOLLOWED"}


def _normalize_bool(value) -> bool:
    """Convert various truthy/falsy values to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "y")
    if isinstance(value, (int, float)):
        return value > 0
    return False


def _normalize_score(value) -> float:
    """Ensure compliance score is a float between 0.0 and 1.0."""
    try:
        score = float(value)
        if score > 1.0:
            score = score / 100.0  # Auto-correct 0-100 scale
        return max(0.0, min(1.0, round(score, 2)))
    except (ValueError, TypeError):
        return 0.0


def _normalize_payment(value) -> str:
    """Normalize payment preference to valid enum."""
    if not value or str(value).strip().upper() in ("NONE", "NULL", "N/A", ""):
        return "EMI"  # Default

    raw = str(value).strip().upper().replace(" ", "_")

    # Map common variations
    payment_map = {
        "EMI": "EMI",
        "FULL_PAYMENT": "FULL_PAYMENT",
        "FULL": "FULL_PAYMENT",
        "FULLPAYMENT": "FULL_PAYMENT",
        "PARTIAL_PAYMENT": "PARTIAL_PAYMENT",
        "PARTIAL": "PARTIAL_PAYMENT",
        "PARTIALPAYMENT": "PARTIAL_PAYMENT",
        "DOWN_PAYMENT": "DOWN_PAYMENT",
        "DOWN": "DOWN_PAYMENT",
        "DOWNPAYMENT": "DOWN_PAYMENT",
    }

    return payment_map.get(raw, "EMI")


def _normalize_rejection(value) -> str:
    """Normalize rejection reason to valid enum."""
    if not value or str(value).strip().upper() in ("NONE", "NULL", "N/A", ""):
        return "NONE"

    raw = str(value).strip().upper().replace(" ", "_")

    rejection_map = {
        "HIGH_INTEREST": "HIGH_INTEREST",
        "HIGHINTEREST": "HIGH_INTEREST",
        "BUDGET_CONSTRAINTS": "BUDGET_CONSTRAINTS",
        "BUDGETCONSTRAINTS": "BUDGET_CONSTRAINTS",
        "NO_MONEY": "BUDGET_CONSTRAINTS",
        "NOMONEY": "BUDGET_CONSTRAINTS",
        "ALREADY_PAID": "ALREADY_PAID",
        "ALREADYPAID": "ALREADY_PAID",
        "NOT_INTERESTED": "NOT_INTERESTED",
        "NOTINTERESTED": "NOT_INTERESTED",
        "NONE": "NONE",
        "PRICE_TOO_HIGH": "HIGH_INTEREST",
        "PRICETOO_HIGH": "HIGH_INTEREST",
        "WILL_PAY_LATER": "NOT_INTERESTED",
        "WRONG_TIMING": "NOT_INTERESTED",
        "DISPUTES_LOAN": "NOT_INTERESTED",
    }

    return rejection_map.get(raw, "NONE")


def _normalize_sentiment(value) -> str:
    """Normalize sentiment to valid enum."""
    if not value:
        return "Neutral"

    raw = str(value).strip().lower()

    if "pos" in raw:
        return "Positive"
    elif "neg" in raw:
        return "Negative"
    else:
        return "Neutral"


def _normalize_adherence(score: float) -> str:
    """Determine adherence status based on compliance score."""
    return "FOLLOWED" if score >= 0.6 else "NOT_FOLLOWED"


def normalize_response(
    llm_output: Dict[str, Any],
    language: str,
    transcript: str,
) -> Dict[str, Any]:
    """
    Normalize LLM output into the strict API response format.
    Ensures ALL required fields exist with valid values.

    Returns the complete response dict matching the API spec.
    """
    # ── Extract summary ──
    summary = str(llm_output.get("summary", "")).strip()
    if not summary:
        summary = "Call analysis completed. No detailed summary available."

    # ── Extract and normalize SOP validation ──
    sop_raw = llm_output.get("sop_validation", {})
    if not isinstance(sop_raw, dict):
        sop_raw = {}

    compliance_score = _normalize_score(sop_raw.get("complianceScore", 0.0))

    sop_validation = {
        "greeting": _normalize_bool(sop_raw.get("greeting", False)),
        "identification": _normalize_bool(sop_raw.get("identification", False)),
        "problemStatement": _normalize_bool(sop_raw.get("problemStatement", False)),
        "solutionOffering": _normalize_bool(sop_raw.get("solutionOffering", False)),
        "closing": _normalize_bool(sop_raw.get("closing", False)),
        "complianceScore": compliance_score,
        "adherenceStatus": _normalize_adherence(compliance_score),
        "explanation": str(sop_raw.get("explanation", "SOP compliance evaluated based on transcript analysis.")).strip(),
    }

    # Override adherenceStatus if LLM provided one and it's valid
    llm_adherence = str(sop_raw.get("adherenceStatus", "")).strip().upper()
    if llm_adherence in VALID_ADHERENCE:
        sop_validation["adherenceStatus"] = llm_adherence

    # ── Extract and normalize analytics ──
    analytics_raw = llm_output.get("analytics", {})
    if not isinstance(analytics_raw, dict):
        analytics_raw = {}

    analytics = {
        "paymentPreference": _normalize_payment(
            analytics_raw.get("paymentPreference",
                              llm_output.get("payment_type",
                                             llm_output.get("paymentPreference")))
        ),
        "rejectionReason": _normalize_rejection(
            analytics_raw.get("rejectionReason",
                              llm_output.get("rejection_reason",
                                             llm_output.get("rejectionReason")))
        ),
        "sentiment": _normalize_sentiment(
            analytics_raw.get("sentiment",
                              llm_output.get("sentiment"))
        ),
    }

    # ── Extract keywords ──
    keywords_raw = llm_output.get("keywords", [])
    if isinstance(keywords_raw, list):
        keywords = [str(k).strip() for k in keywords_raw if k and str(k).strip()]
    elif isinstance(keywords_raw, str):
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    else:
        keywords = []

    # Ensure at least some keywords
    if not keywords:
        keywords = _extract_fallback_keywords(transcript)

    # ── Build final response ──
    return {
        "status": "success",
        "language": language,
        "transcript": transcript,
        "summary": summary,
        "sop_validation": sop_validation,
        "analytics": analytics,
        "keywords": keywords,
    }


def _extract_fallback_keywords(transcript: str) -> List[str]:
    """
    Extract basic keywords from transcript as fallback.
    """
    common_keywords = [
        "payment", "loan", "emi", "account", "bank",
        "customer", "amount", "due", "interest", "balance",
        "call", "service", "complaint", "resolution",
    ]

    transcript_lower = transcript.lower()
    found = [kw for kw in common_keywords if kw in transcript_lower]
    return found[:10] if found else ["call", "customer", "service"]
