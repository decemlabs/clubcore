"""v1 router. Aggregates business module routers under /api/v1 (D-16).

health.router is mounted on the parent api router at root (Phase 2 D-14
Kubernetes contract), NOT under v1. This file therefore only mounts
business modules.
"""

from fastapi import APIRouter

from app.api.v1._internal.email.router import router as email_webhook_router
from app.api.v1._internal.yookassa.router import router as yookassa_webhook_router
from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import bookings_router, client_scoped_bookings_router
from app.modules.clients.router import router as clients_router
from app.modules.memberships.router import (
    memberships_router,
)
from app.modules.memberships.router import (
    router as plans_router,
)
from app.modules.online_payments.router import router as online_payments_router
from app.modules.payments.router import router as payments_router
from app.modules.payroll.router import router as payroll_router
from app.modules.pt_packages.router import (
    plans_router as pt_package_plans_router,
)
from app.modules.pt_packages.router import (
    pt_packages_router,
)
from app.modules.pt_sessions.router import (
    package_scoped_router as pt_sessions_package_scoped_router,
)
from app.modules.pt_sessions.router import (
    pt_sessions_router,
)
from app.modules.reports.router import audit_log_router
from app.modules.reports.router import router as reports_router
from app.modules.schedule.router import schedule_router
from app.modules.trainers.router import router as trainers_router
from app.modules.users.router import router as users_router
from app.modules.visits.router import router as visits_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(
    online_payments_router,
    prefix="/online-payments",
    tags=["online-payments"],
)
v1.include_router(payments_router, prefix="/payments", tags=["payments"])
v1.include_router(payroll_router, prefix="/payroll", tags=["payroll"])
v1.include_router(
    pt_package_plans_router,
    prefix="/pt-package-plans",
    tags=["pt-package-plans"],
)
v1.include_router(pt_packages_router, prefix="/pt-packages", tags=["pt-packages"])
v1.include_router(pt_sessions_router, prefix="/pt-sessions", tags=["pt-sessions"])
v1.include_router(
    pt_sessions_package_scoped_router,
    prefix="/pt-packages",
    tags=["pt-sessions"],
)
v1.include_router(schedule_router, prefix="/trainer-slots", tags=["schedule"])
v1.include_router(bookings_router, prefix="/bookings", tags=["bookings"])
# Per-client bookings — mounted under /clients per BOOK-08 locked contract;
# implementation lives in bookings/router.py (client_scoped_bookings_router)
# to keep clients/ dependency-leaf. Mirrors pt_sessions_package_scoped_router
# composition pattern above. Resolves Phase 38 verifier Gap #2.
v1.include_router(
    client_scoped_bookings_router,
    prefix="/clients",
    tags=["bookings"],
)
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(users_router, prefix="/users", tags=["users"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
v1.include_router(reports_router, prefix="/reports", tags=["reports"])
v1.include_router(audit_log_router, prefix="/audit-log", tags=["audit-log"])

# Phase 42 EMAIL-07 / D-42-17 — _internal namespace established here.
# Transport-layer endpoints (provider webhooks, ops callbacks) sit under
# /api/v1/_internal/* with their own auth model (HMAC signature in
# X-Email-Webhook-Signature for the email webhook). Future infrastructure
# callbacks (ЮKassa, SMS providers, ...) land here, NOT under business
# modules.
v1.include_router(
    email_webhook_router,
    prefix="/_internal/email",
    tags=["_internal"],
)

# Phase 50 WH-01 / D-50-03 — ЮKassa webhook intake. Second /_internal/* inhabitant.
# Anonymous-by-design (IP allowlist only — see router.py module docstring + the
# Phase 48-shipped verify_yookassa_ip Depends).
v1.include_router(
    yookassa_webhook_router,
    prefix="/_internal/yookassa",
    tags=["_internal"],
)
