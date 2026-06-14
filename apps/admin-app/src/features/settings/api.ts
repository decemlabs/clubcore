/**
 * Settings domain TanStack Query hooks (Phase 104 SET-01 + Phase 108 CFG-01/02/03/04).
 *
 * Profile is read-only: ProfileSection reuses useSession() from features/auth/api.ts.
 * No PATCH /auth/me endpoint exists — profile edit is deferred (Phase 104).
 *
 * Sessions:
 *   useSessions()             — GET /api/v1/auth/sessions (list)
 *   useRevokeSession()        — POST /api/v1/auth/sessions/{family_id}/revoke (non-current)
 *   useRevokeCurrentSession() — POST same endpoint for the current session; on 204 publishes
 *                               session_expired via authBus → RequireAuth redirects to /login.
 *                               Does NOT navigate directly (T-104-09 mitigation).
 *
 * Gym card (CFG-01):
 *   useGymInfo(role)          — GET /api/v1/gym  [enabled: can(role,'edit','gym')]
 *   useUpdateGymInfo()        — PUT /api/v1/gym
 *
 * Working hours (CFG-02):
 *   useWorkingHours(role)     — GET /api/v1/settings/hours  [enabled: can(role,'edit','settings')]
 *   useUpdateWorkingHours()   — PUT /api/v1/settings/hours
 *
 * Booking config (CFG-03):
 *   useBookingConfig(role)    — GET /api/v1/settings/booking  [enabled: can(role,'edit','settings')]
 *   useUpdateBookingConfig()  — PUT /api/v1/settings/booking
 *
 * Notification prefs (CFG-04):
 *   useNotificationPrefs(role)       — GET /api/v1/settings/notifications  [enabled: can(role,'edit','settings')]
 *   useUpdateNotificationPrefs()     — PUT /api/v1/settings/notifications
 *
 * Reception zero-calls discipline (T-104-12 mirror):
 *   Every settings GET query uses `enabled: can(role, 'edit', ...)` so reception fires
 *   zero requests. The backend 403 is the authority; the enabled gate is defense-in-depth.
 *
 * NOTE — PATH TYPES: /api/v1/settings/{hours,booking,notifications} are new endpoints
 *   landed in Phase 108-02. They are NOT yet in packages/api-client/src/schema.d.ts
 *   (Phase 111 regenerates openapi.json + schema.d.ts additively). Until then, these
 *   paths are cast `as never` at the staffRequest call site — the runtime path string
 *   is correct; only the compile-time `paths` type is ahead of the schema. (D-V31-CONTRACT-ADDITIVE)
 *
 * useMockSettingsData() — mock compat for sections not yet wired (Branch/Hours/Booking/Payments/
 *   Notifications/App/Integrations/Billing). Renamed from `useSettings` so the old mock is gone.
 *   TODO: Remove when all SettingsPage sections are wired to real endpoints.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { staffRequest, mockResponse, ApiError } from '@/api/client';
import { publishSessionExpired } from '@/lib/authBus';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import { settingsData } from '@/mocks/settings';
import type { SettingsData } from './types';
import {
  SessionsListResponseSchema,
  GymInfoResponseSchema,
  GymInfoSchema,
  WorkingHoursResponseSchema,
  WorkingHoursSchema,
  BookingConfigResponseSchema,
  BookingConfigSchema,
  NotificationPrefsResponseSchema,
  NotificationPrefsSchema,
  type GymInfoUpdateInput,
  type WorkingHoursUpdateInput,
  type BookingConfigUpdateInput,
  type NotificationPrefsUpdateInput,
} from './schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const settingsKeys = {
  sessions: ['auth', 'sessions'] as const,
  gymInfo: ['settings', 'gym'] as const,
  workingHours: ['settings', 'hours'] as const,
  bookingConfig: ['settings', 'booking'] as const,
  notificationPrefs: ['settings', 'notifications'] as const,
};

// ---------------------------------------------------------------------------
// useSessions — list active sessions
// ---------------------------------------------------------------------------

export function useSessions() {
  return useQuery({
    queryKey: settingsKeys.sessions,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/auth/sessions');
      return SessionsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// useRevokeSession — revoke a NON-current session
// ---------------------------------------------------------------------------

/**
 * Revokes a session by familyId (for non-current sessions only).
 * On 204 success: invalidates the sessions query so the row is removed.
 * For the CURRENT session, use useRevokeCurrentSession instead.
 */
export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (familyId: string) =>
      staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {
        params: { family_id: familyId },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: settingsKeys.sessions });
    },
  });
}

// ---------------------------------------------------------------------------
// useRevokeCurrentSession — self-revoke via authBus (T-104-09)
// ---------------------------------------------------------------------------

/**
 * Self-revokes the CURRENT session.
 * On 204 success: publishes session_expired via authBus — the same path
 * that RequireAuth subscribes to (T-100-09). This clears the auth cache and
 * navigates to /login?state=expired without a direct navigate() call here.
 *
 * Do NOT use this for non-current sessions — it triggers a full logout flow.
 */
export function useRevokeCurrentSession() {
  return useMutation({
    mutationFn: (familyId: string) =>
      staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {
        params: { family_id: familyId },
      }),
    onSuccess: () => {
      // Route through authBus session-expiry path (same as mid-session 401):
      // RequireAuth subscriber removes authKeys.me + navigates to /login?state=expired.
      publishSessionExpired();
    },
  });
}

// ---------------------------------------------------------------------------
// useGymInfo — GET /api/v1/gym (CFG-01)
// ---------------------------------------------------------------------------

