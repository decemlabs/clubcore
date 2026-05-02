"""Auth module-local exceptions — Phase 7 verify failure modes (D-13).

These classes live in app.modules.auth (NOT app.core) because they belong
to the narrow Telegram-OTP domain. Every subclass extends
app.core.exceptions.AppError so the existing handler `_app_error_handler`
(app/core/exceptions.py:81-93) automatically renders the
`{code, message, fields?}` envelope without any extra registration.

Mapping to D-13 table:
  | Failure                                  | HTTP | code             | fields                |
  |------------------------------------------|------|------------------|-----------------------|
  | OtpCode found, code_hash IS NULL         | 409  | bot_not_started  | {deepLinkUrl}         |
  | expires_at < now                         | 410  | otp_expired      | --                    |
  | code_hash mismatch, attempts<5           | 401  | otp_invalid      | {attemptsRemaining}   |
  | code_hash mismatch, attempts>=5 after miss| 429 | otp_max_attempts | --                    |
  | consumed_at IS NOT NULL                  | 409  | otp_consumed     | --                    |
  | deep_link_token_hash not found           | 404  | token_unknown    | --                    |

`fields` is supplied by the caller via the standard
`AppError.__init__(message, *, fields=...)` (app/core/exceptions.py:13-16);
the classes themselves are declarative and only carry `code` + `status_code`.
"""

from app.core.exceptions import AppError


class BotNotStarted(AppError):  # noqa: N818
    """OtpCode found but `code_hash IS NULL` -- user has not pressed /start in the bot.

    Caller must pass `fields={"deepLinkUrl": <url>}` to `__init__` so the
    frontend can re-display the deep link.
    """

    code = "bot_not_started"
    status_code = 409


class OtpExpired(AppError):  # noqa: N818
    """`expires_at < now` -- OTP code TTL elapsed (5 minutes from issuance)."""

    code = "otp_expired"
    status_code = 410


class OtpInvalid(AppError):  # noqa: N818
    """sha256(presented_code) != code_hash; attempts still < 5 after increment.

    Caller must pass `fields={"attemptsRemaining": n}` so the frontend can
    show the remaining-attempts counter.
    """

    code = "otp_invalid"
    status_code = 401


class OtpMaxAttempts(AppError):  # noqa: N818
    """attempts >= 5 after the latest miss -- OTP is locked."""

    code = "otp_max_attempts"
    status_code = 429


class OtpAlreadyConsumed(AppError):  # noqa: N818
    """`consumed_at IS NOT NULL` -- replay attempt on an already used code."""

    code = "otp_consumed"
    status_code = 409


class TokenUnknown(AppError):  # noqa: N818
    """Hashed deep_link_token not found in OtpCode."""

    code = "token_unknown"
    status_code = 404
