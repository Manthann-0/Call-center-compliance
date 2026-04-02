"""
Pydantic schemas for API request/response validation.
"""
from typing import Optional, Dict, List, Any
from pydantic import BaseModel


# ── Call Analytics (New Strict API) ─────────────────────
class CallAnalyticsRequest(BaseModel):
    language: str
    audioFormat: str
    audioBase64: str


class SOPValidation(BaseModel):
    greeting: bool = False
    identification: bool = False
    problemStatement: bool = False
    solutionOffering: bool = False
    closing: bool = False
    complianceScore: float = 0.0
    adherenceStatus: str = "NOT_FOLLOWED"
    explanation: str = ""


class Analytics(BaseModel):
    paymentPreference: str = "EMI"
    rejectionReason: str = "NONE"
    sentiment: str = "Neutral"


class CallAnalyticsResponse(BaseModel):
    status: str = "success"
    language: str = ""
    transcript: str = ""
    summary: str = ""
    sop_validation: SOPValidation = SOPValidation()
    analytics: Analytics = Analytics()
    keywords: List[str] = []


# ── Upload (Legacy) ────────────────────────────────────
class UploadResponse(BaseModel):
    job_id: str
    message: str


# ── Job Status (Legacy) ────────────────────────────────
class JobStatus(BaseModel):
    job_id: str
    status: str
    filename: Optional[str] = None
    language: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    sop_score: Optional[float] = None
    sop_breakdown: Optional[Dict[str, Any]] = None
    payment_type: Optional[str] = None
    rejection_reason: Optional[str] = None
    sentiment: Optional[str] = None
    keywords: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Call List Item ──────────────────────────────────────
class CallListItem(BaseModel):
    id: str
    filename: str
    language: Optional[str] = None
    payment_type: Optional[str] = None
    sop_score: Optional[float] = None
    rejection_reason: Optional[str] = None
    status: str
    created_at: Optional[str] = None


# ── Dashboard Metrics ──────────────────────────────────
class DashboardMetrics(BaseModel):
    total_calls: int
    calls_today: int
    avg_sop_score: Optional[float] = None
    rejection_rate: float
    payment_distribution: Dict[str, int]
    language_distribution: Dict[str, int]
    rejection_reasons: Dict[str, int]
    avg_sop_breakdown: Optional[Dict[str, float]] = None


# ── Health ──────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
