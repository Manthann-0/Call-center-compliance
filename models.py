"""
SQLAlchemy ORM models for the Call Center Compliance system.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Float, JSON, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Call(Base):
    __tablename__ = "calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    language = Column(String(20), nullable=True)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sop_score = Column(Float, nullable=True)  # 0.0–1.0
    sop_breakdown = Column(JSON, nullable=True)  # full sop_validation object
    payment_type = Column(String(50), nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    sentiment = Column(String(20), nullable=True)  # Positive/Neutral/Negative
    keywords = Column(JSON, nullable=True)  # list of strings
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "language": self.language,
            "transcript": self.transcript,
            "summary": self.summary,
            "sop_score": self.sop_score,
            "sop_breakdown": self.sop_breakdown,
            "payment_type": self.payment_type,
            "rejection_reason": self.rejection_reason,
            "sentiment": self.sentiment,
            "keywords": self.keywords,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
