"""PT-sessions repository — single point of access to the PtSession ORM.

This is the ONLY module in the codebase that imports the PtSession ORM
model from `pt_sessions.models`. Cross-module reads (`pt_packages` metadata)
and cross-module writes (`sessions_remaining` decrement/increment, status
flip `exhausted ↔ active`) go through raw `sa.text()` SQL strings — D-34-04a
keeps the `modules-independent` importlinter contract clean without an
ORM import on the `pt_packages` side.

All cross-module raw SQL statements are marked with
`# noqa: TABLE_REF cross-module SQL per D-34-04a` for grep-ability and use
named parameter binding (`:pt_package_id`) — never f-string interpolation.

Transaction control: NO `session.commit()` and NO `session.flush()` here
(mirrors memberships D-14, pt_packages D-33 caller-owns-txn). The service
layer owns the UoW so it can co-write `audit_log` in the same transaction.

Plan 34-01 lands this header + import surface only. Sale-side helpers
(`atomic_decrement_pt_package`, `atomic_transition_to_exhausted`,
`fetch_pt_package_metadata`, `insert_pt_session`) are filled by 34-02;
cancel/read-side helpers (`get_pt_session`, `mark_cancelled`,
`atomic_increment_pt_package`, `atomic_transition_exhausted_to_active`,
`list_by_pt_package_paginated`) are filled by 34-03.
"""

from __future__ import annotations

from datetime import datetime  # noqa: F401 — used by 34-02/34-03 helpers
from uuid import UUID  # noqa: F401 — used by 34-02/34-03 helpers

import sqlalchemy as sa  # noqa: F401 — used by 34-02/34-03 helpers
from sqlalchemy import Select, func, select  # noqa: F401 — used by 34-02/34-03 helpers
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401 — used by 34-02/34-03 helpers

from app.core.pagination import PaginatedData  # noqa: F401 — used by 34-03
from app.modules.pt_sessions.models import PtSession  # noqa: F401 — used by 34-02/34-03
from app.modules.pt_sessions.schemas import (  # noqa: F401 — used by 34-03
    PtSessionListByPackageQuery,
)
