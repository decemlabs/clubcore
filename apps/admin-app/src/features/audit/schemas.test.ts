/**
 * TDD tests for AuditEventSchema + AuditLogResponseSchema (Phase 104-01 Task 3).
 * RED phase: written before schemas.ts and new api.ts exist.
 */
import { describe, expect, it } from 'vitest';
import { AuditEventSchema, AuditLogResponseSchema } from './schemas';
import { auditKeys } from './api';

describe('AuditEventSchema', () => {
  it('parses a full audit event with all fields', () => {
    const raw = {
      id: 'evt-1',
      createdAt: '2025-06-01T12:00:00Z',
      actorUserId: 'user-1',
      actorEmailSnapshot: 'admin@example.com',
      action: 'create',
      resourceType: 'client',
      resourceId: 'client-1',
      payload: { name: 'Иван' },
    };
    const result = AuditEventSchema.parse(raw);
    expect(result.id).toBe('evt-1');
    expect(result.actorEmailSnapshot).toBe('admin@example.com');
    expect(result.resourceId).toBe('client-1');
    expect(result.payload).toEqual({ name: 'Иван' });
  });

  it('allows nullable resourceId', () => {
    const result = AuditEventSchema.parse({
      id: 'evt-2',
      createdAt: '2025-06-01T12:00:00Z',
      actorUserId: 'user-1',
      actorEmailSnapshot: 'admin@example.com',
      action: 'view',
      resourceType: 'reports',
      resourceId: null,
      payload: null,
    });
    expect(result.resourceId).toBeNull();
    expect(result.payload).toBeNull();
  });

  it('accepts payload as an arbitrary record', () => {
    const result = AuditEventSchema.parse({
      id: 'evt-3',
      createdAt: '2025-06-01T12:00:00Z',
      actorUserId: 'user-1',
      actorEmailSnapshot: 'admin@example.com',
      action: 'delete',
      resourceType: 'membership',
      resourceId: 'mem-1',
      payload: { reason: 'expired', count: 1 },
    });
    expect(result.payload).toEqual({ reason: 'expired', count: 1 });
  });
});

describe('AuditLogResponseSchema', () => {
  it('parses a full paginated audit log response', () => {
    const raw = {
      data: {
        items: [
          {
            id: 'evt-1',
            createdAt: '2025-06-01T12:00:00Z',
            actorUserId: 'user-1',
            actorEmailSnapshot: 'admin@example.com',
            action: 'create',
            resourceType: 'client',
            resourceId: null,
            payload: null,
          },
        ],
        total: 1,
        page: 1,
        pageSize: 25,
      },
    };
    const result = AuditLogResponseSchema.parse(raw).data;
    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);
    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(25);
  });

  it('parses an empty items array', () => {
    const result = AuditLogResponseSchema.parse({
      data: { items: [], total: 0, page: 1, pageSize: 25 },
    }).data;
    expect(result.items).toHaveLength(0);
    expect(result.total).toBe(0);
  });
});

describe('auditKeys', () => {
  it('list key differs per filter object', () => {
    const f1 = { actorEmailSnapshot: 'admin@example.com' };
    const f2 = { resourceType: 'client' };
    expect(auditKeys.list(f1)).not.toEqual(auditKeys.list(f2));
  });

  it('lists() is a prefix of list(filter)', () => {
    const filter = { page: 1 };
    const listKey = auditKeys.list(filter);
    const listsKey = auditKeys.lists();
    // list key must start with the lists key path
    expect(listKey.slice(0, listsKey.length)).toEqual(listsKey);
  });
});
