import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import SessionLocal
from app.routers import products, suppliers, pricing, imports, enrichment, sync, auth, templates
from app.routers import settings as settings_router
from app.routers import email_templates, reorders, audit, store_settings
from app.routers import analytics, webhooks


def _seed_stub_user():
    """Ensure the dev stub user exists so existing data keeps working after auth is added."""
    from app.models.user import User
    from passlib.context import CryptContext

    STUB_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    STUB_EMAIL = "dev@localhost.com"
    db = SessionLocal()
    try:
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        existing = db.query(User).filter(User.id == STUB_UUID).first()
        if existing:
            changed = False
            if existing.email != STUB_EMAIL:
                existing.email = STUB_EMAIL
                changed = True
            if not existing.hashed_password or not pwd_ctx.verify("dev-password", existing.hashed_password):
                existing.hashed_password = pwd_ctx.hash("dev-password")
                changed = True
            if changed:
                db.commit()
        else:
            db.add(User(id=STUB_UUID, email=STUB_EMAIL, name="Dev User", hashed_password=pwd_ctx.hash("dev-password")))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_stub_user()
    yield


app = FastAPI(
    title="Product Manager API",
    description="AI-powered product management for e-commerce authorized dealers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
os.makedirs(settings.storage_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.storage_path), name="uploads")

# Routers
app.include_router(auth.router)
app.include_router(settings_router.router)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(pricing.router)
app.include_router(imports.router)
app.include_router(enrichment.router)
app.include_router(sync.router)
app.include_router(templates.router)
app.include_router(email_templates.router)
app.include_router(reorders.router)
app.include_router(audit.router)
app.include_router(store_settings.router)
app.include_router(analytics.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