/**
 * Fetches gym card info.
 * Gated: can(role,'edit','gym') — reception fires ZERO requests (T-104-12 mirror).
 * The backend EDIT gate (not VIEW) on /gym is intentional — gym card is owner-only end-to-end.
 */
export function useGymInfo(role: Role) {
  return useQuery({
    queryKey: settingsKeys.gymInfo,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/gym');
      return GymInfoResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'edit', 'gym'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// useUpdateGymInfo — PUT /api/v1/gym (CFG-01)
// ---------------------------------------------------------------------------

/**
 * Updates gym card fields.
 * No Idempotency-Key — upsert endpoint (same row every time, idempotent by design).
 * 422 field errors accessible via ApiError.fields for inline display in BranchSection.
 */
export function useUpdateGymInfo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: GymInfoUpdateInput) => {
      const raw = await staffRequest('put', '/api/v1/gym', { body });
      return GymInfoSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('Карточка зала обновлена');
      void qc.invalidateQueries({ queryKey: settingsKeys.gymInfo });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось сохранить изменения. Попробуйте ещё раз.');
    },
  });
}

// ---------------------------------------------------------------------------
// useWorkingHours — GET /api/v1/settings/hours (CFG-02)
// ---------------------------------------------------------------------------

/**
 * Fetches working hours / breaks / closures.
 * Gated: can(role,'edit','settings') — reception fires ZERO requests.
 */
export function useWorkingHours(role: Role) {
  return useQuery({
    queryKey: settingsKeys.workingHours,
    queryFn: async () => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest('get' as never, '/api/v1/settings/hours' as never);
      return WorkingHoursResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'edit', 'settings'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// useUpdateWorkingHours — PUT /api/v1/settings/hours (CFG-02)
// ---------------------------------------------------------------------------

/**
 * Updates working hours / breaks / closures.
 * No Idempotency-Key — upsert endpoint.
 */
export function useUpdateWorkingHours() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: WorkingHoursUpdateInput) => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest('put' as never, '/api/v1/settings/hours' as never, { body });
      return WorkingHoursSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('График работы обновлён');
      void qc.invalidateQueries({ queryKey: settingsKeys.workingHours });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось сохранить изменения. Попробуйте ещё раз.');
    },
  });
}

// ---------------------------------------------------------------------------
// useBookingConfig — GET /api/v1/settings/booking (CFG-03)
// ---------------------------------------------------------------------------

/**
 * Fetches booking rules configuration.
 * Gated: can(role,'edit','settings') — reception fires ZERO requests.
 */
export function useBookingConfig(role: Role) {
  return useQuery({
    queryKey: settingsKeys.bookingConfig,
    queryFn: async () => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest('get' as never, '/api/v1/settings/booking' as never);
      return BookingConfigResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'edit', 'settings'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// useUpdateBookingConfig — PUT /api/v1/settings/booking (CFG-03)
// ---------------------------------------------------------------------------

/**
 * Updates booking rules.
 * No Idempotency-Key — upsert endpoint.
 * MONEY: noShowPenaltyKopecks is in kopecks — Plan 05 must multiply ×100 before calling.
 */
export function useUpdateBookingConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BookingConfigUpdateInput) => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest('put' as never, '/api/v1/settings/booking' as never, { body });
      return BookingConfigSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('Правила записи обновлены');
      void qc.invalidateQueries({ queryKey: settingsKeys.bookingConfig });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось сохранить изменения. Попробуйте ещё раз.');
    },
  });
}

// ---------------------------------------------------------------------------
// useNotificationPrefs — GET /api/v1/settings/notifications (CFG-04)
// ---------------------------------------------------------------------------

/**
 * Fetches notification preferences (matrix + sender signature + quiet hours).
 * Gated: can(role,'edit','settings') — reception fires ZERO requests.
 */
export function useNotificationPrefs(role: Role) {
  return useQuery({
    queryKey: settingsKeys.notificationPrefs,
    queryFn: async () => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest('get' as never, '/api/v1/settings/notifications' as never);
      return NotificationPrefsResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'edit', 'settings'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// useUpdateNotificationPrefs — PUT /api/v1/settings/notifications (CFG-04)
// ---------------------------------------------------------------------------

/**
 * Updates notification preferences.
 * No Idempotency-Key — upsert endpoint.
 */
export function useUpdateNotificationPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: NotificationPrefsUpdateInput) => {
      // Path cast: not yet in schema.d.ts — regenerated in Phase 111 (D-V31-CONTRACT-ADDITIVE)
      const raw = await staffRequest(
        'put' as never,
        '/api/v1/settings/notifications' as never,
        { body },
      );
      return NotificationPrefsSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('Настройки уведомлений обновлены');
      void qc.invalidateQueries({ queryKey: settingsKeys.notificationPrefs });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось сохранить изменения. Попробуйте ещё раз.');
    },
  });
}

// ---------------------------------------------------------------------------
// useMockSettingsData — mock compat for unwired sections
// ---------------------------------------------------------------------------

/**
 * Mock settings data for sections not yet wired to the backend.
 * ProfileSection and SecuritySection are self-fetching (Plan 104-04).
 * TeamSection will be wired in Plan 104-05.
 * Renamed from `useSettings` (the old mock hook is removed).
 */
export function useMockSettingsData() {
  return useQuery({
    queryKey: ['settings', 'mock'],
    queryFn: () => mockResponse<SettingsData>(settingsData),
  });
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { ApiError };
