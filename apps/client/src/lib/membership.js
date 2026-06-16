// ─── Shared membership adapters (WR-05) ───────────────────────────────────
// Single source of truth for the API membership → render-shape adapter,
// previously duplicated verbatim in HomeScreen.jsx and ProfileScreen.jsx.
// API: ClientMembershipResponse { id, planNameSnapshot, startDate, endDate,
//       status, daysUntilEnd, expiringSoon } | null

// Whole-day span between two ISO date-only strings (YYYY-MM-DD).
// Parses as UTC midnight to avoid the DST risk of new Date(dateOnlyString)
// (CLAUDE.md domain convention). Returns 0 if either bound is missing/invalid.
export function subTotalDays(startDate, endDate) {
  if (!startDate || !endDate) return 0;
  const start = Date.parse(`${startDate}T00:00:00Z`);
  const end = Date.parse(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return 0;
  return Math.max(0, Math.round((end - start) / 86_400_000));
}

export function toSubInfo(membership) {
  if (!membership) {
    return { daysLeft: 0, total: 0, until: '—', label: 'Нет абонемента', tone: 'danger' };
  }
  const daysLeft = Math.max(0, membership.daysUntilEnd ?? 0);
  const tone = membership.expiringSoon
    ? (daysLeft === 0 ? 'danger' : 'warn')
    : 'ok';
  return {
    daysLeft,
    // Derive the real plan duration from startDate/endDate instead of a
    // hardcoded 90 so the progress bar reflects the actual membership length.
    total: subTotalDays(membership.startDate, membership.endDate),
    until: membership.endDate ?? '—',
    label: membership.planNameSnapshot ?? 'Абонемент',
    tone,
  };
}
