/**
 * Settings domain Zod schemas (Phase 104 SET-01 + Phase 108 CFG-01/02/03/04).
 *
 * Defines wire shapes for:
 *   GET /api/v1/auth/sessions → {data: {items, total, page, pageSize}}
 *   GET/PUT /api/v1/gym        → GymInfo wire + form validation (CFG-01)
 *   GET/PUT /api/v1/settings/hours        → WorkingHours (CFG-02)
 *   GET/PUT /api/v1/settings/booking      → BookingConfig (CFG-03)
 *   GET/PUT /api/v1/settings/notifications → NotificationPrefs (CFG-04)
 *
 * All fields camelCase (alias_generator=to_camel on backend ContractModel).
 *
 * Zod seam: each Update schema doubles as the react-hook-form resolver AND the
 * PUT request body — the same schema validates form input before submission.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Session (Phase 104 SET-01) — do NOT modify
// ---------------------------------------------------------------------------

export const SessionSchema = z.object({
  familyId: z.string(),
  createdAt: z.string(),
  lastUsedAt: z.string(),
  userAgent: z.string().nullable(),
  channel: z.string(), // 'admin_web' | 'api'
  isCurrent: z.boolean(),
});

export const SessionsListResponseSchema = z.object({
  data: z.object({
    items: z.array(SessionSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type SessionData = z.infer<typeof SessionSchema>;
export type SessionsListData = z.infer<typeof SessionsListResponseSchema>['data'];

// ---------------------------------------------------------------------------
// GymInfo (CFG-01) — wire shape from GET/PUT /api/v1/gym
// ---------------------------------------------------------------------------

export const GymInfoSchema = z.object({
  name: z.string(),
  address: z.string(), // NOT nullable — mirrors backend Mapped[str] NOT NULL (WR-01)
  tagline: z.string().nullable(),
  city: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  latitude: z.number().nullable(),
  longitude: z.number().nullable(),
  hours: z.array(z.unknown()),
  // Backend returns amenities as objects [{icon,label}], not strings — keep as
  // passthrough so the gym card loads (BranchSection form doesn't read amenities). (UAT BUG-3)
  amenities: z.array(z.unknown()),
  rules: z.array(z.string()),
  social: z.array(z.unknown()),
});

export const GymInfoResponseSchema = z.object({ data: GymInfoSchema });

/**
 * BranchSection form schema (Zod seam — validates react-hook-form input AND PUT body).
 * Note: nameShort maps to GymInfo.name field on the backend (short public name).
 */
// Mirror backend GymInfoUpdateRequest (extra='forbid'): name/address/phone/email/
// lat/lng only. `nameShort` and `description` are vestigial UI-only fields the
// backend rejects — they must NOT be in the PUT body. (UAT BUG-6)
export const GymInfoUpdateSchema = z.object({
  name: z.string().min(1).max(120),
  address: z.string().min(1),
  latitude: z.number().min(-90).max(90).nullable().optional(),
  longitude: z.number().min(-180).max(180).nullable().optional(),
  phone: z.string().max(20).nullable().optional(),
  email: z.string().email().nullable().optional(),
});

export type GymInfoData = z.infer<typeof GymInfoSchema>;
export type GymInfoUpdateInput = z.infer<typeof GymInfoUpdateSchema>;

// ---------------------------------------------------------------------------
// WorkingHours (CFG-02) — wire shape from GET/PUT /api/v1/settings/hours
// ---------------------------------------------------------------------------

/**
 * WorkingHours wire schema.
 * schedule/breaks/closures are passthrough JSONB arrays — the backend does
 * not validate their internal structure (UI-SPEC defines the shape).
 */
export const WorkingHoursSchema = z.object({
  schedule: z.array(z.unknown()),
  breaks: z.array(z.unknown()),
  closures: z.array(z.unknown()),
});

export const WorkingHoursResponseSchema = z.object({ data: WorkingHoursSchema });

/** One row in the weekly schedule array (embedded in WorkingHoursUpdateSchema). */
const ScheduleDaySchema = z.object({
  // Wire key is `day_of_week` (0=Mon … 6=Sun) — matches backend seed +
  // /settings/hours response + booking-enforcement SQL. (UAT BUG-4)
  day_of_week: z.number().int().min(0).max(6),
  open: z.string().regex(/^\d{2}:\d{2}$/, 'Введите время в формате ЧЧ:ММ'),
  close: z.string().regex(/^\d{2}:\d{2}$/, 'Введите время в формате ЧЧ:ММ'),
  closed: z.boolean().optional(),
});

/**
 * WorkingHours update schema (Zod seam — validates form + request body).
 * Enforces close > open per day and that breaks fall within the day's window.
 */
export const WorkingHoursUpdateSchema = z
  .object({
    schedule: z.array(ScheduleDaySchema).optional(),
    breaks: z.array(z.unknown()).optional(),
    closures: z.array(z.unknown()).optional(),
  })
  .refine(
    (v) => {
      if (!v.schedule) return true;
      return v.schedule.every((day) => {
        if (day.closed) return true;
        return day.close > day.open;
      });
    },
    { message: 'Время закрытия должно быть позже времени открытия для каждого дня' },
  );

