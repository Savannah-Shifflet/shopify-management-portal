from celery import Celery
from celery.schedules import crontab
from app.config import settings

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
    # Windows: prefork pool uses Unix semaphores which fail on Windows; solo runs tasks
    # in-process without multiprocessing. Set CELERYD_POOL=threads in .env to use threads instead.
    worker_pool="solo",
    task_routes={
        "app.workers.import_tasks.*": {"queue": "imports"},
        "app.workers.scrape_tasks.*": {"queue": "scraping"},
        "app.workers.enrichment_tasks.*": {"queue": "enrichment"},
        "app.workers.pricing_tasks.*": {"queue": "pricing"},
        "app.workers.sync_tasks.*": {"queue": "sync"},
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
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.workers.import_tasks",
    "app.workers.enrichment_tasks",
    "app.workers.scrape_tasks",
    "app.workers.pricing_tasks",
    "app.workers.sync_tasks",
])
