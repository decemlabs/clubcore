// Subscription state computer
export function getSubInfo(subState) {
  if (subState === 'active') {
    return { daysLeft: 47, total: 90, until: '16 июня', label: 'Годовой', tone: 'ok' };
  }
  if (subState === 'expiring') {
    return { daysLeft: 7, total: 90, until: '7 мая', label: 'Месячный', tone: 'warn' };
  }
  return { daysLeft: 0, total: 90, until: '24 апреля', label: 'Месячный (истёк)', tone: 'danger' };
}
