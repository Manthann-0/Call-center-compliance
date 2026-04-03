"""
FastAPI application — routes, CORS, static file serving, and API router.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from database import init_db, get_db, SessionLocal
from models import Call
from schemas import UploadResponse, JobStatus, DashboardMetrics, HealthResponse

# Import the new call-analytics router
from api.call_analytics import router as analytics_router
from api.auth import APIKeyError

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────
app = FastAPI(
    title="CallCenter Compliance AI",
    description="Multilingual call center compliance analytics platform",
    version="2.0.0",
)

# CORS — allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include API Routers ─────────────────────────────────
app.include_router(analytics_router, tags=["Call Analytics"])


# ── Exception Handlers ──────────────────────────────────
@app.exception_handler(APIKeyError)
async def api_key_error_handler(request, exc: APIKeyError):
    """Return clean 401 JSON for auth failures."""
    return JSONResponse(
        status_code=401,
        content={"status": "error", "message": exc.message},
    )

# ── Startup ─────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Database initialized, upload dir ready. Using Sarvam Saaras for STT.")


# ── Static Files ────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ═══════════════════════════════════════════════════════
# LEGACY ROUTES (preserved for dashboard + upload flow)
# ═══════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def root():
    """Serve the dashboard."""
    html_path = os.path.join(static_dir, "dashboard.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return JSONResponse({"message": "CallCenter Compliance AI — API is running. Dashboard not found."})


@app.post("/", include_in_schema=False)
async def root_post(request: Request):
    """Redirect POST requests to the correct API endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "message": "Use POST /api/call-analytics for call analysis",
            "endpoint": "/api/call-analytics",
            "method": "POST",
            "required_headers": {"x-api-key": "your-api-key", "Content-Type": "application/json"},
            "required_body": {"language": "Auto|Hindi|Tamil", "audioFormat": "mp3", "audioBase64": "base64-encoded-audio"}
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """API health check."""
    db_status = "connected"
    redis_status = "unknown"

    try:
        db = SessionLocal()
        db.execute(func.now() if not settings.DATABASE_URL.startswith("sqlite") else func.date("now"))
        db.close()
    except Exception:
        db_status = "disconnected"

    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return HealthResponse(status="healthy", database=db_status, redis=redis_status)


