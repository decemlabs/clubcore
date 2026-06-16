/**
 * "В разработке" shared placeholder (D-71-08).
 *
 * Net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet,
 * NotificationsSheet, GymInfoSheet) are coming-soon placeholders — they
 * import ONLY this component, no query layer (D-71-09).
 *
 * No React import needed — uses the new JSX transform (react-jsx, D-69-07).
 * No clientFetcher, no clientQueries, no @tanstack/react-query imports.
 */

/**
 * Centered "в разработке" (coming soon) placeholder card.
 * @param title - Optional section name shown above the copy (defaults to 'Скоро').
 */
export function ComingSoon({ title = 'Скоро' }: { title?: string }) {
  return (
    <div
      className="page"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 32,
      }}
    >
      <div className="t-h2">{title}</div>
      <div className="t-small" style={{ color: 'var(--text-3)', textAlign: 'center' }}>
        В разработке
      </div>
    </div>
  )
}
