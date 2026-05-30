// D-71-08: Net-new screen — mock data stripped, rendered as "В разработке" placeholder.
// The chat/messaging domain is out of scope for Phase 71 and v2.0 entirely
// (requires a staff-side component in the frozen admin-web). Mock conversation data
// removed per D-71-08 — no stale-mock confusion, smaller bundle.
// When a real chat backend is built in a future phase, this file will be wired
// to the real data source via the data/index.js swap seam.
import React from 'react';
import { ComingSoon } from '@/components/ComingSoon.tsx';

export const ChatScreen = ({
  tweaks: _tweaks,
  initialConv: _initialConv,
  onClearInitial: _onClearInitial,
  onThreadOpen: _onThreadOpen,
}) => {
  return <ComingSoon title="Сообщения" />;
};
