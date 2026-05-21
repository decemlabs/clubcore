---
phase: 48-kassa-integration-adapter
plan: 04
subsystem: integrations/yookassa
tags: [integrations, yookassa, receipt, 54fz, ast-gate, locked-literal, adapter-04]
one_liner: "Locked 54-ФЗ receipt-item builder + 3 enums + extended AST gate (payment_subject/payment_mode literal walkers)"
requires:
  - phase: 47
    artifact: app/integrations/yookassa/_money.py (kopecks_to_yookassa)
  - phase: 47
    artifact: tests/unit/test_locked_yookassa_constants_ast.py (Phase 47 baseline walker)
provides:
  - app/integrations/yookassa/receipt.py (build_receipt_item + PaymentSubject/PaymentMode/VatCode)
  - 4 new AST-gate tests on test_locked_yookassa_constants_ast.py
  - tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_{subject,mode}.py
affects:
  - downstream Phase 49 orchestrator (assembles receipt items via build_receipt_item)
  - downstream Phase 50 fiscal-receipt dispatcher (consumes receipt items via list[dict])
tech_stack:
  added: []
  patterns:
    - "StrEnum + IntEnum lock for 54-ФЗ tags (D-48-17)"
    - "AST-walker gate for literal enum-member kwargs (D-48-18, INFRA-15 discipline)"
    - "Pure dict return for ЮKassa wire format (D-48-16)"
key_files:
  created:
    - apps/backend/app/integrations/yookassa/receipt.py
    - apps/backend/tests/integrations/yookassa/__init__.py
    - apps/backend/tests/integrations/yookassa/test_receipt.py
    - apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_subject.py
    - apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_mode.py
  modified:
    - apps/backend/tests/unit/test_locked_yookassa_constants_ast.py
decisions:
  - "D-48-16: build_receipt_item returns plain dict[str, Any], not a typed model (callers concatenate into list inside payment-create body)"
  - "D-48-17: 3 enums lock 54-ФЗ tag values (PaymentSubject:1, PaymentMode:2, VatCode:6 members)"
  - "D-48-18: AST gate extended with 2 walker tests rejecting non-literal payment_subject/payment_mode kwargs"
  - "Claude's Discretion: CURRENCY=RUB hardcoded; quantity default '1.00'; 128-char description guard before wire send"
metrics:
  duration_minutes: 4
  tasks_completed: 3
  files_changed: 6
  completed: 2026-05-21
requirements: [ADAPTER-04]
---

# Phase 48 Plan 04: Receipt Builder + 54-ФЗ Enum Locks Summary

Locked the 54-ФЗ receipt-item wire shape behind a single pure function
(`build_receipt_item`) and three enum classes (`PaymentSubject`, `PaymentMode`,
`VatCode`) at module-load time, then extended the Phase 47 AST gate with two
walker tests that reject non-literal `payment_subject=` / `payment_mode=`
kwargs at any future callsite — mirroring INFRA-15 discipline so Phase 49's
orchestrator (the first real consumer) cannot accidentally pass a variable or
f-string instead of an enum member.

## Tasks Executed

| Task | Name                                                                                | Commit  | Files                                                                                                                                                                                                                                            |
| ---- | ----------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Create receipt.py with 3 enums + build_receipt_item                                 | f830829 | apps/backend/app/integrations/yookassa/receipt.py                                                                                                                                                                                              |
| 2    | Create test_receipt.py with shape + enum-count + 128-char tests                     | d07ea9e | apps/backend/tests/integrations/yookassa/{__init__.py,test_receipt.py}                                                                                                                                                                          |
| 3    | Extend AST gate with payment_subject + payment_mode walker tests + 2 fixtures       | 62f57e6 | apps/backend/tests/unit/test_locked_yookassa_constants_ast.py, apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_{subject,mode}.py                                                                                  |

## Public Surface (receipt.py)

