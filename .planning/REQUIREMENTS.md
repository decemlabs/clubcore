# Requirements: Sportzal — v1.9 Trainers Complete

**Defined:** 2026-05-24
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Milestone goal:** Закрыть последний неполный бизнес-домен — довести Trainers с catalog-only до ✅: настраиваемый payroll-ledger, расширение расписания (recurring-слоты + отпуска), и read-only отчёт по тренерам.

> Phase numbering continues from v1.8 (ended Phase 57) → v1.9 starts at **Phase 58**.

## v1 Requirements

Requirements for milestone v1.9. Each maps to a roadmap phase.

### Payroll

- [x] **PAY-01**: Owner настраивает на тренере модель компенсации — `commission_pct` (NUMERIC) и/или `session_fee_kopecks` (INT), оба nullable; оба NULL = payroll для тренера не считается; гибрид (оба заданы) допускается
- [x] **PAY-02**: Owner получает read-only preview начисления тренеру за период (`from`/`to`, Europe/Moscow): session_count, fixed_kopecks, commission_kopecks, total_kopecks — без персистентности
- [x] **PAY-03**: Owner фиксирует начисление как append-only строку в новой `trainer_payroll_accruals` (snapshot ставки + period + session_count; UNIQUE `(trainer_id, period_start, period_end)`; 409 при дубле периода; 422 если у тренера нет comp-config)
- [x] **PAY-04**: Owner отмечает начисление выплаченным (`paid_at` + `paid_by_user_id` — единственная разрешённая мутация строки; 409 `already_paid`; операции «unpay» нет)
- [x] **PAY-05**: Owner видит список начислений тренера, упорядоченный `accrued_at DESC`, с paid/unpaid статусом (`{items, total, page, pageSize}`)
- [ ] **PAY-06**: Возврат PT-пакета, пришедший после начисления комиссии, пишет append-only отрицательную clawback-корректировку в payroll-ledger (hook в существующий PT-package refund-flow; same-UoW; не UPDATE существующей строки)

### Recurring Schedule

- [ ] **REC-01**: Owner задаёт recurring-паттерн доступности тренера (`day_of_week` 0..6, `start_time`/`end_time`, `valid_from`, nullable `valid_until`, `is_active`); UNIQUE `(trainer_id, day_of_week, start_time, valid_from)`
- [ ] **REC-02**: ARQ daily cron материализует конкретные `trainer_availability_slots` на горизонт `RECURRING_SLOT_HORIZON_DAYS` (env, default 56) вперёд — идемпотентно (`unique=True` + дедуп перед INSERT), пропуская окна time-off
- [ ] **REC-03**: Owner создаёт/удаляет time-off блок тренера (`block_start`/`block_end`, `reason`); создание отменяет пересекающиеся `active`-слоты (`cancel_reason='trainer_time_off'`); при пересечении с `booked`-слотом — 409 со списком броней, `?force=true` каскадит отмену брони (booking FSM) + DM клиенту через существующую notification-машинерию
- [ ] **REC-04**: Owner/reception видят список recurring-паттернов и time-off блоков тренера

### Trainer Report

- [ ] **RPT-01**: Owner видит read-only отчёт-нагрузку по тренерам за период (session_count, cancelled_session_count, total_hours, unique_client_count, utilization_pct — NULL при 0 слотов), упорядоченный `session_count DESC`; reception 403
- [ ] **RPT-02**: Отчёт показывает revenue-атрибуцию на тренера (sum PT-package sale, avg_revenue_per_session) — атрибуция по участию тренера в пакете (known limitation: пакет с >1 тренером даёт revenue double-count на total-уровне)
- [ ] **RPT-03**: Owner выгружает trainer-report в CSV (UTF-8 BOM, RFC-4180 excel dialect — дисциплина v1.8)
- [ ] **RPT-04**: Отчёт дополнительно показывает `total_accrued_kopecks` / `total_paid_kopecks` за период (из `trainer_payroll_accruals`)

### API Handoff

- [ ] **HND-01**: Byte-stable regen `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` со всеми v1.9 путями + `_v19Checks` `AssertNonNever` forward-guards; RBAC three-way parity (`Resource.TRAINER_PAYROLL` + новые OWNER_ONLY пары; backend ↔ admin-web `can.ts` ↔ `registry.ts`) зелёный; milestone verification

## v2 Requirements

Deferred to v1.10+. Tracked but not in current roadmap.

### Payroll

- **PAY-FUT-01**: Per-session commission proration across period boundaries (вместо full-package-if-any-session)
- **PAY-FUT-02**: «Void» / reverse accrual operation (сейчас — только новые корректирующие строки)
- **PAY-FUT-03**: CSV-экспорт payroll-accruals / 1C-export

### Schedule

- **REC-FUT-01**: iCal / Google Calendar sync паттернов
- **REC-FUT-02**: Pattern templates (копирование паттерна между тренерами)

### Frontend

