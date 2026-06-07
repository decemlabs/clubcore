"""Messaging module — client↔gym 1:1 messaging threads + messages (Phase 90 MSG-01..04 / RT-01..04).

Bounded responsibility: each client has a single lazily-created thread with the gym.
REST endpoints (send / list / mark-read) live in router.py (Plans 02+).
Real-time WebSocket transport with Redis pub/sub fan-out lives in router.py (Plan 03+).

TODO Phase 91: read receipts + typing indicators (RCPT-01..03).
TODO Phase 92: photo attachments + attachment_id FK (ATT-01..03).
TODO Phase 93: Telegram bridge forward + reply routing (BRDG-01..03).
"""
