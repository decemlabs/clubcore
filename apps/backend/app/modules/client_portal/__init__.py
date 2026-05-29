"""Client-portal module — Phase 69 read-only aggregator (CHOME-01..03, CHIST-01..03, CPLAN-01..03).

Read-only aggregator (D-20-MODULE): performs ZERO INSERT/UPDATE/DELETE on
business tables. The SVC001 commit-gate does not apply (no write paths).

Cross-module data is read via raw SQL `text()` SELECTs in repository.py
(D-54-08 / D-49-03 / D-20-MODULE precedent) — NOT by importing other modules'
ORM models. This keeps `modules-independent` clean with zero new
`ignore_imports` edges.

No models.py (client_portal owns no tables); no email_templates.py (no notifications).
All reads are IDOR-safe: mandatory client_id bind param on every owned read (D-20-IDOR).
"""
