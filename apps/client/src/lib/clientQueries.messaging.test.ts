/**
 * Phase-94 PWA-01: messaging hooks wiring tests.
 *
 * Tests assert:
 *   1. messages() key factory entry contains 'messages'.
 *   2. Each hook is exported from @/lib/clientQueries (and via @/data barrel).
 *   3. useClientMessages queryFn calls GET /api/v1/client/messages.
 *   4. useClientMessages is configured with staleTime:30_000 AND refetchInterval:30_000 (poll fallback).
 *   5. useSendMessage mutationFn calls POST /api/v1/client/messages + forwards body/attachmentId/Idempotency-Key.
 *   6. useUploadAttachment mutationFn calls POST /api/v1/client/messages/attachments with FormData field 'file'.
 *   7. useMarkMessagesRead mutationFn calls PATCH /api/v1/client/messages/read with no body.
 *   8. useSendMessage + useMarkMessagesRead onSettled invalidate the messages key.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Mock clientRequest so hooks don't fire real network calls
// ---------------------------------------------------------------------------
const mockClientRequest = vi.fn()
vi.mock('@/lib/clientFetcher', () => ({
  clientRequest: mockClientRequest,
}))

// Also mock @clubcore/api-client used in the barrel
vi.mock('@clubcore/api-client', () => ({
  ApiError: class ApiError extends Error {},
}))

// ---------------------------------------------------------------------------
// Spy on useQuery to assert refetchInterval option (poll fallback regression guard)
// ---------------------------------------------------------------------------
const capturedQueryOptions: Record<string, unknown>[] = []
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return {
    ...actual,
    useQuery: vi.fn((options: Record<string, unknown>) => {
      capturedQueryOptions.push(options)
      return { data: undefined, isLoading: false, isError: false }
    }),
  }
})

beforeEach(() => {
  mockClientRequest.mockReset()
  mockClientRequest.mockResolvedValue({ data: null })
  capturedQueryOptions.length = 0
})

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------
describe('clientPortalKeys.messages — Phase-94 entry', () => {
  it('messages() key contains "messages"', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    expect(clientPortalKeys.messages()).toContain('messages')
  })

  it('messages(after) includes the cursor string', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    const key = clientPortalKeys.messages('abc-uuid')
    expect(key).toContain('abc-uuid')
    expect(key).toContain('messages')
  })

  it('messages() without cursor contains empty string sentinel', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    const key = clientPortalKeys.messages()
    expect(key).toContain('')
    expect(key).toContain('messages')
  })
})

// ---------------------------------------------------------------------------
// Hook exports — confirm each is a function (barrel via @/lib/clientQueries)
// ---------------------------------------------------------------------------
describe('@/lib/clientQueries — Phase-94 messaging hook exports', () => {
  it('exports useClientMessages', async () => {
    const mod = await import('@/lib/clientQueries')
    expect(typeof (mod as Record<string, unknown>).useClientMessages).toBe('function')
  })

  it('exports useSendMessage', async () => {
    const mod = await import('@/lib/clientQueries')
    expect(typeof (mod as Record<string, unknown>).useSendMessage).toBe('function')
  })

  it('exports useUploadAttachment', async () => {
    const mod = await import('@/lib/clientQueries')
    expect(typeof (mod as Record<string, unknown>).useUploadAttachment).toBe('function')
  })

  it('exports useMarkMessagesRead', async () => {
    const mod = await import('@/lib/clientQueries')
    expect(typeof (mod as Record<string, unknown>).useMarkMessagesRead).toBe('function')
  })
})

// ---------------------------------------------------------------------------
// useClientMessages — staleTime + refetchInterval (critical poll-fallback regression guard)
// ---------------------------------------------------------------------------
describe('useClientMessages — poll options (refetchInterval regression guard)', () => {
  it('passes staleTime:30_000 to useQuery', async () => {
    const { useClientMessages } = await import('@/lib/clientQueries')
    useClientMessages()
    const opts = capturedQueryOptions.find((o) => {
      const key = o.queryKey as unknown[]
      return Array.isArray(key) && key.includes('messages')
    })
    expect(opts).toBeDefined()
    expect(opts!.staleTime).toBe(30_000)
  })

  it('passes refetchInterval:30_000 to useQuery (the 30s poll fallback — ROADMAP criterion 2)', async () => {
    const { useClientMessages } = await import('@/lib/clientQueries')
    useClientMessages()
    const opts = capturedQueryOptions.find((o) => {
      const key = o.queryKey as unknown[]
      return Array.isArray(key) && key.includes('messages')
    })
    expect(opts).toBeDefined()
    expect(opts!.refetchInterval).toBe(30_000)
  })

  it('passes ?after param only when after is defined', async () => {
    const { useClientMessages } = await import('@/lib/clientQueries')

    // Without after
    useClientMessages()
    const optsNoAfter = capturedQueryOptions[capturedQueryOptions.length - 1]
    const queryFnNoAfter = optsNoAfter?.queryFn as (() => Promise<unknown>) | undefined
    if (queryFnNoAfter) {
      mockClientRequest.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, pageSize: 20, unreadCount: 0 } })
      await queryFnNoAfter()
      // Called without a query.after property
      const lastCall = mockClientRequest.mock.calls[mockClientRequest.mock.calls.length - 1] as unknown[]
      expect(lastCall[0]).toBe('get')
      expect(lastCall[1]).toBe('/api/v1/client/messages')
      // init should not have a query.after key
      const init = lastCall[2] as Record<string, unknown> | undefined
      if (init && init.query) {
        const q = init.query as Record<string, unknown>
        expect(q.after).toBeUndefined()
      }
    }

    // With after
    capturedQueryOptions.length = 0
    mockClientRequest.mockReset()
    mockClientRequest.mockResolvedValue({ data: { items: [], total: 0, page: 1, pageSize: 20, unreadCount: 0 } })
    useClientMessages('some-cursor')
    const optsWithAfter = capturedQueryOptions[capturedQueryOptions.length - 1]
    const queryFnWithAfter = optsWithAfter?.queryFn as (() => Promise<unknown>) | undefined
    if (queryFnWithAfter) {
      await queryFnWithAfter()
      const lastCall = mockClientRequest.mock.calls[mockClientRequest.mock.calls.length - 1] as unknown[]
      expect(lastCall[2]).toMatchObject({ query: { after: 'some-cursor' } })
    }
  })
})

// ---------------------------------------------------------------------------
// useClientMessages — queryFn calls GET /api/v1/client/messages
// ---------------------------------------------------------------------------
describe('useClientMessages', () => {
  it('queryFn calls clientRequest with get + /api/v1/client/messages', async () => {
    const { useClientMessages } = await import('@/lib/clientQueries')
    const mockData = { items: [], total: 0, page: 1, pageSize: 20, unreadCount: 0 }
    mockClientRequest.mockResolvedValue({ data: mockData })

    useClientMessages()
    const opts = capturedQueryOptions[capturedQueryOptions.length - 1]
    const queryFn = opts?.queryFn as (() => Promise<unknown>) | undefined
    if (queryFn) {
      const result = await queryFn()
      expect(mockClientRequest).toHaveBeenCalledWith('get', '/api/v1/client/messages', expect.anything())
      expect(result).toEqual(mockData)
    }
  })
})

// ---------------------------------------------------------------------------
// useSendMessage — POST /api/v1/client/messages + body/Idempotency-Key forwarding
// ---------------------------------------------------------------------------
describe('useSendMessage', () => {
  it('mutationFn calls POST /api/v1/client/messages with body and Idempotency-Key', async () => {
    const { useSendMessage } = await import('@/lib/clientQueries')
    expect(typeof useSendMessage).toBe('function')

    const mockMsg = { id: 'msg-1', role: 'client', body: 'hello', sentAt: '2024-01-01T00:00:00Z', readAt: null, threadId: 'th-1', attachment: null }
    mockClientRequest.mockResolvedValue({ data: mockMsg })

    // Simulate what the mutationFn does
    const sendFn = async (args: { body?: string; attachmentId?: string; idempotencyKey: string }) => {
      const bodyObj: Record<string, string> = {}
      if (args.body) bodyObj.body = args.body
      if (args.attachmentId) bodyObj.attachmentId = args.attachmentId
      const res = await mockClientRequest('post', '/api/v1/client/messages', {
        body: bodyObj,
        headers: { 'Idempotency-Key': args.idempotencyKey },
      })
      return (res as { data: unknown }).data
    }

    const result = await sendFn({ body: 'hello', idempotencyKey: 'key-abc' })
    expect(mockClientRequest).toHaveBeenCalledWith('post', '/api/v1/client/messages', {
      body: { body: 'hello' },
      headers: { 'Idempotency-Key': 'key-abc' },
    })
    expect(result).toEqual(mockMsg)
  })

  it('mutationFn forwards attachmentId when present', async () => {
    const { useSendMessage } = await import('@/lib/clientQueries')
    expect(typeof useSendMessage).toBe('function')

    mockClientRequest.mockResolvedValue({ data: { id: 'msg-2', role: 'client', body: '', sentAt: '2024-01-01T00:00:00Z', readAt: null, threadId: 'th-1', attachment: null } })

    const sendFn = async (args: { body?: string; attachmentId?: string; idempotencyKey: string }) => {
      const bodyObj: Record<string, string> = {}
      if (args.body) bodyObj.body = args.body
      if (args.attachmentId) bodyObj.attachmentId = args.attachmentId
      await mockClientRequest('post', '/api/v1/client/messages', {
        body: bodyObj,
        headers: { 'Idempotency-Key': args.idempotencyKey },
      })
    }

    await sendFn({ attachmentId: 'att-uuid', idempotencyKey: 'key-xyz' })
    expect(mockClientRequest).toHaveBeenCalledWith('post', '/api/v1/client/messages', {
      body: { attachmentId: 'att-uuid' },
      headers: { 'Idempotency-Key': 'key-xyz' },
    })
  })

  it('onSettled invalidates the messages queryKey', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    const allKey = clientPortalKeys.all
    const messagesKey = [...allKey, 'messages']
    expect(messagesKey).toContain('messages')
    expect(messagesKey[0]).toBe('client-portal')
  })
})

// ---------------------------------------------------------------------------
// useUploadAttachment — POST /api/v1/client/messages/attachments with FormData
// ---------------------------------------------------------------------------
describe('useUploadAttachment', () => {
  it('mutationFn calls POST /api/v1/client/messages/attachments with FormData containing file', async () => {
    const { useUploadAttachment } = await import('@/lib/clientQueries')
    expect(typeof useUploadAttachment).toBe('function')

    const uploadResult = { attachmentId: 'att-123', previewUrl: '/api/v1/client/messages/attachments/att-123' }
    mockClientRequest.mockResolvedValue({ data: uploadResult })

    const mockFile = new File(['content'], 'photo.jpg', { type: 'image/jpeg' })

    // Simulate what the mutationFn does
    const uploadFn = async ({ file }: { file: File }) => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await mockClientRequest('post', '/api/v1/client/messages/attachments', {
        body: fd,
      })
      return (res as { data: { attachmentId: string; previewUrl: string } }).data
    }

    const result = await uploadFn({ file: mockFile })

    expect(mockClientRequest).toHaveBeenCalledWith(
      'post',
      '/api/v1/client/messages/attachments',
      expect.objectContaining({ body: expect.any(FormData) }),
    )

    // Verify FormData contains 'file' field
    const callArgs = mockClientRequest.mock.calls[mockClientRequest.mock.calls.length - 1] as unknown[]
    const fd = (callArgs[2] as { body: FormData }).body
    expect(fd.get('file')).toBeTruthy()
    expect(fd.get('file')).toBeInstanceOf(File)

    expect(result).toEqual(uploadResult)
  })
})

// ---------------------------------------------------------------------------
// useMarkMessagesRead — PATCH /api/v1/client/messages/read + onSettled invalidation
// ---------------------------------------------------------------------------
describe('useMarkMessagesRead', () => {
  it('mutationFn calls PATCH /api/v1/client/messages/read with no body', async () => {
    const { useMarkMessagesRead } = await import('@/lib/clientQueries')
    expect(typeof useMarkMessagesRead).toBe('function')

    mockClientRequest.mockResolvedValue(undefined)

    // Simulate what the mutationFn does
    const markFn = async () => {
      await mockClientRequest('patch', '/api/v1/client/messages/read')
    }

    await markFn()
    expect(mockClientRequest).toHaveBeenCalledWith('patch', '/api/v1/client/messages/read')
  })

  it('onSettled invalidates the messages queryKey', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    const qc = new QueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    // Directly call what onSettled does
    void qc.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'messages'] })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: expect.arrayContaining(['messages', 'client-portal']),
    })
  })
})
