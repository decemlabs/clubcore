"""Shared OpenAPI response objects for components.responses (Phase 64 FRZ-06).

Decision references:
  - D-64-RESPONSES-LOCATION: define all 6 shared response objects in this module.
  - D-64-RESPONSES-APPLY: post-processor in app/main.py injects them into
    spec.components.responses and rewrites inline 401/403/404/409/422/429
    operation responses to $ref.

Envelope source of truth: app/core/exceptions.py:440-449.
  Every error response carries exactly {code: string, message: string, fields: object | null}.
"""

# Each entry is a full OpenAPI 3.1 Response Object dict.
# Trailing comment on each entry names the representative AppError subclass(es)
# per the code-mapping table in 64-PATTERNS.md §1.
OPENAPI_ERROR_RESPONSES: dict[str, dict[str, object]] = {
    # InvalidAccessToken (exceptions.py:79), InvalidPassword (line 86), InvalidSession (line 100)
    "401_Unauthorized": {
        "description": "Unauthorized — invalid or missing session credentials.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
    "403_Forbidden": {  # ForbiddenError (exceptions.py:24), CsrfMismatch (line 29)
        "description": "Forbidden — insufficient permissions or CSRF mismatch.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
    "404_NotFound": {  # NotFoundError (exceptions.py:19), ClientNotFoundError (line 120)
        "description": "Not Found — the requested resource does not exist.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
    "409_Conflict": {  # ConflictError (exceptions.py:43), PhoneExistsError (line 127)
        "description": "Conflict — the resource state conflicts with the request.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
    # ValidationAppError (exceptions.py:48), ClientEmailRequiredForOnlinePaymentError (line 53)
    "422_ValidationError": {
        "description": "Validation Error — request body or parameters failed validation.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
    "429_RateLimited": {  # RateLimited (exceptions.py:113)
        "description": "Too Many Requests — per-actor throttle exhausted.",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "nullable": True,
                            "additionalProperties": True,
                        },
                    },
                    "required": ["code", "message"],
                }
            }
        },
    },
}
