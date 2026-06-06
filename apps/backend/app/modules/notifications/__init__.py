"""Notifications module — in-app inbox + push-token registration (Phase 87 INBOX-01..04).

Populated in Phase 87:
  models.py      — InAppNotification + ClientPushToken ORM models
  schemas.py     — Request/response DTOs (Pydantic v2)
  repository.py  — Raw-SQL reads + ORM writes (caller-owns-txn)
  service.py     — 5-function public service contract (caller-owns-txn)

TODO Phase B+: event-bus outbox pattern for async Telegram/email delivery channels.
"""