```
class PaymentSubject(StrEnum):  # тег 1212; len==1
    SERVICE = "service"

class PaymentMode(StrEnum):      # тег 1214; len==2
    FULL_PAYMENT = "full_payment"
    FULL_PREPAYMENT = "full_prepayment"

class VatCode(IntEnum):          # тег 1199; len==6
    VAT_NONE = 1; VAT_0 = 2; VAT_10 = 3; VAT_20 = 4; VAT_10_110 = 5; VAT_20_120 = 6

CURRENCY: Final[str] = "RUB"
_MAX_DESCRIPTION_LEN: Final[int] = 128

def build_receipt_item(
    *,
    description: str,
    amount_kopecks: int,
    payment_subject: PaymentSubject,
    payment_mode: PaymentMode,
    vat_code: VatCode,
    quantity: str = "1.00",
) -> dict[str, Any]: ...
```

Returns the canonical ЮKassa wire shape:

```
{
  "description": "...",
  "quantity": "1.00",
  "amount": {"value": "1990.00", "currency": "RUB"},
  "vat_code": 1,
  "payment_mode": "full_prepayment",
  "payment_subject": "service",
}
```

Raises `ValueError` on descriptions > 128 chars (ЮKassa wire limit).

## AST Gate Extension

Added 4 new tests to `tests/unit/test_locked_yookassa_constants_ast.py` (Phase 47
baseline tests untouched, all still green):

| Test                                                | Role                                                                                              |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `test_payment_subject_literal_at_callsites`         | Walks `apps/backend/app/**/*.py`; 0 violations today (Phase 48 ships zero real callsites)         |
| `test_payment_mode_literal_at_callsites`            | Same shape for `PaymentMode`                                                                      |
| `test_non_literal_payment_subject_fixture_is_rejected` | Sanity-checks the walker against `non_literal_payment_subject.py` fixture                       |
| `test_non_literal_payment_mode_fixture_is_rejected`    | Sanity-checks the walker against `non_literal_payment_mode.py` fixture                          |

Three new helpers added without colliding with Phase 47 helpers:
`_is_build_receipt_item_call`, `_extract_kwarg`, `_is_enum_member_literal`.

## Test Coverage

- `tests/integrations/yookassa/test_receipt.py` — 10 sync tests (>=8 required):
  CURRENCY constant, PaymentSubject/PaymentMode/VatCode member counts + values,
  wire-shape dict equality (canonical 199_000 kopecks example), FULL_PAYMENT
  branch + VAT_20 code path, custom quantity override, exactly-128/129 boundary,
  `type(item) is dict` (D-48-16 lock).
- `tests/unit/test_locked_yookassa_constants_ast.py` — 7 tests total (3 Phase 47
  baseline + 4 new); all pass; ruff + mypy strict clean.

## Verification

- `cd apps/backend && uv run ruff check app/integrations/yookassa/receipt.py tests/integrations/yookassa/test_receipt.py tests/unit/test_locked_yookassa_constants_ast.py` → exit 0
- `cd apps/backend && uv run mypy --strict ...` (same three files) → exit 0
- `cd apps/backend && uv run pytest tests/integrations/yookassa/test_receipt.py tests/unit/test_locked_yookassa_constants_ast.py -q` → 17 passed
- `cd apps/backend && uv run python -c "from app.integrations.yookassa.receipt import PaymentSubject, PaymentMode, VatCode; assert len(PaymentSubject) == 1 and len(PaymentMode) == 2 and len(VatCode) == 6"` → exit 0
- AST-walker confirms 0 real `build_receipt_item` `ast.Call` nodes in
  `apps/backend/app/**/*.py` (Phase 49 orchestrator lands the first).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] mypy strict rejects `VatCode.VAT_NONE == 1`**