export type WorkingHoursData = z.infer<typeof WorkingHoursSchema>;
export type WorkingHoursUpdateInput = z.infer<typeof WorkingHoursUpdateSchema>;

// ---------------------------------------------------------------------------
// BookingConfig (CFG-03) — wire shape from GET/PUT /api/v1/settings/booking
// ---------------------------------------------------------------------------

/**
 * BookingConfig wire schema.
 * 13 camelCase fields matching backend BookingConfigResponse.
 *
 * MONEY NOTE: noShowPenaltyKopecks is stored and transmitted in kopecks (integer).
 * The BranchSection form displays and accepts the value in RUBLES.
 * Plan 05 must multiply ×100 before submit and divide ÷100 for display.
 */
export const BookingConfigSchema = z.object({
  scheduleStepMinutes: z.number().int(),
  bookingAheadDays: z.number().int(),
  cutoffMinutes: z.number().int(),
  cancelWindowHours: z.number().int(),
  cancelWindowEnabled: z.boolean(),
  rescheduleSameDay: z.boolean(),
  noShowPenaltyKopecks: z.number().int(),
  noShowPenaltyEnabled: z.boolean(),
  groupLimit: z.number().int(),
  waitlistLimit: z.number().int(),
  waitlistAutoTransfer: z.boolean(),
  clientSelfBook: z.boolean(),
  showTrainerWindows: z.boolean(),
});

export const BookingConfigResponseSchema = z.object({ data: BookingConfigSchema });

/**
 * BookingConfig update schema (Zod seam).
 * Bounds mirror the backend BookingConfigUpdateRequest validation.
 * noShowPenaltyKopecks must be ≥ 0 (the UI sends kopecks, not rubles).
 */
export const BookingConfigUpdateSchema = z.object({
  scheduleStepMinutes: z.union([
    z.literal(15),
    z.literal(30),
    z.literal(60),
    z.literal(90),
  ]),
  bookingAheadDays: z.number().int().min(1).max(365),
  cutoffMinutes: z.number().int().min(0).max(1440),
  cancelWindowHours: z.number().int().min(1).optional(),
  cancelWindowEnabled: z.boolean().optional(),
  rescheduleSameDay: z.boolean().optional(),
  noShowPenaltyKopecks: z.number().int().min(0).optional(),
  noShowPenaltyEnabled: z.boolean().optional(),
  groupLimit: z.number().int().min(1).optional(),
  waitlistLimit: z.number().int().min(0).optional(),
  waitlistAutoTransfer: z.boolean().optional(),
  clientSelfBook: z.boolean().optional(),
  showTrainerWindows: z.boolean().optional(),
});

export type BookingConfigData = z.infer<typeof BookingConfigSchema>;
export type BookingConfigUpdateInput = z.infer<typeof BookingConfigUpdateSchema>;

// ---------------------------------------------------------------------------
// NotificationPrefs (CFG-04) — wire shape from GET/PUT /api/v1/settings/notifications
// ---------------------------------------------------------------------------

/**
 * NotificationPrefs wire schema.
 * matrix: club-wide per-trigger × per-channel toggle map (JSONB passthrough).
 * senderSignature: up to 11 Latin uppercase chars for SMS/Telegram sender ID.
 * quietHoursStart / quietHoursEnd: HH:MM strings (Europe/Moscow TZ).
 */
export const NotificationPrefsSchema = z.object({
  matrix: z.record(z.unknown()),
  senderSignature: z.string().nullable(),
  quietHoursStart: z.string().nullable(),
  quietHoursEnd: z.string().nullable(),
});

export const NotificationPrefsResponseSchema = z.object({ data: NotificationPrefsSchema });

/**
 * NotificationPrefs update schema (Zod seam).
 * senderSignature: max 11 Latin uppercase characters (SMS/Telegram sender ID limit).
 * quietHours: start ≠ end enforced via .refine(); no max/min (window may cross midnight).
 */
export const NotificationPrefsUpdateSchema = z
  .object({
    matrix: z.record(z.unknown()).optional(),
    senderSignature: z
      .string()
      .max(11, 'до 11 символов')
      .regex(/^[A-Z]*$/, 'только латинские заглавные буквы')
      .nullable()
      .optional(),
    quietHoursStart: z
      .string()
      .regex(/^\d{2}:\d{2}$/, 'Введите время в формате ЧЧ:ММ')
      .nullable()
      .optional(),
    quietHoursEnd: z
      .string()
      .regex(/^\d{2}:\d{2}$/, 'Введите время в формате ЧЧ:ММ')
      .nullable()
      .optional(),
  })
  .refine(
    (v) => {
      if (v.quietHoursStart == null || v.quietHoursEnd == null) return true;
      return v.quietHoursStart !== v.quietHoursEnd;
    },
    { message: 'Время начала и конца тихих часов не должны совпадать' },
  );

export type NotificationPrefsData = z.infer<typeof NotificationPrefsSchema>;
export type NotificationPrefsUpdateInput = z.infer<typeof NotificationPrefsUpdateSchema>;
