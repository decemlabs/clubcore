"""ARQ scheduled-jobs sub-namespace (Phase 18 ARQ-01).

Per Phase 7 D-06 / Phase 18 D-09: workers MAY import a single owning module's
service layer. Each `app/workers/scheduled/<job>.py` file is the I/O fanout
for that owning module's recurring task — the file name encodes the job, the
import target encodes the module.

Examples (current and future):
  - expire_memberships.py        -> app.modules.memberships.service (Phase 18)
  - notify_expiring.py           -> app.modules.notifications.service (v1.3+)
  - aggregate_visits_daily.py    -> app.modules.visits.service (v1.3+)

Cross-module imports inside workers are still forbidden — a single scheduled
file MUST NOT import services from two different modules. Use module-level
events (deferred to v1.2+ events bus) for cross-module recurring work.
"""
