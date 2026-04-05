"""IMAP inbox polling — matches inbound emails to known supplier addresses."""
import email
import email.utils
import imaplib
import logging
from datetime import datetime
from email.header import decode_header

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _decode_mime_words(s: str) -> str:
    parts = decode_header(s)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_body(msg) -> str:
    """Extract plain text body; fall back to HTML."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    return ""


def run_imap_sync(user_id: str, db) -> dict:
    """
    Core IMAP sync logic shared between the Celery task and the manual /sync-inbox endpoint.
    Polls UNSEEN messages, matches them to known supplier email addresses, and logs them.
    Returns {"new_emails": N, "matched_suppliers": K} or {"error": "..."}.
    """
    from uuid import UUID
    from app.models.store_settings import StoreSettings
    from app.models.supplier import Supplier
    from app.models.supplier_email import SupplierEmail

    uid = UUID(user_id)
    settings = db.query(StoreSettings).filter(StoreSettings.user_id == uid).first()
    if not settings or not settings.imap_host or not settings.imap_user:
        return {"new_emails": 0, "matched_suppliers": 0, "error": "IMAP not configured"}

    # Build lookup: lowercase email → Supplier
    suppliers = db.query(Supplier).filter(Supplier.user_id == uid).all()
    email_to_supplier = {
        s.company_email.lower(): s
        for s in suppliers
        if s.company_email
    }
    if not email_to_supplier:
        return {"new_emails": 0, "matched_suppliers": 0}

    new_emails = 0
    matched_set: set[str] = set()

    try:
        folder = settings.imap_folder or "INBOX"
        with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port or 993) as mail:
            mail.login(settings.imap_user, settings.imap_password)
            mail.select(folder, readonly=False)

            # Fetch UNSEEN messages only (efficient for recurring polls)
            _, data = mail.search(None, "UNSEEN")
            uid_list = data[0].split()

            for uid_bytes in uid_list:
                try:
                    _, msg_data = mail.fetch(uid_bytes, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    message_id = msg.get("Message-ID", "").strip()

                    # Skip if already logged (dedup by Message-ID)
                    if message_id:
                        existing = db.query(SupplierEmail).filter(
                            SupplierEmail.message_id == message_id
                        ).first()
                        if existing:
                            continue

                    # Match to a known supplier by From address
                    from_header = msg.get("From", "")
                    from_email = email.utils.parseaddr(from_header)[1].lower()
                    supplier = email_to_supplier.get(from_email)
                    if not supplier:
                        continue

                    # Decode subject
                    raw_subject = msg.get("Subject", "")
                    decoded_subject = _decode_mime_words(raw_subject)

                    # Extract body
                    body = _extract_body(msg)

                    # Parse date
                    date_str = msg.get("Date", "")
                    try:
                        sent_at = email.utils.parsedate_to_datetime(date_str)
                        # Make naive (strip tzinfo) for consistent storage
                        sent_at = sent_at.replace(tzinfo=None)
                    except Exception:
                        sent_at = datetime.utcnow()

                    record = SupplierEmail(
                        supplier_id=supplier.id,
                        direction="INBOUND",
                        subject=decoded_subject,
                        body=body,
                        sent_at=sent_at,
                        message_id=message_id or None,
                    )
                    db.add(record)
                    new_emails += 1
                    matched_set.add(str(supplier.id))

                except Exception as e:
                    logger.warning(f"Failed to process message {uid_bytes}: {e}")
                    continue

        if new_emails:
            db.commit()

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP auth/connection error for user {user_id}: {e}")
        return {"new_emails": 0, "matched_suppliers": 0, "error": f"IMAP error: {str(e)}"}
    except Exception as e:
        logger.error(f"IMAP sync failed for user {user_id}: {e}")
        return {"new_emails": 0, "matched_suppliers": 0, "error": str(e)}

    return {"new_emails": new_emails, "matched_suppliers": len(matched_set)}


@celery_app.task(name="app.workers.email_tasks.sync_all_inboxes")
def sync_all_inboxes():
    """Poll IMAP for all users who have IMAP configured. Runs every 15 minutes."""
    from app.database import SessionLocal
    from app.models.store_settings import StoreSettings

    db = SessionLocal()
    total_new = 0
    users_synced = 0
    try:
        configured = db.query(StoreSettings).filter(
            StoreSettings.imap_host.isnot(None),
            StoreSettings.imap_user.isnot(None),
        ).all()
        for s in configured:
            result = run_imap_sync(str(s.user_id), db)
            total_new += result.get("new_emails", 0)
            if "error" not in result:
                users_synced += 1
        return {"users_synced": users_synced, "total_new_emails": total_new}
    finally:
        db.close()
