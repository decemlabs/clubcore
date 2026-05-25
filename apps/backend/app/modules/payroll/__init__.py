"""Payroll module — Phase 58 PAY-01..06.

Append-only accrual ledger (D-58-03 INFRA-15). Orchestrator-owns-commit
discipline for run_payroll_period and mark_accrual_paid — each service
function owns the UoW.

Protocol slot PayrollClawbackRecorder wired exclusively from
app.main.create_app() (NOT in app.workers.telegram_bot). Defensive-raise
accessor get_payroll_clawback_recorder() in app.core.dependencies surfaces
'slot not registered' as RuntimeError.

Cross-module reads (pt_sessions / pt_packages / payments) go via raw SQL
text() SELECTs in payroll/repository.py (D-58-19 / D-54-08 lineage) —
ZERO new ignore_imports edges are needed.
"""
