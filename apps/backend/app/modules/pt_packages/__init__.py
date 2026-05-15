"""PT-packages module (Phase 33 PT-01..13 plans + instances).

Module marker — re-exports the public resolver delegate so ``app.main.create_app``
can wire it via ``register_active_pt_package_resolver`` without crossing the
modules-independent importlinter contract (composition-root carve-out per
Phase 5 D-15 / Phase 17 D-18 / Phase 33 D-33-12).

Phase 34 (PT-14..22) materialises PT-sessions in a separate module (B-04
variant B — confirmed by user).
"""

from app.modules.pt_packages.service import resolve_active_pt_package

__all__ = ("resolve_active_pt_package",)
