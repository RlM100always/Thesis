"""B-SMART operational FastAPI app; legacy research models retired October 2026."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import utf8_console  # noqa: E402,F401  — UTF-8 stdout before any printing

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from .app_routes import router as app_router  # noqa: E402
from .auth_routes import router as auth_router  # noqa: E402
from .commerce_routes import router as commerce_router  # noqa: E402
from .directory_routes import router as directory_router  # noqa: E402
from .finance_routes import router as finance_router  # noqa: E402
from .data_import_routes import router as data_import_router  # noqa: E402
from .analytics_routes import router as analytics_router  # noqa: E402
from .bsmart_routes import router as bsmart_router  # noqa: E402
from .audit_routes import router as audit_router  # noqa: E402
from .batch_routes import router as batch_router  # noqa: E402
from .insights_routes import router as insights_router  # noqa: E402
from .bulk_import_routes import router as bulk_import_router  # noqa: E402
from .planning_routes import router as planning_router  # noqa: E402
from .receivables_routes import router as receivables_router  # noqa: E402
from .insights_advanced_routes import router as insights_advanced_router  # noqa: E402
from .accounting_routes import router as accounting_router  # noqa: E402
from .approval_routes import router as approval_router  # noqa: E402
from .stock_count_routes import router as stock_count_router  # noqa: E402
from .order_routes import router as order_router, public_router as public_order_router  # noqa: E402
from .purchase_return_routes import router as purchase_return_router  # noqa: E402
from .reference_routes import router as reference_router  # noqa: E402
from .integration_routes import router as integration_router  # noqa: E402
from .loyalty_routes import router as loyalty_router  # noqa: E402
from .platform_routes import router as platform_router  # noqa: E402
from .admin_platform_routes import router as admin_platform_router  # noqa: E402
from .shift_routes import router as shift_router  # noqa: E402
from .ticket_routes import router as ticket_router  # noqa: E402
from .team_chat_routes import router as team_chat_router  # noqa: E402
from .assistant_routes import router as assistant_router  # noqa: E402
from .lead_routes import router as lead_router  # noqa: E402
from .feedback_routes import router as feedback_router  # noqa: E402
from .notification_routes import router as notification_router  # noqa: E402
from .attendance_routes import router as attendance_router  # noqa: E402
from .leave_routes import router as leave_router  # noqa: E402
from .roster_routes import router as roster_router  # noqa: E402
from .commission_routes import router as commission_router  # noqa: E402
from .target_routes import router as target_router  # noqa: E402
from .delivery_routes import router as delivery_router  # noqa: E402
from .advance_routes import router as advance_router  # noqa: E402
from .payroll_routes import router as payroll_router  # noqa: E402
from .health_score_routes import router as health_score_router  # noqa: E402
from .mission_queue_routes import router as mission_queue_router  # noqa: E402
from .reservation_routes import router as reservation_router  # noqa: E402
from .store_routes import router as store_router, public_router as public_store_router  # noqa: E402
from .store_customer_routes import router as sc_router, biz_router as sc_biz_router
from .payment_routes import router as payment_router
from .coupon_routes import router as coupon_router, public_router as public_coupon_router
from .review_routes import router as review_router
from .research_portal_routes import router as research_portal_router  # noqa: E402
from .database import create_schema, SessionLocal  # noqa: E402
from .schemas import Health  # noqa: E402

app = FastAPI(
    title="B-SMART Bangladesh SME Business Platform",
    description="Operational shop software. Previous ML artifacts were archived; no new research model has been trained.",
    version="3.0.0-reset",
)

# The Vite dev server runs on a different origin, so the browser needs
# explicit permission. Ports 5173/5174 are Vite's default and its fallback.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(app_router)
app.include_router(commerce_router)
app.include_router(directory_router)
app.include_router(finance_router)
app.include_router(data_import_router)
app.include_router(analytics_router)
app.include_router(bsmart_router)
app.include_router(audit_router)
app.include_router(batch_router)
app.include_router(insights_router)
app.include_router(bulk_import_router)
app.include_router(planning_router)
app.include_router(receivables_router)
app.include_router(insights_advanced_router)
app.include_router(accounting_router)
app.include_router(approval_router)
app.include_router(stock_count_router)
app.include_router(order_router)
app.include_router(public_order_router)
app.include_router(purchase_return_router)
app.include_router(reference_router)
app.include_router(integration_router)
app.include_router(loyalty_router)
app.include_router(platform_router)
app.include_router(admin_platform_router)
app.include_router(shift_router)
app.include_router(ticket_router)
app.include_router(lead_router)
app.include_router(feedback_router)
app.include_router(notification_router)
app.include_router(attendance_router)
app.include_router(leave_router)
app.include_router(roster_router)
app.include_router(commission_router)
app.include_router(target_router)
app.include_router(delivery_router)
app.include_router(advance_router)
app.include_router(payroll_router)
app.include_router(health_score_router)
app.include_router(mission_queue_router)
app.include_router(reservation_router)
app.include_router(store_router)
app.include_router(public_store_router)
app.include_router(sc_router)
app.include_router(sc_biz_router)
app.include_router(payment_router)
app.include_router(coupon_router)
app.include_router(public_coupon_router)
app.include_router(review_router)
app.include_router(team_chat_router)
app.include_router(assistant_router)
app.include_router(research_portal_router)

# Serve chat file uploads as static files
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles
_chat_upload_dir = _Path(__file__).parent.parent / "uploads" / "chat"
_chat_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/app/messages/uploads", _StaticFiles(directory=str(_chat_upload_dir)), name="chat_uploads")


@app.on_event("startup")
def initialize_application_database():
    """Create the development schema; Alembic will own production upgrades."""
    create_schema()
    from .presentation_demo import ensure_presentation_demo
    ensure_presentation_demo()
    _seed_site_defaults()


def _seed_site_defaults():
    """Insert any missing SiteContent rows from SITE_DEFAULTS on first boot."""
    import json
    from sqlalchemy import select
    from .domain_models import SiteContent
    from .site_defaults import SITE_DEFAULTS
    db = SessionLocal()
    try:
        existing = {r.key for r in db.scalars(select(SiteContent))}
        for key, value in SITE_DEFAULTS.items():
            if key not in existing:
                db.add(SiteContent(key=key, value_json=json.dumps(value, ensure_ascii=False)))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.get("/health", response_model=Health, tags=["system"])
def health():
    return {"status": "ok", "artifacts_loaded": False,
            "detail": "Research models reset; awaiting new synthetic dataset integration."}


@app.get("/", tags=["system"])
def root():
    if _frontend_dist.is_dir():
        return _FileResponse(_frontend_dist / "index.html")
    return {"name": "AI-Powered Business Analytics API", "docs": "/docs", "health": "/health"}


from fastapi.responses import FileResponse as _FileResponse
from fastapi import HTTPException as _HTTPException
_frontend_dist = _Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", _StaticFiles(directory=str(_frontend_dist / "assets")), name="frontend_assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa(full_path: str):
    if not _frontend_dist.is_dir() or full_path.startswith("api/"):
        raise _HTTPException(status_code=404)
    path = (_frontend_dist / full_path).resolve()
    if path.is_relative_to(_frontend_dist.resolve()) and path.is_file():
        return _FileResponse(path)
    return _FileResponse(_frontend_dist / "index.html")
