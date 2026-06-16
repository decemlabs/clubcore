/** Тона тегов диалога (вынесено из компонентов ради react-refresh). */
import type { TagTone } from '@/features/messages/types';

export const TAG_TONE: Record<TagTone, string> = {
  urgent: 'bg-danger-soft text-danger',
  neutral: 'bg-surface-3 text-fg-muted',
  staff: 'bg-lead-soft text-lead',
  complaint: 'bg-warning-soft text-warning-deep',
  review: 'bg-primary-soft text-primary-deep dark:text-primary',
};
