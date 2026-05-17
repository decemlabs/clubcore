"""Integration tests for schedule module — Phase 38 plan 38-01.

Task 1 ships the import-only smoke + constant assertion. Task 3 fills the
behavioural test suite for publish_slot / list_slots / get_slot / cancel_slot
+ resolve_slot_by_id silent-None contract.
"""

from __future__ import annotations


def test_trainer_availability_slot_model_imports() -> None:
    """SLOT-01 — ORM model class is importable and exposes the locked tablename."""
    from app.modules.schedule.models import TrainerAvailabilitySlot

    assert TrainerAvailabilitySlot.__tablename__ == "trainer_availability_slots"


def test_slot_buffer_minutes_constant() -> None:
    """SLOT-04 / C-15 — buffer constant hardcoded to 10 minutes for v1.5."""
    from app.modules.schedule.constants import SLOT_BUFFER_MINUTES

    assert SLOT_BUFFER_MINUTES == 10
