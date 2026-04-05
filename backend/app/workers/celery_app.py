from celery import Celery
from celery.schedules import crontab
from app.config import settings
import app.models  # noqa: F401 — registers all SQLAlchemy mappers at worker startup

celery_app = Celery(
    "shopify_products",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # threads pool works on Windows (unlike prefork which needs Unix fork).
    # Allows multiple tasks to run concurrently — critical for enrich_products_batch
    # which uses asyncio.gather() internally, plus lets beat tasks (email, pricing)
    # run while a batch enrichment is in progress.
    # On Linux production: switch to gevent with higher concurrency (e.g. --concurrency=50).
    worker_pool="threads",
    worker_concurrency=4,  # 4 threads: enough for 1 batch + beat tasks simultaneously
    task_routes={
        "app.workers.import_tasks.*": {"queue": "imports"},
        "app.workers.scrape_tasks.*": {"queue": "scraping"},
        "app.workers.enrichment_tasks.*": {"queue": "enrichment"},
        "app.workers.pricing_tasks.*": {"queue": "pricing"},
        "app.workers.sync_tasks.*": {"queue": "sync"},
        "app.workers.gdpr_tasks.*": {"queue": "default"},
        # enrich_products_batch routes to enrichment queue alongside single-product tasks
    },
    beat_schedule={
        "check-supplier-prices": {
            "task": "app.workers.pricing_tasks.check_all_supplier_prices",
            "schedule": crontab(minute="*/15"),
        },
        "apply-pricing-schedules": {
            "task": "app.workers.pricing_tasks.apply_due_schedules",
            "schedule": crontab(minute="*"),
        },
        "retry-failed-syncs": {
            "task": "app.workers.sync_tasks.retry_failed_syncs",
            "schedule": crontab(minute=0),
        },
        "sync-use-supplier-prices": {
            "task": "app.workers.pricing_tasks.sync_use_supplier_prices",
            "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
        },
        "sync-imap-inboxes": {
            "task": "app.workers.email_tasks.sync_all_inboxes",
            "schedule": crontab(minute="*/15"),
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.workers.import_tasks",
    "app.workers.enrichment_tasks",
    "app.workers.scrape_tasks",
    "app.workers.pricing_tasks",
    "app.workers.sync_tasks",
    "app.workers.email_tasks",
    "app.workers.gdpr_tasks",
])
