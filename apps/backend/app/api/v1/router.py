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
from app.modules.client_auth.router import router as client_auth_router
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
from app.modules.promo_codes.router import router as promo_codes_router
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
from app.modules.schedule.router import (
    recurring_templates_router,
    schedule_router,
    time_off_router,
)
from app.modules.trainers.router import router as trainers_router
from app.modules.users.router import router as users_router
from app.modules.visits.router import router as visits_router

v1 = APIRouter()

# Phase 64 FRZ-03 — tags now declared on each APIRouter; aggregator no longer
# passes tags= per D-64-TAG-ORDER / PATTERNS.md Notes-for-Planner #1.
v1.include_router(auth_router, prefix="/auth")
v1.include_router(clients_router, prefix="/clients")
v1.include_router(plans_router, prefix="/membership-plans")
v1.include_router(memberships_router, prefix="/memberships")
v1.include_router(
    online_payments_router,
    prefix="/online-payments",
)
v1.include_router(payments_router, prefix="/payments")
v1.include_router(promo_codes_router, prefix="/promo-codes")
v1.include_router(payroll_router, prefix="/payroll")
v1.include_router(
    pt_package_plans_router,
    prefix="/pt-package-plans",
)
v1.include_router(pt_packages_router, prefix="/pt-packages")
v1.include_router(pt_sessions_router, prefix="/pt-sessions")
v1.include_router(
    pt_sessions_package_scoped_router,
    prefix="/pt-packages",
)
v1.include_router(schedule_router, prefix="/trainer-slots")
v1.include_router(
    recurring_templates_router,
    prefix="/recurring-templates",
)
v1.include_router(time_off_router, prefix="/time-off")
v1.include_router(bookings_router, prefix="/bookings")
# Per-client bookings — mounted under /clients per BOOK-08 locked contract;
# implementation lives in bookings/router.py (client_scoped_bookings_router)
# to keep clients/ dependency-leaf. Mirrors pt_sessions_package_scoped_router
# composition pattern above. Resolves Phase 38 verifier Gap #2.
v1.include_router(
    client_scoped_bookings_router,
    prefix="/clients",
)
v1.include_router(trainers_router, prefix="/trainers")
v1.include_router(users_router, prefix="/users")
v1.include_router(visits_router, prefix="/visits")
v1.include_router(reports_router, prefix="/reports")
v1.include_router(audit_log_router, prefix="/audit-log")

# Phase 68 CAUTH-01..06 / CISO-01..05 — client auth + profile self-service.
# Mounted before /_internal so client paths live under /api/v1/client (D-10).
v1.include_router(client_auth_router, prefix="/client")

# Phase 69 CHOME-01..03, CHIST-01..03, CPLAN-01..03 — client read endpoints.
# Mounted at /api/v1/client alongside the Phase-68 client_auth_router (same prefix).
# Tags declared on client_portal_router itself (D-64-TAG-ORDER).
# FastAPI merges both routers correctly — disjoint sub-paths (D-20-MODULE).
from app.modules.client_portal.router import router as client_portal_router  # noqa: E402

v1.include_router(client_portal_router, prefix="/client")

# Phase 82 LOYL-01/LOYL-02 — loyalty client reads.
# Mounted at /api/v1/client (same prefix as client_portal_router) to expose
# /api/v1/client/loyalty/balance and /api/v1/client/loyalty/history.
# Separate router avoids a client_portal→loyalty cross-module edge (D-20-MODULE).
from app.modules.loyalty.router import router as loyalty_router  # noqa: E402

v1.include_router(loyalty_router, prefix="/client")

# Phase 86 GYM-01/GYM-02 — gym-info client read + owner write.
# Client read mounted at /api/v1/client/gym (require_client gate — GYM-01).
# Owner write mounted at /api/v1/gym (require_permission(EDIT, GYM) + verify_csrf — GYM-02).
# Separate routers avoid a cross-module edge and keep the two distinct auth gates clean
# (D-20-MODULE). client_router prefix "/client" → /api/v1/client/gym;
# owner_router prefix "/gym" → /api/v1/gym.
from app.modules.gym.router import client_router as gym_client_router  # noqa: E402
from app.modules.gym.router import owner_router as gym_owner_router  # noqa: E402

