"""Reports module — Phase 54 INFRA-41 scaffold (bodies land Phase 55).

Read-only aggregator (D-54-07): performs ZERO INSERT/UPDATE/DELETE on
business tables. The SVC001 commit-gate does not apply (no write paths).

Cross-module data is read via raw SQL `text()` SELECTs in repository.py
(D-54-08, Phase 49 D-49-03 precedent) — NOT by importing other modules'
ORM models. This keeps `modules-independent` clean with zero new
`ignore_imports` edges.

No models.py (reports own no tables); no email_templates.py (no notifications).
Endpoint bodies + query logic deferred to Phase 55.
"""
