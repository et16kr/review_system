from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, index=True)
    trigger: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    findings: Mapped[list[ReviewFinding]] = relationship(back_populates="review_run")


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_run_id: Mapped[int] = mapped_column(ForeignKey("review_runs.id"), index=True)
    pr_id: Mapped[int] = mapped_column(Integer, index=True)
    fingerprint: Mapped[str] = mapped_column(String(500), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_no: Mapped[str] = mapped_column(String(100))
    source_family: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    publication_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    review_run: Mapped[ReviewRun] = relationship(back_populates="findings")
    publications: Mapped[list[FindingPublication]] = relationship(back_populates="finding")


class FindingPublication(Base):
    __tablename__ = "finding_publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, index=True)
    review_run_id: Mapped[int] = mapped_column(ForeignKey("review_runs.id"))
    finding_id: Mapped[int] = mapped_column(ForeignKey("review_findings.id"))
    batch_no: Mapped[int] = mapped_column(Integer)
    comment_id: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    finding: Mapped[ReviewFinding] = relationship(back_populates="publications")
