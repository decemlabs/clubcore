"""Reports service — Phase 54 INFRA-41 scaffold (bodies land Phase 55).

Read-only aggregator role: orchestrates calls to repository.py which reads
cross-module data via raw SQL ``text()`` SELECTs (D-54-08 / D-49-03 precedent).

INVARIANTS (must hold after Phase 55 bodies land):
- ZERO INSERT / UPDATE / DELETE on any business table.
- SVC001 commit-gate does NOT apply (no write paths, no ``session.commit``).
- Never imports another module's ORM model — reads go through repository.py
  raw SQL readers exclusively.

Phase 55 will add:
  - ``get_revenue_report(session, query)`` — aggregate payments by period.
  - ``get_clients_report(session, query)`` — active/expiring/new clients.
  - ``get_visits_report(session, query)`` — visits by day/hour buckets.
"""
