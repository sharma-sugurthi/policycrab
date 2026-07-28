"""
Celery Application — async task queue for long-running AI pipelines.

Why Celery:
  PolicyCrab's LLM pipelines (policy ingestion, claim evaluation, appeal
  generation) take 30-90 seconds — far exceeding Heroku's 30-second HTTP
  timeout.  Celery offloads these to background workers, giving users
  instant feedback and enabling independent scaling.

Broker/Backend: Upstash Redis (free tier: 10K commands/day, 256 MB).
Serialiser: JSON only — no pickle, ever (HIPAA compliance).
"""

from celery import Celery

from app.config import settings

# ── Create Celery App ─────────────────────────────────────────────
celery_app = Celery(
    "policycrab",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# ── Configuration ─────────────────────────────────────────────────
celery_app.conf.update(
    # Serialisation — JSON only (HIPAA: never unpickle untrusted data)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_soft_time_limit=300,    # 5 min soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=600,         # 10 min hard kill
    task_acks_late=True,         # Only ACK after task completes (crash safety)
    worker_prefetch_multiplier=1,  # Don't prefetch — LLM tasks are slow

    # Result backend
    result_expires=3600,         # Results expire after 1 hour
    result_extended=True,        # Store task args/kwargs in result for debugging

    # Task routing — separate queues for different priority levels
    task_routes={
        "app.tasks.policy_tasks.*":    {"queue": "heavy_ai"},
        "app.tasks.claim_tasks.*":     {"queue": "heavy_ai"},
        "app.tasks.email_tasks.*":     {"queue": "email"},
    },
    task_default_queue="default",

    # Retry policy defaults
    task_default_retry_delay=5,
    task_max_retries=3,

    # Broker connection — resilient to transient Redis failures
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 900,   # 15 min — must exceed task_time_limit
    },
)

# ── Auto-discover task modules ────────────────────────────────────
celery_app.autodiscover_tasks(["app.tasks"])
