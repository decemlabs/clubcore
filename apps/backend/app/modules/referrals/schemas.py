"""Referral module Pydantic schemas (Phase 96 REFER-01 / REFER-03 / REFER-07).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

Wire names are camelCase per project convention; Python attribute names are
snake_case. Each field carries a trailing comment with its wire name.
"""

from __future__ import annotations

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
    code is the 8-char Crockford-base32 referral code shared by the referrer.
    max_length=16 mirrors the referral_codes.code VARCHAR(16) column.
    """

    code: str = Field(min_length=1, max_length=16)  # wire: code


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