@app.post("/upload", response_model=UploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload an audio file for processing.
    Returns a job_id immediately — processing is async via Celery.
    """
    allowed_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}")

    if language and language not in ("Hindi", "Tamil"):
        raise HTTPException(status_code=400, detail="Language must be 'Hindi' or 'Tamil'")

    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    call = Call(
        id=job_id,
        filename=file.filename,
        language=language,
        status="pending",
    )
    db.add(call)
    db.commit()

    # Enqueue Celery task
    from tasks.celery_tasks import process_call
    process_call.delay(job_id, file_path, language)

    logger.info(f"Uploaded {file.filename} → job_id: {job_id}")
    return UploadResponse(job_id=job_id, message="File uploaded — processing enqueued.")


@app.get("/job/{job_id}/status", response_model=JobStatus)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get the current status and results for a processing job."""
    call = db.query(Call).filter(Call.id == job_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(
        job_id=call.id,
        status=call.status,
        filename=call.filename,
        language=call.language,
        transcript=call.transcript,
        summary=call.summary,
        sop_score=call.sop_score,
        sop_breakdown=call.sop_breakdown,
        payment_type=call.payment_type,
        rejection_reason=call.rejection_reason,
        sentiment=call.sentiment,
        keywords=call.keywords,
        error_message=call.error_message,
        created_at=call.created_at.isoformat() if call.created_at else None,
        completed_at=call.completed_at.isoformat() if call.completed_at else None,
    )


@app.get("/calls")
async def list_calls(
    language: Optional[str] = Query(None),
    payment_type: Optional[str] = Query(None),
    sop_min: Optional[float] = Query(None),
    sop_max: Optional[float] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all processed calls with optional filters."""
    query = db.query(Call).order_by(Call.created_at.desc())

    if language:
        query = query.filter(Call.language == language)
    if payment_type:
        query = query.filter(Call.payment_type == payment_type)
    if sop_min is not None:
        query = query.filter(Call.sop_score >= sop_min)
    if sop_max is not None:
        query = query.filter(Call.sop_score <= sop_max)
    if status:
        query = query.filter(Call.status == status)
    if search:
        query = query.filter(
            (Call.filename.ilike(f"%{search}%")) | (Call.id.ilike(f"%{search}%"))
        )

    calls = query.limit(200).all()
    return [c.to_dict() for c in calls]


@app.get("/calls/{job_id}")
async def get_call_detail(job_id: str, db: Session = Depends(get_db)):
    """Full call detail including transcript, summary, SOP breakdown."""
    call = db.query(Call).filter(Call.id == job_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call.to_dict()


@app.get("/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Aggregate stats for the dashboard."""
    total = db.query(func.count(Call.id)).scalar() or 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    calls_today = db.query(func.count(Call.id)).filter(Call.created_at >= today_start).scalar() or 0

    avg_sop = db.query(func.avg(Call.sop_score)).filter(
        Call.status == "completed", Call.sop_score.isnot(None)
    ).scalar()
    avg_sop = round(avg_sop, 2) if avg_sop else None

    completed = db.query(func.count(Call.id)).filter(Call.status == "completed").scalar() or 0
    rejected = db.query(func.count(Call.id)).filter(
        Call.status == "completed", Call.rejection_reason.isnot(None),
        Call.rejection_reason != "NONE",
    ).scalar() or 0
    rejection_rate = round((rejected / completed * 100), 1) if completed > 0 else 0.0

    payment_rows = (
        db.query(Call.payment_type, func.count(Call.id))
        .filter(Call.payment_type.isnot(None))
        .group_by(Call.payment_type)
        .all()
    )
    payment_dist = {pt: cnt for pt, cnt in payment_rows}

    lang_rows = (
        db.query(Call.language, func.count(Call.id))
        .filter(Call.language.isnot(None))
        .group_by(Call.language)
        .all()
    )
    lang_dist = {lang: cnt for lang, cnt in lang_rows}

    rej_rows = (
        db.query(Call.rejection_reason, func.count(Call.id))
        .filter(Call.rejection_reason.isnot(None), Call.rejection_reason != "NONE")
        .group_by(Call.rejection_reason)
        .all()
    )
    rej_dist = {reason: cnt for reason, cnt in rej_rows}

    avg_breakdown = None
    if completed > 0:
        calls_with_breakdown = (
            db.query(Call.sop_breakdown)
            .filter(Call.status == "completed", Call.sop_breakdown.isnot(None))
            .all()
        )
        if calls_with_breakdown:
            totals = {}
            count = 0
            for (bd,) in calls_with_breakdown:
                if bd and isinstance(bd, dict):
                    count += 1
                    for k, v in bd.items():
                        if isinstance(v, (int, float)):
                            totals[k] = totals.get(k, 0) + (v or 0)
            if count > 0:
                avg_breakdown = {k: round(v / count, 2) for k, v in totals.items()}

    return DashboardMetrics(
        total_calls=total,
        calls_today=calls_today,
        avg_sop_score=avg_sop,
        rejection_rate=rejection_rate,
        payment_distribution=payment_dist,
        language_distribution=lang_dist,
        rejection_reasons=rej_dist,
        avg_sop_breakdown=avg_breakdown,
    )


@app.post("/analyze", include_in_schema=False)
@app.post("/analyse", include_in_schema=False)
@app.post("/call-analytics", include_in_schema=False)
async def redirect_to_api(request: Request):
    """Redirect common endpoint variations to the correct API."""
    return JSONResponse(
        status_code=200,
        content={
            "message": "Please use POST /api/call-analytics endpoint",
            "correct_endpoint": "/api/call-analytics",
            "documentation": "Send JSON with {language, audioFormat, audioBase64} and x-api-key header"
        }
    )


# ── Run ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
