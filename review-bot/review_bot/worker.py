from __future__ import annotations

from rq import Worker

from review_bot.bot.review_runner import ReviewRunner
from review_bot.db.session import SessionLocal, init_db
from review_bot.errors import ReviewBotError
from review_bot.queueing import (
    get_detect_queue,
    get_publish_queue,
    get_redis_connection,
    get_sync_queue,
)


def execute_detect_job(review_run_id: str) -> None:
    init_db()
    session = SessionLocal()
    try:
        runner = ReviewRunner()
        runner.execute_detect_phase(session, review_run_id)
        session.commit()
        try:
            get_publish_queue().enqueue(execute_publish_job, review_run_id)
        except Exception as exc:
            _mark_followup_enqueue_failure(
                review_run_id,
                stage="publish",
                exc=exc,
            )
            raise
    finally:
        session.close()


def execute_publish_job(review_run_id: str) -> None:
    init_db()
    session = SessionLocal()
    try:
        runner = ReviewRunner()
        runner.execute_publish_phase(session, review_run_id)
        session.commit()
        try:
            get_sync_queue().enqueue(execute_sync_job, review_run_id)
        except Exception as exc:
            _mark_followup_enqueue_failure(
                review_run_id,
                stage="sync",
                exc=exc,
            )
            raise
    finally:
        session.close()


def execute_sync_job(review_run_id: str) -> None:
    init_db()
    session = SessionLocal()
    try:
        runner = ReviewRunner()
        runner.execute_sync_phase(session, review_run_id)
        session.commit()
    finally:
        session.close()


def _mark_followup_enqueue_failure(review_run_id: str, *, stage: str, exc: Exception) -> None:
    init_db()
    session = SessionLocal()
    try:
        runner = ReviewRunner()
        review_run = runner._get_review_run(session, review_run_id)  # noqa: SLF001
        error = ReviewBotError(
            f"Failed to enqueue {stage} follow-up job: {exc}",
            category="queue",
            retryable=True,
        )
        review_run.status = "failed"
        review_run.error_category = error.category
        review_run.error_message = str(error)
        runner._record_dead_letter(  # noqa: SLF001
            session,
            review_run=review_run,
            stage=stage,
            error_category=error.category,
            error_message=str(error),
            replayable=error.retryable,
            payload={"review_run_id": review_run_id},
        )
        session.commit()
    finally:
        session.close()


def main() -> None:
    init_db()
    connection = get_redis_connection()
    worker = Worker(
        [get_detect_queue(), get_publish_queue(), get_sync_queue()],
        connection=connection,
    )
    worker.work()
