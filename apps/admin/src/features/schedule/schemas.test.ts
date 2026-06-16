/**
 * Schedule domain schemas — Zod contract tests (Phase 102-01).
 *
 * Pure Zod schema validation — no network, no React.
 */
import { describe, it, expect } from 'vitest';
import {
  TrainerSlotSchema,
  TrainerSlotListResponseSchema,
  PublishSlotSchema,
  CancelSlotSchema,
  CreateTemplateSchema,
  CreateTimeOffSchema,
  RecurringTemplateSchema,
  TimeOffSchema,
} from './schemas';

// ---------------------------------------------------------------------------
// TrainerSlotSchema
// ---------------------------------------------------------------------------

describe('TrainerSlotSchema', () => {
  const validSlot = {
    id: 'slot-1',
    trainerId: 'trainer-1',
    startTime: '2026-06-15T10:00:00Z',
    endTime: '2026-06-15T11:00:00Z',
    status: 'active' as const,
    createdAt: '2026-06-13T00:00:00Z',
  };

  it('parses a valid wire slot', () => {
    const result = TrainerSlotSchema.parse(validSlot);
    expect(result.id).toBe('slot-1');
    expect(result.status).toBe('active');
  });

  it('accepts all status enum values', () => {
    for (const status of ['active', 'cancelled', 'booked'] as const) {
      const result = TrainerSlotSchema.parse({ ...validSlot, status });
      expect(result.status).toBe(status);
    }
  });

  it('rejects invalid status', () => {
    expect(() => TrainerSlotSchema.parse({ ...validSlot, status: 'pending' })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// TrainerSlotListResponseSchema
// ---------------------------------------------------------------------------

describe('TrainerSlotListResponseSchema', () => {
  it('parses a valid list response and exposes .data.items', () => {
    const raw = {
      data: {
        items: [],
        total: 0,
        page: 1,
        pageSize: 25,
      },
    };
    const result = TrainerSlotListResponseSchema.parse(raw);
    expect(result.data.total).toBe(0);
    expect(result.data.items).toHaveLength(0);
  });

  it('parses a list response with items', () => {
    const raw = {
      data: {
        items: [
          {
            id: 'slot-1',
            trainerId: 'trainer-1',
            startTime: '2026-06-15T10:00:00Z',
            endTime: '2026-06-15T11:00:00Z',
            status: 'active',
            createdAt: '2026-06-13T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        pageSize: 25,
      },
    };
    const result = TrainerSlotListResponseSchema.parse(raw);
    expect(result.data.items).toHaveLength(1);
    expect(result.data.items[0]?.id).toBe('slot-1');
  });
});

// ---------------------------------------------------------------------------
// PublishSlotSchema
// ---------------------------------------------------------------------------

describe('PublishSlotSchema', () => {
  it('accepts valid publish input', () => {
    const result = PublishSlotSchema.parse({
      trainerId: 'trainer-1',
      startTime: '2026-06-15T10:00:00Z',
      endTime: '2026-06-15T11:00:00Z',
    });
    expect(result.trainerId).toBe('trainer-1');
  });

  it('rejects empty trainerId with Russian message', () => {
    expect(() =>
      PublishSlotSchema.parse({
        trainerId: '',
        startTime: '2026-06-15T10:00:00Z',
        endTime: '2026-06-15T11:00:00Z',
      }),
    ).toThrow('Выберите тренера');
  });

  it('rejects missing trainerId', () => {
    expect(() =>
      PublishSlotSchema.parse({
        startTime: '2026-06-15T10:00:00Z',
        endTime: '2026-06-15T11:00:00Z',
      }),
    ).toThrow();
  });
});

// ---------------------------------------------------------------------------
// CancelSlotSchema
// ---------------------------------------------------------------------------

describe('CancelSlotSchema', () => {
  it('accepts cancelReason 1-200 chars', () => {
    const result = CancelSlotSchema.parse({ cancelReason: 'Тренер заболел' });
    expect(result.cancelReason).toBe('Тренер заболел');
  });

  it('rejects empty cancelReason', () => {
    expect(() => CancelSlotSchema.parse({ cancelReason: '' })).toThrow();
  });

  it('rejects cancelReason longer than 200 chars', () => {
    expect(() => CancelSlotSchema.parse({ cancelReason: 'a'.repeat(201) })).toThrow();
  });

  it('accepts exactly 200 chars', () => {
    const result = CancelSlotSchema.parse({ cancelReason: 'a'.repeat(200) });
    expect(result.cancelReason).toHaveLength(200);
  });
});

// ---------------------------------------------------------------------------
// CreateTemplateSchema
// ---------------------------------------------------------------------------

describe('CreateTemplateSchema', () => {
  it('accepts valid template input', () => {
    const result = CreateTemplateSchema.parse({
      trainerId: 'trainer-1',
      dayOfWeek: 1,
      startTime: '10:00',
      endTime: '11:00',
      validFrom: '2026-06-15',
    });
    expect(result.dayOfWeek).toBe(1);
  });

  it('enforces dayOfWeek int 0-6', () => {
    expect(() =>
      CreateTemplateSchema.parse({
        trainerId: 'trainer-1',
        dayOfWeek: 7,
        startTime: '10:00',
        endTime: '11:00',
        validFrom: '2026-06-15',
      }),
    ).toThrow();
    expect(() =>
      CreateTemplateSchema.parse({
        trainerId: 'trainer-1',
        dayOfWeek: -1,
        startTime: '10:00',
        endTime: '11:00',
        validFrom: '2026-06-15',
      }),
    ).toThrow();
  });

  it('accepts dayOfWeek 0 (Sunday)', () => {
    const result = CreateTemplateSchema.parse({
      trainerId: 'trainer-1',
      dayOfWeek: 0,
      startTime: '10:00',
      endTime: '11:00',
      validFrom: '2026-06-15',
    });
    expect(result.dayOfWeek).toBe(0);
  });

  it('rejects empty trainerId with Russian message', () => {
    expect(() =>
      CreateTemplateSchema.parse({
        trainerId: '',
        dayOfWeek: 1,
        startTime: '10:00',
        endTime: '11:00',
        validFrom: '2026-06-15',
      }),
    ).toThrow('Выберите тренера');
  });

  it('accepts optional validUntil', () => {
    const result = CreateTemplateSchema.parse({
      trainerId: 'trainer-1',
      dayOfWeek: 3,
      startTime: '10:00',
      endTime: '11:00',
      validFrom: '2026-06-15',
      validUntil: '2026-12-31',
    });
    expect(result.validUntil).toBe('2026-12-31');
  });
});

// ---------------------------------------------------------------------------
// CreateTimeOffSchema
// ---------------------------------------------------------------------------

describe('CreateTimeOffSchema', () => {
  it('requires blockStart and blockEnd', () => {
    const result = CreateTimeOffSchema.parse({
      trainerId: 'trainer-1',
      blockStart: '2026-06-20T00:00:00Z',
      blockEnd: '2026-06-21T00:00:00Z',
    });
    expect(result.blockStart).toBe('2026-06-20T00:00:00Z');
    expect(result.blockEnd).toBe('2026-06-21T00:00:00Z');
  });

  it('rejects empty trainerId with Russian message', () => {
    expect(() =>
      CreateTimeOffSchema.parse({
        trainerId: '',
        blockStart: '2026-06-20T00:00:00Z',
        blockEnd: '2026-06-21T00:00:00Z',
      }),
    ).toThrow('Выберите тренера');
  });

  it('accepts optional reason', () => {
    const result = CreateTimeOffSchema.parse({
      trainerId: 'trainer-1',
      blockStart: '2026-06-20T00:00:00Z',
      blockEnd: '2026-06-21T00:00:00Z',
      reason: 'Болезнь',
    });
    expect(result.reason).toBe('Болезнь');
  });
});

// ---------------------------------------------------------------------------
// RecurringTemplateSchema
// ---------------------------------------------------------------------------

describe('RecurringTemplateSchema', () => {
  it('parses a valid recurring template', () => {
    const result = RecurringTemplateSchema.parse({
      id: 'tmpl-1',
      trainerId: 'trainer-1',
      dayOfWeek: 1,
      startTime: '10:00',
      endTime: '11:00',
      validFrom: '2026-06-15',
      isActive: true,
    });
    expect(result.id).toBe('tmpl-1');
    expect(result.isActive).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// TimeOffSchema
// ---------------------------------------------------------------------------

describe('TimeOffSchema', () => {
  it('parses a valid time-off block', () => {
    const result = TimeOffSchema.parse({
      id: 'off-1',
      trainerId: 'trainer-1',
      blockStart: '2026-06-20T00:00:00Z',
      blockEnd: '2026-06-21T00:00:00Z',
      createdAt: '2026-06-13T00:00:00Z',
    });
    expect(result.id).toBe('off-1');
  });

  it('accepts optional reason', () => {
    const result = TimeOffSchema.parse({
      id: 'off-1',
      trainerId: 'trainer-1',
      blockStart: '2026-06-20T00:00:00Z',
      blockEnd: '2026-06-21T00:00:00Z',
      reason: 'Отпуск',
      createdAt: '2026-06-13T00:00:00Z',
    });
    expect(result.reason).toBe('Отпуск');
  });
});
