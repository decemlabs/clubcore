"""Phase 62 D-62-02 / CLUB_BRAND-EXTRACTION — single source of truth for the gym brand.

This is NOT the product/codebase name (``clubcore``). This IS the per-installation
gym brand surfaced in email subjects, footers, and invitation copy. Value is
locked to ``"Sportzal"`` placeholder in v1.10 (zero behaviour change per
D-10-NO-NEW-BUSINESS). Per-club configurable brand deferred to a future phase.
"""

from typing import Final

CLUB_BRAND: Final[str] = "Sportzal"
