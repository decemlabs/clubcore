"""Telegram integration -- python-telegram-bot 22 wiring (Phase 7).

Layer responsibilities:
  - bot.py       : Application factory (D-09 -- no module-level instances).
  - handlers.py  : ptb update callbacks; consume HandlerContext closure (D-05).
  - sender.py    : SOLE outbound DM boundary (D-07); typed SendResult.

Architectural constraint (importlinter `integrations-not-depend-on-modules`):
this package MUST NOT import from app.modules.*. Domain calls are injected
via HandlerContext, constructed in app/workers/telegram_bot.py (D-05, D-06).
"""
