// D-71-08: Net-new screen — mock data stripped, rendered as "В разработке" placeholder.
// The in-app notification inbox domain is out of scope for Phase 71 (notifications
// remain push-only via Telegram/email per the v2.0 scope decision).
// When a client-readable notification feed is built in a future phase, this file
// will be wired to the real data source via the data/index.js swap seam.
import React from 'react';
import { ComingSoon } from '@/components/ComingSoon.tsx';

export const NotificationsSheet = ({ onClose: _onClose, onOpenChat: _onOpenChat }) => {
  return <ComingSoon title="Уведомления" />;
};
