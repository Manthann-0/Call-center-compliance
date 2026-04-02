"""
Pydantic schemas for API request/response validation.
"""
from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel


# ── Upload ──────────────────────────────────────────────
class UploadResponse(BaseModel):
    job_id: str
    message: str


# ── Job Status ──────────────────────────────────────────
class JobStatus(BaseModel):
    job_id: str
    status: str
    filename: Optional[str] = None
    language: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    sop_score: Optional[float] = None
    sop_breakdown: Optional[Dict[str, float]] = None
    payment_type: Optional[str] = None
    rejection_reason: Optional[str] = None
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