v1.include_router(gym_client_router, prefix="/client")
v1.include_router(gym_owner_router, prefix="/gym")

# Phase 108 CFG-02/CFG-03/CFG-04 — settings domain (hours / booking / notifications).
# All endpoints owner-only: require_permission(EDIT, SETTINGS) + verify_csrf on PUT.
# Owner-only GETs gated on require_permission(VIEW, SETTINGS) — both in OWNER_ONLY.
# Mounted at /api/v1/settings (D-20-MODULE; independent from gym module).
from app.modules.settings.router import owner_router as settings_owner_router  # noqa: E402

v1.include_router(settings_owner_router, prefix="/settings")

# Phase 96 REFER-01/REFER-02/REFER-03/REFER-07 — referral domain.
# Public resolver mounted at /api/v1 (no prefix — path is /i/{code}).
# Client endpoints mounted at /api/v1/client (same prefix as loyalty — D-20-MODULE).
# Owner config mounted at /api/v1/referral (require_permission + verify_csrf).
from app.modules.referrals.router import client_router as referral_client_router  # noqa: E402
from app.modules.referrals.router import owner_router as referral_owner_router  # noqa: E402
from app.modules.referrals.router import public_router as referral_public_router  # noqa: E402

v1.include_router(referral_public_router)  # /api/v1/i/{code}
v1.include_router(referral_client_router, prefix="/client")  # /api/v1/client/referral/*
v1.include_router(referral_owner_router, prefix="/referral")  # /api/v1/referral/config

# Phase 87 INBOX-01/INBOX-02 — notification inbox + push-token registration.
# Mounted at /api/v1/client (same prefix as client_portal_router) to expose
# /api/v1/client/notifications and /api/v1/client/push-tokens.
# Separate router avoids a client_portal→notifications cross-module edge (D-20-MODULE).
from app.modules.notifications.router import router as notifications_router  # noqa: E402

v1.include_router(notifications_router, prefix="/client")

# Phase 90 MSG-01..04 / RT-01..04 — messaging REST + WS endpoint.
# Mounted at /api/v1/client (same prefix as client_portal_router) to expose
# /api/v1/client/messages and (Plan 03) the WS endpoint /api/v1/client/ws/messages.
# Separate router avoids a client_portal→messaging cross-module edge (D-20-MODULE).
from app.modules.messaging.router import router as messaging_router  # noqa: E402

v1.include_router(messaging_router, prefix="/client")

# Phase 116 MSG-01/02 — staff-side messaging REST (inbox list + reply + mark-read).
# Mounted at /api/v1/messages (separate from /api/v1/client to avoid cross-module edge;
# D-20-MODULE; same split pattern as client_portal_router / notifications_router above).
# Final paths: /api/v1/messages/threads, /api/v1/messages/threads/{id}/reply|read.
from app.modules.messaging.staff_router import router as staff_messaging_router  # noqa: E402

v1.include_router(staff_messaging_router, prefix="/messages")

# Phase 42 EMAIL-07 / D-42-17 — _internal namespace established here.
# Transport-layer endpoints (provider webhooks, ops callbacks) sit under
# /api/v1/_internal/* with their own auth model (HMAC signature in
# X-Email-Webhook-Signature for the email webhook). Future infrastructure
# callbacks (ЮKassa, SMS providers, ...) land here, NOT under business
# modules.
v1.include_router(
    email_webhook_router,
    prefix="/_internal/email",
)

# Phase 50 WH-01 / D-50-03 — ЮKassa webhook intake. Second /_internal/* inhabitant.
# Anonymous-by-design (IP allowlist only — see router.py module docstring + the
# Phase 48-shipped verify_yookassa_ip Depends).
v1.include_router(
    yookassa_webhook_router,
    prefix="/_internal/yookassa",
)
