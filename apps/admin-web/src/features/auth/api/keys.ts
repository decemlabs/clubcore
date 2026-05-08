/**
 * TanStack Query keys for the auth feature.
 * TkDodo factory pattern — every consumer (loader, hook, invalidate) reads
 * keys from here so cache writes stay in sync.
 */
export const authKeys = {
  all: ['auth'] as const,
  me: ['auth', 'me'] as const,
  sessions: ['auth', 'sessions'] as const,
  telegramStatus: (token: string) => ['auth', 'telegram-status', token] as const,
} as const
