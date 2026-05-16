"""PT-sessions service — orchestration between router and repository (Phase 34).

PT-sessions are orthogonal to visits (PT-20 / Q3 default): recording does NOT
INSERT into visits; check-in does NOT INSERT into pt_sessions. Enforced by
ABSENCE — no service code in this file touches visits.

D-34-11a carve-out: `cancel_pt_session` (Plan 34-03) performs a reverse
transition `exhausted → active` on the parent pt_package via raw `text()` SQL
predicate-gated UPDATE in `pt_sessions.repository`. This bypass is NOT in the
global `PT_PACKAGE_STATUS_TRANSITIONS` FSM (Phase 33 D-33-04 is forward-only).
The locally-scoped invariant "we just freed one balance unit from an
exhausted package" makes the reverse flip safe under `WHERE status='exhausted'`.

D-34-04a: ALL cross-module SQL against `pt_packages` uses raw `text()` from
`pt_sessions.repository` (NEVER `from app.modules.pt_packages import ...`)
to keep the `modules-independent` importlinter contract clean.

Discipline invariants (Phase 30 walkers must remain green):
  - SVC001 caller-owns-txn (`tests/unit/test_service_commit_gate.py`):
    every public mutating orchestrator MUST end with `await session.commit()`.
  - audit.emit literal-string AST gate (INFRA-11 /
    `tests/unit/test_audit_taxonomy.py`): every `emit()` call uses literal
    strings for `event` and `resource_type`.
  - audit_payloads.py `extra='forbid'` validation (D-30-03): emit kwargs
    MUST match `PtSessionRecordedPayload` / `PtSessionCancelledPayload` /
    `PtPackageExhaustedPayload` schemas verbatim.

Plan 34-01 lands the module-level docstring + import surface + error class
hierarchy only. Public orchestrators are filled by 34-02 / 34-03:
  - 34-02: `record_pt_session` (PT-15 / PT-16 / PT-17).
  - 34-03: `cancel_pt_session` (PT-18), `get_pt_session` (PT-19),
    `list_sessions_by_pt_package` (PT-19).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta  # noqa: F401 — used by 34-02/34-03
from uuid import UUID  # noqa: F401 — used by 34-02/34-03

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401 — used by 34-02/34-03

from app.core import audit  # noqa: F401 — used by 34-02/34-03
from app.core.dependencies import (  # noqa: F401 — used by 34-02/34-03
    CurrentUser,
    resolve_trainer_by_id,
)
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.core.pagination import PaginatedData  # noqa: F401 — used by 34-03
from app.core.permissions import Role  # noqa: F401 — used by 34-02/34-03
from app.modules.pt_sessions import repository  # noqa: F401 — used by 34-02/34-03
from app.modules.pt_sessions.constants import (  # noqa: F401 — used by 34-02/34-03
    BACKDATING_WINDOW_DAYS_RECEPTION,
    CANCEL_WINDOW_HOURS_RECEPTION,
)
from app.modules.pt_sessions.schemas import (  # noqa: F401 — used by 34-02/34-03
    PtSessionCancelRequest,
    PtSessionCreateRequest,
    PtSessionListByPackageQuery,
    PtSessionResponse,
)

# ---------------------------------------------------------------------------
# Error classes (D-34-18 catalogue).
#
# Mirror pt_packages.service error-class hierarchy. Each class carries a
# stable `code` (translated by the global exception handler into the
# response envelope `{error.code}` field) and an HTTP `status_code`.
# ---------------------------------------------------------------------------


class PtSessionNotFoundError(NotFoundError):
    """Raised by cancel_pt_session / get_pt_session when the id does not exist."""

    code = "pt_session_not_found"
    status_code = 404


class PtPackageNotFoundError(NotFoundError):
    """Raised when fetch_pt_package_metadata returns None
    (record_pt_session / cancel_pt_session pre-mutation guard)."""

    code = "pt_package_not_found"
    status_code = 404


class PtPackageNotActiveError(ConflictError):
    """Raised when fetch_pt_package_metadata returns status != 'active'
    (record_pt_session pre-decrement guard; race-loser uses
    PtPackageExhaustedError instead)."""

    code = "pt_package_not_active"
    status_code = 409


class PtPackageExhaustedError(ConflictError):
    """Raised when atomic_decrement_pt_package returns None — i.e. the
    `sessions_remaining > 0 AND status='active'` predicate excluded the row
    (PT-16 / D-34-04a race-loser path)."""

    code = "pt_package_exhausted"
    status_code = 409


class TrainerNotFoundError(NotFoundError):
    """Raised by record_pt_session when the TrainerById Protocol slot
    resolves to None for `trainer_id`."""

    code = "trainer_not_found"
    status_code = 404


class TrainerInactiveError(ValidationAppError):
    """Raised by record_pt_session when the resolved trainer has
    `is_active=False`. 422 (semantic-validation) not 409 (state-conflict)
    per Phase 31 convention."""

    code = "trainer_inactive"
    status_code = 422


class PerformedAtInFutureError(ValidationAppError):
    """Raised by record_pt_session when `performed_at > datetime.now(UTC)`.
    Applies to BOTH roles (owner-unlimited is past-direction only —
    D-34-06). Distinct from `performed_at_out_of_window` for UI clarity."""

    code = "performed_at_in_future"
    status_code = 422


class PerformedAtOutOfWindowError(ValidationAppError):
    """Raised by record_pt_session when reception backdates more than
    BACKDATING_WINDOW_DAYS_RECEPTION (B-11 / D-34-06). Owner unlimited
    in the past direction."""

    code = "performed_at_out_of_window"
    status_code = 422


class PtSessionAlreadyCancelledError(ConflictError):
    """Raised by cancel_pt_session when `cancelled_at IS NOT NULL`
    already. Idempotency-Key replay returns the cached envelope first
    (D-34-10); this is the second-line guard for different keys against
    the same row."""

    code = "already_cancelled"
    status_code = 409


class CancelWindowExpiredError(ForbiddenError):
    """Raised by cancel_pt_session when reception attempts to cancel
    >CANCEL_WINDOW_HOURS_RECEPTION after `created_at` (B-12 / D-34-07).
    Owner is anytime. 403 not 409 — actor authorisation issue, not state
    conflict (mirrors OWNER_ONLY 403 mapping convention)."""

    code = "cancel_window_expired"
    status_code = 403