- **FE-FUT-01**: Trainer payroll + schedule + report UI в production admin (v2.0, против frozen контракта)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Reuse `payments` table для payroll accruals | Смешивает revenue-ledger с expense-ledger; ломает v1.8 revenue reports; требует хирургии CHECK-констрейнтов → отдельная `trainer_payroll_accruals` |
| Tiered commission (% по порогам выручки) | Enterprise-фича; нет второго зала для сравнения → один flat `commission_pct` |
| Автоматическое определение payroll-периода | Нет payroll-календаря; owner задаёт период вручную (`from`/`to`) |
| Expand-on-read recurring слоты (виртуальные) | Ломает `bookings.slot_id` FK + race-safe UNIQUE → generate-ahead concrete rows |
| iCalendar RRULE + EXDATE per-occurrence exceptions | Over-engineering; нет внешнего календарного sync → time-off блок отменяет конкретные слоты |
| Payroll за не-PT работу (floor time, групповые) | Нет class-модуля → только PT-сессии |
| Class-instructor utilization в отчёте | Нет class/group модуля → только PT-сессии |
| No-show rate в trainer-report | No-show живёт на booking-уровне → отдельная будущая фича |
| Write-операции внутри reports-модуля | D-54-07 read-only дисциплина → только raw-SQL reads |
| API Handoff + Production Hardening (Postman/Newman, doc-сайт, npm-publish, idempotency-hardening) | Сдвинуто на v1.10 (reorder 2026-05-24) |
| Tech-debt sweep (DEFER-46-04 ruff/format/mypy, DEFER-40-01 v1.5 runbook) | Перенесено в v1.10 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PAY-01 | Phase 58 | Complete |
| PAY-02 | Phase 58 | Complete |
| PAY-03 | Phase 58 | Complete |
| PAY-04 | Phase 58 | Complete |
| PAY-05 | Phase 58 | Complete |
| PAY-06 | Phase 58 | Pending |
| REC-01 | Phase 59 | Pending |
| REC-02 | Phase 59 | Pending |
| REC-03 | Phase 59 | Pending |
| REC-04 | Phase 59 | Pending |
| RPT-01 | Phase 60 | Pending |
| RPT-02 | Phase 60 | Pending |
| RPT-03 | Phase 60 | Pending |
| RPT-04 | Phase 60 | Pending |
| HND-01 | Phase 61 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15 ✓
- Unmapped: 0 ✓

## Locked Decisions (carry into planning)

- **D-PAYROLL-LEDGER**: новая `trainer_payroll_accruals` (НЕ reuse `payments`); append-only дисциплина v1.4; SVC001 commit-gate покрывает payroll-сервис.
- **D-PAYROLL-RATE-SNAPSHOT**: ставка (commission_pct + session_fee_kopecks) снапшотится в accrual-строку; изменение конфига тренера НЕ меняет прошлые начисления (зеркало v1.2 mandatory price snapshot).
- **D-PAYROLL-ATTRIBUTION**: комиссия начисляется на полную сумму PT-package sale, если ≥1 сессия пакета попадает в период (НЕ per-session proration); документированное known limitation.
- **D-PAYROLL-ROUNDING**: `decimal.Decimal` + `ROUND_HALF_EVEN` (банковское округление), без float; commission_kopecks = round(sum_revenue * pct / 100).
- **D-PAYROLL-CLAWBACK**: refund PT-пакета после начисления → append-only отрицательная корректирующая строка в same UoW, не UPDATE.
- **D-SLOT-GENERATE-AHEAD**: recurring-паттерны материализуются ARQ-кроном в concrete `trainer_availability_slots` (горизонт env), НЕ expand-on-read; идемпотентность через дедуп/`ON CONFLICT DO NOTHING` + `unique=True`.
- **D-TIMEOFF-CONFLICT**: time-off над `booked`-слотом → 409 + список броней; каскадная отмена только по явному `?force=true`.
- **D-REPORT-READONLY**: trainer-report живёт в `app/modules/reports/` под D-54-07/08 (raw-SQL `text()`, no `models.py`, owner-only, zero writes, zero new import-linter ignores).
- **D-AUDIT-PREREG**: LOCKED audit events (`trainer_payroll_accrued`, `trainer_payroll_paid`, `trainer_payroll_clawed_back`, `trainer_time_off_created`, `trainer_time_off_deleted` + optional recurring-pattern events) пре-регистрируются ДО любого callsite (INFRA-15).
- **D-RBAC-VERIFY**: Phase 58 ДОЛЖНА сначала прочитать `permissions.py` + `can.ts` — research-флаг MUST-VERIFY: возможно `Resource.PAYROLL`/`COMPENSATION` уже существуют; новые пары owner-only + byte-parity test зелёный.
- **TZ**: все периоды и buckets детерминированы в Europe/Moscow (зеркало `visits.gym_date STORED`).
- **Money**: integer kopecks везде; форматирование на фронте (v2.0); CSV — единственное место server-side рублёвого форматирования (D-11).

---
*Requirements defined: 2026-05-24*
*Last updated: 2026-05-24 — traceability table filled after roadmap creation (v1.9 Trainers Complete, Phases 58-61)*
