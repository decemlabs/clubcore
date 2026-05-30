// D-71-08: Net-new screen — mock data stripped, rendered as "В разработке" placeholder.
// The referral/invite-friend domain is out of scope for Phase 71.
// When a real referral backend is built in a future phase, this file will be wired
// to the real data source via the data/index.js swap seam.
import React from 'react';
import { ComingSoon } from '@/components/ComingSoon.tsx';

export const ReferralSheet = ({ onClose: _onClose, userName: _userName }) => {
  return <ComingSoon title="Привести друга" />;
};
