from __future__ import annotations

from rq import Worker

from app.bot.review_runner import ReviewRunner
from app.db.session import SessionLocal, init_db
from app.queueing import get_queue, get_redis_connection


def execute_review_job(review_run_id: int) -> None:
    init_db()
    session = SessionLocal()
    try:
        ReviewRunner().execute_review_run(session, review_run_id)
    finally:
        session.close()


def publish_next_batch_job(pr_id: int) -> None:
    init_db()
    session = SessionLocal()
    try:
        ReviewRunner().publish_next_batch(session, pr_id)
        session.commit()
    finally:
        session.close()


def main() -> None:
    init_db()
    queue = get_queue()
    connection = get_redis_connection()
    worker = Worker([queue], connection=connection)
    worker.work()
