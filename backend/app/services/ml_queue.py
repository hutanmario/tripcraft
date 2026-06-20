from __future__ import annotations

from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job

from app.config import settings


def get_redis_connection() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        health_check_interval=30,
    )


def get_ml_queue() -> Queue:
    connection = get_redis_connection()
    connection.ping()
    return Queue(settings.RQ_ML_QUEUE_NAME, connection=connection)


def enqueue_photo_analysis(files_data: list[dict], user_id: int) -> Job:
    queue = get_ml_queue()
    return queue.enqueue(
        "app.workers.photo_analysis.analyze_photos_job",
        files_data,
        user_id,
        job_timeout=settings.RQ_ML_JOB_TIMEOUT_SECONDS,
        result_ttl=settings.RQ_ML_RESULT_TTL_SECONDS,
        failure_ttl=settings.RQ_ML_FAILURE_TTL_SECONDS,
        meta={"user_id": user_id},
        description=f"Photo analysis for user {user_id}",
    )


def fetch_photo_analysis_job(job_id: str) -> Job:
    return Job.fetch(job_id, connection=get_redis_connection())


def normalize_job_status(status: Any) -> str:
    value = getattr(status, "value", status)
    return str(value).lower()


def redis_unavailable(exc: Exception) -> bool:
    return isinstance(exc, RedisError)
