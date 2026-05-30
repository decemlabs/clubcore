// D-71-08: Net-new screen — mock data stripped, rendered as "В разработке" placeholder.
// The gym-info backend domain is out of scope for Phase 71 (PWA-05 covers only the 6
// core screens). When a real gym-info backend is built in a future phase, this file
// will be wired to the real data source via the data/index.js swap seam.
import React from 'react';
import { ComingSoon } from '@/components/ComingSoon.tsx';

export const GymInfoSheet = ({ onClose: _onClose }) => {
  return <ComingSoon title="Информация о зале" />;
};
