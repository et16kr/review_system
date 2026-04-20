from __future__ import annotations

from redis import Redis
from rq import Queue

from review_bot.config import get_settings


def get_redis_connection() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url)


def get_queue(name: str) -> Queue:
    return Queue(name, connection=get_redis_connection())


def get_detect_queue() -> Queue:
    settings = get_settings()
    return get_queue(settings.queue_detect_name)


def get_publish_queue() -> Queue:
    settings = get_settings()
    return get_queue(settings.queue_publish_name)


def get_sync_queue() -> Queue:
    settings = get_settings()
    return get_queue(settings.queue_sync_name)
