/**
 * Staff messaging domain TanStack Query hooks (Phase 116 MSG-01/02).
 *
 * Replaces the mock swap-seam (mockResponse + messagesData) with real
 * staff endpoint calls. Wire shapes are pinned to the 116-01-SUMMARY
 * (D-V32-DRIFT-LESSON: parse with Zod to catch field-name drift early).
 *
 * Hooks:
 *   useThreads()          — GET /api/v1/messages/threads (inbox, polls every 15s)
 *   useThread(id)         — GET /api/v1/messages/threads/{id} (thread history)
 *   useSendReply(id)      — POST /api/v1/messages/threads/{id}/reply (owner-only)
 *   useMarkThreadRead()   — POST /api/v1/messages/threads/{id}/read (fire-and-forget)
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { toast } from 'sonner'
import { staffRequest } from '@/api/client'

// ---------------------------------------------------------------------------
// Zod schemas — match the EXACT camelCase wire shapes from 116-01-SUMMARY
// ---------------------------------------------------------------------------

const StaffThreadItemSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  clientName: z.string(),
  clientInitials: z.string(),
  lastMessageAt: z.string().nullable(),
  lastMessageBody: z.string().nullable(),
  lastMessageRole: z.enum(['client', 'staff']).nullable(),
  staffUnreadCount: z.number(),
})

const StaffInboxSchema = z.object({
  data: z.object({
    items: z.array(StaffThreadItemSchema),
    total: z.number(),
  }),
})

const StaffMessageItemSchema = z.object({
  id: z.string(),
  role: z.string(), // open string for forward compat ('client' | 'staff')
  body: z.string(),
  sentAt: z.string(),
})

const StaffThreadSchema = z.object({
  data: z.object({
    threadId: z.string(),
    messages: z.array(StaffMessageItemSchema),
  }),
})

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const messagesKeys = {
  all: ['messages'] as const,
  threads: () => ['messages', 'threads'] as const,
  thread: (id: string) => ['messages', 'threads', id] as const,
} as const

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Staff inbox: GET /api/v1/messages/threads
 *
 * Polls every 15 s (near-realtime inbox — 116-CONTEXT discretionary interval).
 * refetchOnWindowFocus: true overrides the global `false` for the inbox only.
 * staleTime: 0 ensures the latest thread order is always visible.
 */
export function useThreads() {
  return useQuery({
    queryKey: messagesKeys.threads(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/messages/threads')
      return StaffInboxSchema.parse(raw).data
    },
    staleTime: 0,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  })
}

/**
 * Thread history: GET /api/v1/messages/threads/{id}
 *
 * Disabled when threadId is null (no thread selected).
 * IN-01: polls every 15s (matching the inbox) so an open thread shows newly-arrived
 * client messages near-realtime instead of lagging up to staleTime (30s).
 */
export function useThread(threadId: string | null) {
  return useQuery({
    queryKey: messagesKeys.thread(threadId ?? ''),
    queryFn: async () => {
      const raw = await staffRequest(
        'get',
        '/api/v1/messages/threads/{thread_id}',
        { params: { thread_id: threadId ?? '' } },
      )
      return StaffThreadSchema.parse(raw).data
    },
    enabled: !!threadId,
    staleTime: 30_000,
    refetchInterval: 15_000,
  })
}

/**
 * Send staff reply: POST /api/v1/messages/threads/{id}/reply
 *
 * Owner-only — reception gets 403 (backend enforces).
 * onSettled invalidates thread history + inbox (unread count refresh).
 * onError: Russian toast per Copywriting Contract.
 */
export function useSendReply(threadId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: string) => {
      return staffRequest(
        'post',
        '/api/v1/messages/threads/{thread_id}/reply',
        { params: { thread_id: threadId }, body: { body } },
      )
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: messagesKeys.thread(threadId) })
      void queryClient.invalidateQueries({ queryKey: messagesKeys.threads() })
    },
    onError: () => {
      toast.error('Не удалось отправить сообщение. Попробуйте ещё раз.')
    },
  })
}

/**
 * Mark thread read: POST /api/v1/messages/threads/{id}/read → 204 No Content
 *
 * Fire-and-forget — no toast on error (silent watermark update).
 * Both roles allowed (backend: VIEW, MESSAGES).
 * WR-01: invalidate the inbox query on settle so the unread badge clears
 * immediately instead of lagging up to the 15s poll.
 */
export function useMarkThreadRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (threadId: string) =>
      staffRequest(
        'post',
        '/api/v1/messages/threads/{thread_id}/read',
        { params: { thread_id: threadId }, body: {} },
      ),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: messagesKeys.threads() })
    },
  })
}
