"""
GDPR data deletion tasks.

Triggered by Shopify mandatory GDPR webhooks:
  - shop/redact     → redact_shop_data   (delete all data for an uninstalled merchant)
  - customers/redact → no-op for this app (no customer PII stored)

Shopify requires shop/redact to be processed within 30 days of receiving the webhook.
This task handles the full cascade deletion asynchronously so the webhook endpoint
can return 200 immediately within Shopify's 5-second timeout.
"""

import logging
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.gdpr_tasks.redact_shop_data", bind=True, max_retries=3)
def redact_shop_data(self, shop_domain: str, shop_id: int | None = None):
    """
    Delete all data belonging to a merchant after they uninstall the app.

    Deletion order respects FK constraints:
      Products (+ variants, images, price_history, alerts, schedules, sync_log, audit_log)
      → Suppliers (+ emails, documents, checklist, reorder_logs)
      → DescriptionTemplates
      → ImportJobs
      → StoreSettings
      → User (anonymised last so we keep the audit trail until everything else is gone)

    SQLAlchemy cascade='all, delete-orphan' handles child rows automatically
    when the parent is deleted, so we only need to delete top-level rows per user.
    """
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.product import Product
    from app.models.supplier import Supplier
    from app.models.description_template import DescriptionTemplate
    from app.models.import_job import ImportJob
    from app.models.store_settings import StoreSettings

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.shopify_store == shop_domain).first()
        if not user:
            logger.info(f"GDPR shop/redact: no user found for shop {shop_domain} — nothing to delete")
            return {"shop": shop_domain, "status": "no_user_found"}

        user_id = user.id
        logger.info(f"GDPR shop/redact: starting deletion for shop={shop_domain} user_id={user_id}")

        # Delete owned rows — cascades handle child tables
        db.query(Product).filter(Product.user_id == user_id).delete(synchronize_session=False)
        db.query(Supplier).filter(Supplier.user_id == user_id).delete(synchronize_session=False)
        db.query(DescriptionTemplate).filter(DescriptionTemplate.user_id == user_id).delete(synchronize_session=False)
        db.query(ImportJob).filter(ImportJob.user_id == user_id).delete(synchronize_session=False)
        db.query(StoreSettings).filter(StoreSettings.user_id == user_id).delete(synchronize_session=False)

        # Delete the user record itself
        db.delete(user)
        db.commit()

        logger.info(f"GDPR shop/redact: completed for shop={shop_domain} user_id={user_id}")
        return {"shop": shop_domain, "user_id": str(user_id), "status": "deleted"}

    except Exception as exc:
        db.rollback()
        logger.error(f"GDPR shop/redact failed for {shop_domain}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
    finally:
        db.close()
