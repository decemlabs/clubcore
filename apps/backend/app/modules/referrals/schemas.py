"""Referral module Pydantic schemas (Phase 96 REFER-01 / REFER-03 / REFER-07;
Phase 98 REFER-06 adds ReferralInviteeItem + ReferralSummaryResponse).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

Wire names are camelCase per project convention; Python attribute names are
snake_case. Each field carries a trailing comment with its wire name.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData


class ReferralCodeResponse(ResponseData):
    """GET /client/referral/code payload (REFER-01).

    Wire: { code: str, shareUrl: str }
    shareUrl is server-authoritative: {pwa_base_url}/i/{code}
    (pwa_base_url is a Settings field, not hardcoded).
    """

    code: str  # wire: code
    share_url: str  # wire: shareUrl


class ReferralResolveResponse(ResponseData):
    """GET /i/{code} public deep-link resolver payload (REFER-01).

    Wire: { valid: bool, referrerFirstName: str | None, welcomeBonusKopecks: int }
    Always 200 — valid=False for unknown codes (anti-enumeration: no 404).
    referrerFirstName exposes only the first name of the referrer (no PII beyond that).
    welcomeBonusKopecks is 0 when valid=False.
    """

    valid: bool  # wire: valid
    referrer_first_name: str | None  # wire: referrerFirstName
    welcome_bonus_kopecks: int  # wire: welcomeBonusKopecks


class ReferralCaptureRequest(BackendSchemaBase):
    """POST /client/referral/capture request body (REFER-03).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    code is exactly 8 Crockford-base32 characters (WR-03 fix).

    Pattern accepts both upper- and lower-case Crockford alphabet chars
    (0-9 A-H J K M N P-T V-Z, excluding O/I/L/U) — the repository normalises
    to upper-case via .upper() before the DB lookup.
    """

    code: str = Field(
        min_length=8,
        max_length=8,
        # Crockford base32 alphabet (upper or lower), exactly 8 chars.
        # Excluded: I (eye), L (el), O (oh), U — ambiguous under Crockford spec.
        pattern=r"^[0-9A-HJKMNPQRSTVWXYZa-hjkmnpqrstvwxyz]{8}$",
    )  # wire: code


class ReferralConfigResponse(ResponseData):
    """GET /referral/config owner-only payload (REFER-07).

    Wire: { referrerBonusKopecks: int, refereeWelcomeKopecks: int }
    Mirrors the seeded singleton values (50000 / 30000 kopecks).
    """

    referrer_bonus_kopecks: int  # wire: referrerBonusKopecks
    referee_welcome_kopecks: int  # wire: refereeWelcomeKopecks


class ReferralConfigUpdateRequest(BackendSchemaBase):
    """PUT /referral/config owner-only request body (REFER-07).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    Both fields are required (full-replace semantics, not PATCH).
    ge=0 allows zeroing out either bonus (owner decision).
    """

    referrer_bonus_kopecks: int = Field(ge=0)  # wire: referrerBonusKopecks
    referee_welcome_kopecks: int = Field(ge=0)  # wire: refereeWelcomeKopecks


class ReferralInviteeItem(ResponseData):
    """One invited friend in the referral summary list (REFER-06).

    Wire: {firstName, joinedAt, status, bonusKopecks}.
    PII-minimal: first name only (T-96-06); NO last name, NO referee client_id.
    """

    first_name: str  # wire: firstName
    joined_at: datetime  # wire: joinedAt (referral_captures.created_at, ISO-8601 TZ)
    status: Literal["joined", "pending"]  # wire: status
    bonus_kopecks: int  # wire: bonusKopecks (referrer bonus for this invitee; 0 while pending)


class ReferralSummaryResponse(ResponseData):
    """GET /client/referral/summary payload (REFER-06).

    Wire: {code, shareUrl, accruedKopecks, invitees: [...]}
    accruedKopecks is the SUM of the authenticated client's own referral_accrual
    loyalty_ledger rows — NOT the total loyalty balance.
    shareUrl is server-authoritative: {pwa_base_url}/i/{code}.
    """

    code: str  # wire: code
    share_url: str  # wire: shareUrl
    accrued_kopecks: int  # wire: accruedKopecks (SUM of own referral_accrual rows)
    invitees: list[ReferralInviteeItem]  # wire: invitees
