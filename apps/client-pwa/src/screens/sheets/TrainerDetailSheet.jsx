// D-71-08: Net-new screen — mock data stripped, rendered as "В разработке" placeholder.
// The trainer detail/bio/reviews domain is out of scope for Phase 71.
// When real trainer-detail data is available in a future phase, this file will be wired
// to the real data source via the data/index.js swap seam.
import React from 'react';
import { ComingSoon } from '@/components/ComingSoon.tsx';

export const TrainerDetailSheet = ({
  trainer: _trainer,
  onClose: _onClose,
  onBook: _onBook,
  onCheckout: _onCheckout,
}) => {
  return <ComingSoon title="Тренер" />;
};
