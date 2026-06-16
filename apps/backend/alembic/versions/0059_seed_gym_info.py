"""Seed gym_info singleton baseline (Phase 86 GYM-03).

Revision ID: 0059_seed_gym_info
Revises: 0058_gym_info
Create Date: 2026-06-06

Data-only migration: seeds the single gym_info row with the Тверская baseline
content so fresh environments render real content with zero manual intervention.

Content source: apps/client/src/data/gym.js (GYM_INFO). Fields NOT seeded:
- photos: frontend-only static (décor photos stored in client, not DB)
- staffToday, todayIdx, status, walkMin: computed/derived at render time

Idempotency:
- INSERT ... ON CONFLICT (id) DO NOTHING — id is the PK.
- Re-running upgrade() is a verified no-op (T-86-01 mitigation).
- Conflict target is (id) because the singleton has a deterministic UUID PK
  (no partial unique index needed — PK uniqueness is sufficient).

Downgrade hard-deletes the row (no FK references to gym_info).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_seed_gym_info"
down_revision: str | None = "0058_gym_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Deterministic singleton PK — consistent across all environments.
_SINGLETON_ID = "00000000-0000-0000-0000-000000000001"

# Baseline content from apps/client/src/data/gym.js (GYM_INFO).
_HOURS = json.dumps([
    {"d": "Пн", "open": "07:00", "close": "23:00"},
    {"d": "Вт", "open": "07:00", "close": "23:00"},
    {"d": "Ср", "open": "07:00", "close": "23:00"},
    {"d": "Чт", "open": "07:00", "close": "23:00"},
    {"d": "Пт", "open": "07:00", "close": "22:00"},
    {"d": "Сб", "open": "09:00", "close": "22:00"},
    {"d": "Вс", "open": "09:00", "close": "21:00"},
])

_AMENITIES = json.dumps([
    {"icon": "parking", "label": "Парковка"},
    {"icon": "wifi", "label": "Wi-Fi"},
    {"icon": "shower", "label": "Душ"},
    {"icon": "locker", "label": "Шкафчики"},
    {"icon": "sauna", "label": "Сауна"},
    {"icon": "towel", "label": "Полотенца"},
    {"icon": "water", "label": "Вода"},
    {"icon": "kids", "label": "Детская зона"},
])

_RULES = json.dumps([
    "Спортивная форма и сменная обувь обязательны",
    "Берите полотенце на тренировку — раскладываем на тренажёре",
    "Возвращайте инвентарь на место после подхода",
    "Громкая музыка в наушниках — нет. В колонке — нет",
    "Зона свободных весов — приоритет у тренирующегося",
])

_SOCIAL = json.dumps([
    {"kind": "tg", "label": "Telegram", "handle": "@mygym_tverskaya"},
    {"kind": "ig", "label": "Instagram", "handle": "@mygym.club"},
])


def upgrade() -> None:
    # Use CAST(:param AS type) syntax because SQLAlchemy sa.text().bindparams()
    # cannot parse parameters with the :param::type PostgreSQL cast shorthand
    # (the :: suffix is not recognised as part of the parameter name).
    # The asyncpg driver sends all bind params as VARCHAR; explicit CAST is required
    # for uuid and jsonb columns to avoid type-mismatch errors.
    op.execute(
        sa.text(
            "INSERT INTO gym_info "
            "(id, name, tagline, address, city, metro, phone, email, "
            " hours, amenities, rules, social) "
            "VALUES (CAST(:id AS uuid), :name, :tagline, :address, :city, :metro, :phone, :email, "
            "        CAST(:hours AS jsonb), CAST(:amenities AS jsonb),"
            "        CAST(:rules AS jsonb), CAST(:social AS jsonb)) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_SINGLETON_ID,
            name="Мой зал · Тверская",
            tagline="Круглосуточный клуб в центре",
            address="Тверская, 18, 3 этаж",
            city="Москва",
            metro="5 мин от м. Пушкинская",
            phone="+7 495 123-45-67",
            email="tverskaya@mygym.ru",
            hours=_HOURS,
            amenities=_AMENITIES,
            rules=_RULES,
            social=_SOCIAL,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM gym_info WHERE id = CAST(:id AS uuid)").bindparams(
            id=_SINGLETON_ID
        )
    )