- **Found during:** Task 2 verification (`uv run mypy --strict tests/integrations/yookassa/test_receipt.py`)
- **Issue:** mypy --strict flagged `assert VatCode.VAT_NONE == 1` (and the other 5 VatCode equality asserts) with `comparison-overlap` — `Literal[VatCode.VAT_NONE]` and `Literal[1]` are non-overlapping at the type level even though they are equal at runtime (IntEnum supports `__eq__` but mypy does not narrow the comparison).
- **Fix:** Wrapped each VatCode member in `int(...)` for the equality assertions in `test_vat_code_has_six_members`. Semantics preserved — IntEnum.value is the int regardless.
- **Files modified:** `apps/backend/tests/integrations/yookassa/test_receipt.py`
- **Commit:** d07ea9e (Task 2)

### Acceptance-criterion text vs. semantic intent

**2. [Rule 1 — Bug | docs-only grep false-positive]** Task 3 acceptance criterion
`grep -rE 'build_receipt_item\s*\(' apps/backend/app/ | grep -v 'def build_receipt_item' | wc -l` outputs `0` matches `1` line instead of `0`. The "extra" match is the docstring line in `receipt.py:14` (`...every ``build_receipt_item(payment_subject=..., payment_mode=...)``...`) which mentions the function name inside a triple-quoted module docstring.

- **Why this is not a real violation:** The canonical contract is "0 real callsites in the production AST tree", enforced by the AST walker `test_payment_subject_literal_at_callsites` / `test_payment_mode_literal_at_callsites`. AST parsing treats docstrings as `ast.Constant` (string) nodes, not `ast.Call`, so the walker correctly reports 0 violations. The grep-based acceptance text is a coarser proxy that flags docstring mentions.
- **Action taken:** None — the gate (AST walker) is canonical and passes; the docstring mention is intentional documentation of the AST-gate contract.
- **Verification:** Manual `python3 -c "import ast; ..."` confirmed 0 `ast.Call` nodes for `build_receipt_item` in `apps/backend/app/**/*.py`.

## Threat Mitigations Wired

| Threat ID    | Mitigation Shipped                                                                                                                              |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| T-48-04-01   | `class PaymentSubject(StrEnum): SERVICE = "service"` + `len(PaymentSubject) == 1` runtime assertion + AST gate `test_payment_subject_literal_at_callsites` |
| T-48-04-02   | `class PaymentMode(StrEnum)` with exactly 2 members + AST gate `test_payment_mode_literal_at_callsites`                                          |
| T-48-04-03   | `class VatCode(IntEnum)` with 6 members + `test_vat_code_has_six_members` runtime assertion                                                       |
| T-48-04-04   | AST gate + member-count tests force coupled updates — silent drift impossible without amending both                                              |
| T-48-04-05   | `build_receipt_item` raises `ValueError` when description > 128 chars before any wire send (caught in test/dev, not at runtime against ЮKassa)   |
| T-48-04-06   | `CURRENCY: Final[str] = "RUB"` module constant; no env override; no multi-currency path in v1.7                                                  |

## Downstream Consumers

- **Plan 48-02 (client.py):** consumes `list[dict[str, Any]]` of receipt items
  in the `receipt_items` parameter of `YooKassaClient.create_payment`. The
  client never assembles items itself.
- **Phase 49 orchestrator (online sales):** assembles per-sale items via
  `build_receipt_item(payment_subject=PaymentSubject.SERVICE,
  payment_mode=PaymentMode.FULL_PREPAYMENT or FULL_PAYMENT, vat_code=...,
  ...)` and passes the list to `client.create_payment`. This is the first
  real callsite the AST gate will guard.
- **Phase 50 (fiscal-receipt webhook FSM):** may re-use receipt items for
  refund-side fiscal documents via the same builder.

## Self-Check: PASSED

- FOUND: apps/backend/app/integrations/yookassa/receipt.py
- FOUND: apps/backend/tests/integrations/yookassa/test_receipt.py
- FOUND: apps/backend/tests/integrations/yookassa/__init__.py
- FOUND: apps/backend/tests/unit/test_locked_yookassa_constants_ast.py (modified)
- FOUND: apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_subject.py
- FOUND: apps/backend/tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_mode.py
- FOUND: commit f830829 (Task 1)
- FOUND: commit d07ea9e (Task 2)
- FOUND: commit 62f57e6 (Task 3)
