"""Celery application.

Inference is slow — a 30-second video is far past an acceptable HTTP request —
so the API only enqueues work and the worker process runs the models.

When ``CELERY_BROKER_URL`` is unset the app switches to eager mode: tasks run
inline in the calling process. That keeps the project runnable with no Redis for
development and tests, while production compose files set the broker and get a
real queue.
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_process_init

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "deepfake_detection",
    broker=settings.celery_broker_url or None,
    backend=settings.celery_result_backend or None,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # redeliver if a worker dies mid-inference
    worker_prefetch_multiplier=1,  # long tasks: do not hoard the queue
    task_time_limit=60 * 20,
    task_soft_time_limit=60 * 18,
    task_always_eager=not settings.queue_enabled,
    task_eager_propagates=False,
    broker_connection_retry_on_startup=True,
)


@worker_process_init.connect
def _load_models(**_kwargs) -> None:
    """Load every model once per worker process, not once per task."""
    from app.ml.registry import warm_up

    logger.info("Warming up detection models: %s", warm_up())
