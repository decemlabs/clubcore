"""Seed trainer profiles: bio + specialization baseline (Phase 88 TRNR-03).

Revision ID: 0063_seed_trainer_profiles
Revises: 0062_trainer_profile_fields
Create Date: 2026-06-06

Data-only migration: backfills bio and specialization for the six PWA trainers
so fresh environments render real trainer profiles with zero manual intervention.

Content source: apps/client-pwa/src/data/trainers.js (TRAINERS array).

Idempotency:
- UPDATE ... WHERE full_name = :name AND deleted_at IS NULL
- Re-running sets identical values — safe no-op side-effect on subsequent runs.
- photo_url left NULL; owner sets it later via PATCH /api/v1/trainers/{id}.

Downgrade resets specialization/bio/photo_url to NULL for all non-deleted rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0063_seed_trainer_profiles"
down_revision: str | None = "0062_trainer_profile_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (full_name, specialization, bio)
# Specialization taken verbatim from trainers.js `spec` field.
# Bio synthesised from `exp` + `spec` fields for baseline content.
_TRAINER_PROFILES: list[tuple[str, str, str]] = [
    (
        "Аня Соколова",
        "Силовые, функционал",
        "Аня Соколова — силовые и функциональный тренинг, 7 лет опыта. "
        "Специализируется на технике базовых упражнений и прогрессивной нагрузке.",
    ),
    (
        "Марк Левин",
        "Кроссфит, выносливость",
        "Марк Левин — кроссфит и развитие выносливости, 5 лет опыта. "
        "Помогает достичь высоких функциональных показателей через интервальные тренировки.",
    ),
    (
        "Лиза Орлова",
        "Йога, стретчинг",
        "Лиза Орлова — йога и стретчинг, 9 лет опыта. "
        "Ведёт занятия по хатха-йоге и глубокому растяжению для восстановления и гибкости.",
    ),
    (
        "Денис Кравцов",
        "Бокс, ММА",  # noqa: RUF001
        "Денис Кравцов — бокс и смешанные единоборства, 11 лет опыта. "
        "Тренирует технику ударов, защиты и общей физической подготовки.",
    ),
    (
        "Соня Бек",
        "Пилатес, осанка",
        "Соня Бек — пилатес и коррекция осанки, 4 года опыта. "
        "Работает с мышцами кора и постуральными мышцами для выравнивания тела.",  # noqa: RUF001
    ),
    (
        "Игорь Раш",
        "Бодибилдинг",
        "Игорь Раш — бодибилдинг и набор мышечной массы, 8 лет опыта. "
        "Составляет программы для гипертрофии с учётом индивидуальной физиологии.",  # noqa: RUF001
    ),
]


def upgrade() -> None:
    for full_name, specialization, bio in _TRAINER_PROFILES:
        op.execute(
            sa.text(
                "UPDATE trainers "
                "SET specialization = :spec, bio = :bio, photo_url = NULL "
                "WHERE full_name = :name AND deleted_at IS NULL"
            ).bindparams(name=full_name, spec=specialization, bio=bio)
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE trainers "
            "SET specialization = NULL, bio = NULL, photo_url = NULL "
            "WHERE deleted_at IS NULL"
        )
    )
