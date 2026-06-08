# Phase 94: PWA ChatScreen Wiring — Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 7 target files (1 modify, 6 create/extend)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Action | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| `src/screens/ChatScreen.jsx` | MODIFY (full replace) | screen | request-response + event-driven | `src/screens/sheets/NotificationsSheet.jsx` | exact (same scoped-CSS, `const CSS`, React Query, gestures, PTR) |
| `src/lib/clientQueries.ts` | MODIFY (extend) | data layer | CRUD + event-driven | self — existing hooks pattern | exact |
| `src/lib/useClientMessagingWS.ts` | CREATE | hook | event-driven / pub-sub | `src/lib/authBus.ts` + `src/context/AuthContext.jsx` (effect cleanup) | partial (no WS analog — first WS hook; closest is subscribeSessionExpired cleanup pattern) |
| `src/data/index.js` | MODIFY (3 new re-exports) | barrel / swap seam | — | self | exact |
| `apps/client-pwa/eslint.config.js` | MODIFY (de-list ChatScreen) | config | — | self (lines 27-29, 68-71, 91-93) | exact |
| `src/App.jsx` | MODIFY (wire unreadChat + WS provider mount) | shell | event-driven | self (lines 143-154, 454) | exact |
| `src/context/UIContext.jsx` | MODIFY (add unreadCount state) | context | event-driven | self (lines 41, 70-81) | exact |

---

## Pattern Assignments

---

### `src/screens/ChatScreen.jsx` (screen, request-response + event-driven)

**Action:** Full replacement of the `ComingSoon` placeholder with the ported reference screen.

**Analog:** `src/screens/sheets/NotificationsSheet.jsx` (Phase 87)

**Graduation recipe** — the three changes that turn a placeholder into a wired screen:

1. Remove ChatScreen from D-71-09 ESLint zone (see `eslint.config.js` section below).
2. Import data hooks via `@/data` instead of mock constants.
3. Wire `{ data, isLoading, isError, refetch }` to loading/error/content branches.

**Imports pattern** (mirrors NotificationsSheet lines 27-32):
```jsx
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  useClientMessages,
  useSendMessage,
  useUploadAttachment,
  useMarkMessagesRead,
} from '@/data'
```

**Scoped CSS injection pattern** (NotificationsSheet lines 39-150, ChatScreen equivalent):

NotificationsSheet wraps ALL its CSS rules under `.notif-screen`:
```jsx
const CSS = `
.notif-screen { position: absolute; inset: 0; z-index: 220; background: var(--bg);
  display: flex; flex-direction: column; font-family: var(--font); ... }
.notif-screen .t-num { ... }
.notif-screen .seg { ... }
/* etc — every selector prefixed with .notif-screen */
`
// ...
return (
  <div className="notif-screen">
    <style>{CSS}</style>
    {/* content */}
  </div>
)
```

ChatScreen follows this EXACTLY but:
- Root class is `.chat-root` (not `.notif-screen`).
- The reference's `:root { --accent: ...; }` block becomes `.chat-root { --accent: ...; }`.
- The reference's `body.dark { ... }` block becomes `.chat-root.dark { ... }`.
- The reference's `html, body { ... }` global rules are STRIPPED; font/bg set on `.chat-root` instead.
- Prototype chrome CSS blocks (`.device`, `.device-inner`, `.island`, `.status-bar`, `.home-indicator`, `.stage`, `.tweaks`, `.tabbar`, `.tabbar-item`, `.tab-badge`) are STRIPPED entirely.
- All remaining selectors (`.screen`, `.view`, `.bubble`, `.composer`, `.conv-card`, `.swipe`, `.thread-bar`, etc.) remain verbatim — they are already non-global.

**Dark mode sync pattern** (replaces reference `applyTweaks` / `body.classList.toggle('dark', ...)` at lines 746-749):
```jsx
// Read theme from existing PWA — document.documentElement carries the 'dark' class
// set by the PWA ThemeProvider (next-themes / TweaksContext).
const [isDark, setIsDark] = useState(
  () => document.documentElement.classList.contains('dark')
)
useEffect(() => {
  const obs = new MutationObserver(() => {
    setIsDark(document.documentElement.classList.contains('dark'))
  })
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  return () => obs.disconnect()
}, [])
// Apply to root:
<div className={'chat-root' + (isDark ? ' dark' : '')}>
  <style>{CSS}</style>
  ...
</div>
```

**Loading skeleton pattern** (NotificationsSheet lines 555-559):
```jsx
{isLoading ? (
  <div style={{ paddingTop: 8 }} aria-label="Загрузка сообщений…">
    <div className="sk-card" />
    <div className="sk-card" />
    <div className="sk-card" />
  </div>
) : isError ? (
  // error branch
) : (
  // content
)}
```

**Error + retry pattern** (NotificationsSheet lines 562-569):
```jsx
) : isError ? (
  <div className="card empty fade-up" style={{ padding: 0, marginTop: 8 }}>
    <div className="empty" style={{ margin: 0 }}>
      <div className="empty-ic" style={{ background: 'var(--danger-soft)' }}>
        <Ico name="alert" size={26} color="var(--danger)" sw={1.8} />
      </div>
      <div className="t-h3" style={{ fontSize: 16 }}>Не удалось загрузить</div>
      <div className="t-small" style={{ maxWidth: 230 }}>
        Потяните вниз, чтобы повторить.
      </div>
    </div>
  </div>
```

**Pull-to-refresh real refetch pattern** (NotificationsSheet lines 400-432 — exact copy for list view PTR):
```jsx
// endPull called onPointerUp/Cancel/Leave on the scroller
if (pull >= 44) {
  p.loading = true
  listEl.style.transform = 'translateY(44px)'
  ptr.classList.add('spin')
  ptr.style.opacity = 1
  const svg = ptr.querySelector('svg')
  if (svg) svg.style.transform = ''
  query.refetch().finally(() => {
    settle()
    toast('Обновлено')
  })
} else {
  listEl.style.transform = 'translateY(0)'
  ptr.style.opacity = 0
}
```

**Mock data REMOVAL** — reference's `INITIAL_CONVS` (lines 619-665) is replaced with a single hardcoded conversation object hydrated from backend data:
```jsx
// Hardcoded metadata for the single wired conversation (no API for conv list)
const ADMIN_CONV = {
  id: 'admin',
  name: 'Администрация',
  sub: 'Мой зал',
  initials: 'МЗ',
  color: '#1c1917',
  bg: '#e7e5e4',
  isOfficial: true,
}
```

**Prototype chrome REMOVAL** — delete these reference blocks entirely:
- `TWEAK_DEFAULTS`, `ACCENTS`, `applyAccent`, `applyTweaks`, `setTweak` (lines 667-775)
- `window.parent.postMessage` / `__activate_edit_mode` message listener (lines 778-787)
- `document.addEventListener('click', onClick)` data-go/data-toast handler (lines 789-799)
- `[tweaks, setTweaksShow, tweaksShow]` state vars (lines 700-701)
- `botTimers`, `botReplies`, `botTimers.current.push(setTimeout(...))` in `sendMessage` (lines 719, 898-902)
- `PHOTO_PRESETS` gradient presets — keep constant in source, not rendered.

**Send message mutation wiring** — replaces `pushMsg(t, 'me')` + bot reply in `sendMessage`:
```jsx
const sendTextMessage = useCallback(async (text) => {
  const t = (text ?? inputRef.current).trim()
  if (!t) return
  // Optimistic add
  const optimisticId = 'opt-' + Date.now()
  // ... add to local state as role:'client', sentAt: new Date().toISOString()
  setInput('')
  try {
    await sendMessageMutation.mutateAsync({ body: t })
    // WS new_message frame triggers query invalidation → real message replaces optimistic
  } catch {
    // roll back optimistic message, show toast
  }
}, [sendMessageMutation])
```

**Photo attachment two-step wiring** — replaces `pushMsg(text, 'me', 'photo')`:
```jsx
// Step 1: upload
const uploadResult = await uploadAttachment.mutateAsync({ file })
// → returns { attachmentId, previewUrl }
// Step 2: send message with attachmentId
await sendMessageMutation.mutateAsync({ attachmentId: uploadResult.attachmentId })
```

**Mark-read on thread open** (replaces `conv.unread ? setConvs(...)` zeroing in `openThread` at line 839):
```jsx
const openThread = useCallback((id) => {
  // ... existing reference logic ...
  // Wire: mark all staff messages read
  markReadMutation.mutate()
}, [markReadMutation])
```

**WS integration** — replaces `botTimers` typing simulation with real hook:
```jsx
const { typingFromStaff } = useClientMessagingWS({
  onNewMessage: () => {
    void qc.invalidateQueries({ queryKey: clientPortalKeys.messages() })
  },
  onReadReceipt: (readAt) => {
    // Mark all my sent messages with sentAt <= readAt as read locally
    setConvs(prev => markClientMessagesRead(prev, readAt))
  },
  onTyping: () => {
    setTypingFn(true)
    clearTimeout(typingDismissRef.current)
    typingDismissRef.current = setTimeout(() => setTypingFn(false), 5000)
  },
})
```

**Data mapping** — reference message shape → backend response:
```jsx
// Transform MessageItem from GET /client/messages into reference message shape
function adaptMessage(m) {
  return {
    id: m.id,
    from: m.role === 'client' ? 'me' : 'them',
    body: m.body,
    time: new Intl.DateTimeFormat('ru-RU', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow',
    }).format(new Date(m.sentAt)),
    read: m.readAt != null,
    kind: m.attachment ? 'photo' : 'text',
    attachment: m.attachment ?? null,
    sentAt: m.sentAt,  // kept for read-receipt watermark comparison
  }
}
```

**Photo bubble real image** — replaces `PHOTO_PRESETS` gradient with real `<img>`:
```jsx
// Instead of: <PhotoBubble preset={m.photo} />
// Use:
<div style={{ width: 220, height: 140, borderRadius: 14, overflow: 'hidden', padding: 4 }}>
  <img
    src={m.attachment.url}  // e.g. /api/v1/client/messages/attachments/{id}
    style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 10 }}
    alt="Фото"
    onClick={() => setPhotoOverlay(m.attachment.url)}
  />
</div>
```

**Full-screen photo overlay** (not in reference CSS — implement per project convention):
```jsx
{photoOverlay && (
  <div
    style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.9)',
      zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}
    onClick={() => setPhotoOverlay(null)}
  >
    <img
      src={photoOverlay}
      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
      alt="Просмотр фото"
    />
  </div>
)}
```

---

### `src/lib/clientQueries.ts` (data layer, CRUD)

**Action:** Add messaging keys + hooks.

**Analog:** Existing `useClientNotifications` / `useMarkAllNotificationsRead` hooks (lines 872-914) — exact mirror pattern.

**Key factory additions** (after line 45, mirror `notifications` key pattern at line 44):
```typescript
messages: (cursor?: string) => [...clientPortalKeys.all, 'messages', cursor ?? ''] as const,
```

**Interface additions** (mirror `NotificationItem` at line 858, `NotificationsListData` at line 866):
```typescript
export interface MessageAttachmentItem {
  id: string
  mimeType: string
  sizeBytes: number
  url: string
}

export interface MessageItem {
  id: string
  role: 'client' | 'staff'
  body: string
  sentAt: string
  readAt: string | null
  threadId: string
  attachment: MessageAttachmentItem | null
}

interface MessageListData {
  items: MessageItem[]
  total: number
  page: number
  pageSize: number
  unreadCount: number
}

interface AttachmentUploadResult {
  attachmentId: string
  previewUrl: string
}
```

**Read hook** (mirror `useClientNotifications` at lines 871-883):
```typescript
export function useClientMessages(after?: string) {
  return useQuery({
    queryKey: clientPortalKeys.messages(after),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/messages', {
        ...(after ? { query: { after } } : {}),
      })
      return (res as { data: MessageListData }).data
    },
    staleTime: 30_000,
  })
}
```

**Mark-read mutation** (mirror `useMarkAllNotificationsRead` at lines 904-914):
```typescript
export function useMarkMessagesRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await clientRequest('patch', '/api/v1/client/messages/read')
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'messages'] })
    },
  })
}
```

**Send mutation** (mirror `useCreateBooking` at lines 478-504 for the `Idempotency-Key` pattern):
```typescript
export function useSendMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      body,
      attachmentId,
      idempotencyKey,
    }: {
      body?: string
      attachmentId?: string
      idempotencyKey: string
    }) => {
      const res = await clientRequest('post', '/api/v1/client/messages', {
        body: { ...(body ? { body } : {}), ...(attachmentId ? { attachmentId } : {}) },
        headers: { 'Idempotency-Key': idempotencyKey },
      })
      return (res as { data: MessageItem }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'messages'] })
    },
  })
}
```

**Upload mutation** — `clientRequest` supports `FormData` body (clientFetcher.ts lines 179-181 shows FormData is passed through without JSON-stringify):
```typescript
export function useUploadAttachment() {
  return useMutation({
    mutationFn: async ({ file }: { file: File }) => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await clientRequest('post', '/api/v1/client/messages/attachments', {
        body: fd,
        // No Content-Type header — browser sets multipart/form-data + boundary automatically
      })
      return (res as { data: AttachmentUploadResult }).data
    },
  })
}
```

---

### `src/lib/useClientMessagingWS.ts` (hook, event-driven — NO EXISTING ANALOG)

**Action:** CREATE from scratch. This is the first WebSocket hook in the entire codebase.

**No WS analog exists.** `grep -r "WebSocket\|new WebSocket\|ws://" apps/client-pwa/src/` returns zero results.

**Closest structural analog:** `src/lib/authBus.ts` (subscribe/unsubscribe effect-cleanup pattern) + `src/context/AuthContext.jsx` (useEffect with cleanup return, lines 68-76).

**Effect-cleanup pattern to copy** (AuthContext lines 68-76):
```jsx
useEffect(() => {
  const unsub = subscribeSessionExpired(() => {
    anonSetAtRef.current = Date.now()
    setOverride('anon')
    void qc.invalidateQueries({ queryKey: clientPortalKeys.all })
  })
  return unsub  // cleanup = unsubscribe
}, [qc])
```

**WS hook structure** (build from scratch, guided by WS spec in router.py lines 338-373):
```typescript
// apps/client-pwa/src/lib/useClientMessagingWS.ts
import { useEffect, useRef } from 'react'

interface UseClientMessagingWSOptions {
  enabled?: boolean
  onNewMessage: (messageId: string) => void
  onReadReceipt: (readAt: string) => void
  onTyping: () => void
}

const BASE_DELAY = 1_000
const MAX_DELAY = 30_000

export function useClientMessagingWS({
  enabled = true,
  onNewMessage,
  onReadReceipt,
  onTyping,
}: UseClientMessagingWSOptions): void {
  const reconnectDelay = useRef(BASE_DELAY)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) return

    let destroyed = false

    function connect() {
      if (destroyed) return
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${location.host}/api/v1/client/ws/messages`)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectDelay.current = BASE_DELAY
      }

      ws.onmessage = (event) => {
        let frame: { type: string; messageId?: string; readAt?: string }
        try { frame = JSON.parse(event.data as string) } catch { return }
        if (frame.type === 'new_message' && frame.messageId) {
          onNewMessage(frame.messageId)
        } else if (frame.type === 'read_receipt' && frame.readAt) {
          onReadReceipt(frame.readAt)
        } else if (frame.type === 'typing') {
          onTyping()
        }
        // 'ping' frames: no-op (server heartbeat; client may respond with any text)
      }

      ws.onclose = () => {
        wsRef.current = null
        if (!destroyed) scheduleReconnect()
      }
      ws.onerror = () => ws.close()
    }

    function scheduleReconnect() {
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_DELAY)
        connect()
      }, reconnectDelay.current)
    }

    connect()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer.current ?? undefined)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [enabled, onNewMessage, onReadReceipt, onTyping])
}
```

**WS frame shapes from backend schemas.py** (lines 168-231):
- `new_message`: `{ "type": "new_message", "messageId": "<uuid>" }` — PWA reacts by invalidating messages query + refetching via REST (`?after=` cursor on reconnect).
- `read_receipt`: `{ "type": "read_receipt", "readAt": "<ISO datetime>" }` — `readAt` is a send-time WATERMARK (max sentAt of just-read client rows), NOT the read clock. Mark all own messages with `sentAt <= readAt` as ✓✓.
- `typing`: `{ "type": "typing", "actor": "staff" }` — ephemeral, 5s auto-dismiss.
- `ping`: `{ "type": "ping" }` — server heartbeat, no PWA action.

---

### `src/data/index.js` (barrel, swap seam)

**Action:** Add 4 new re-exports for messaging hooks.

**Pattern** (lines 21-67 — copy the block comment + export group style):
```javascript
// Phase-94 CHAT-01: messaging hooks
export {
  useClientMessages,
  useSendMessage,
  useUploadAttachment,
  useMarkMessagesRead,
} from '../lib/clientQueries'
```

Add after the Phase-88 TRNR-04 block at line 67. No new mock constants needed — messaging has no retained mock data.

---

### `apps/client-pwa/eslint.config.js` (config — de-list ChatScreen from D-71-09 zone)

**Action:** Remove ChatScreen from 3 exact spots. After removal, `grep ChatScreen eslint.config.js` returns 0.

**Spot 1 — ignore-negation** (line 28, current):
```javascript
'!src/screens/ChatScreen.jsx',
```
Delete this line. `ReferralSheet` stays. Resulting block (lines 26-29):
```javascript
'src/**/*.jsx',
'src/**/*.js',
'!src/screens/sheets/ReferralSheet.jsx',
```

**Spot 2 — `files:` target block** (lines 68-71, current):
```javascript
files: [
  'src/screens/ChatScreen.jsx',
  'src/screens/sheets/ReferralSheet.jsx',
],
```
Becomes (remove the ChatScreen line):
```javascript
files: [
  'src/screens/sheets/ReferralSheet.jsx',
],
```

**Spot 3 — `no-restricted-paths` zone `target`** (lines 91-94, current):
```javascript
target: [
  './src/screens/ChatScreen.jsx',
  './src/screens/sheets/ReferralSheet.jsx',
],
```
Becomes:
```javascript
target: [
  './src/screens/sheets/ReferralSheet.jsx',
],
```

Update the comment block (lines 62-66) to note ChatScreen graduated in Phase 94 — mirrors the Phase 86/87/88 graduation notes already in the file.

---

### `src/App.jsx` (shell — wire unreadChat + WS provider)

**Action:** Two modifications.

**Modification 1 — wire unreadChat badge** (line 454, current):
```jsx
<TabBar
  active={tab}
  onChange={handleTab}
  unreadChat={0}        // CURRENT — static zero
/>
```
Becomes:
```jsx
<TabBar
  active={tab}
  onChange={handleTab}
  unreadChat={ui.unreadChat > 99 ? '99+' : ui.unreadChat || 0}
/>
```
`ui.unreadChat` is added to UIContext (see below). The `99+` cap matches the UI-SPEC badge cap.

**Modification 2 — WS provider mount point** (line 143-154, ChatRoute, current):
```jsx
function ChatRoute() {
  const { t } = useTweaksCtx();
  const ui = useUI();
  return (
    <ChatScreen
      tweaks={t}
      initialConv={ui.pendingChat}
      onClearInitial={() => ui.setPendingChat(null)}
      onThreadOpen={ui.setChatThreadOpen}
    />
  );
}
```

The app-level WS singleton is mounted at the App root level (not inside ChatRoute), so the unread badge updates from any screen. Add a `<MessagingWSProvider>` component that wraps the body of `App()`, or add the hook call directly in the top-level `App()` function:
```jsx
// Near top of App() body, after const declarations:
useClientMessagingWS({
  enabled: status === 'authed',
  onNewMessage: () => {
    // Trigger messages refetch; unreadCount will update from the REST response
    void qc.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'messages'] })
  },
  onReadReceipt: (readAt) => {
    // Delegate to ChatScreen via a ref/callback if thread is open; else ignore
    window.__chatReadReceipt?.(readAt)
  },
  onTyping: () => {
    window.__chatTyping?.()
  },
})
```

`useQueryClient` is already available at the App level via `@tanstack/react-query`. The `status` is already destructured from `useAuth()` at line 204.

---

### `src/context/UIContext.jsx` (context — add unreadChat state)

**Action:** Add `unreadChat` / `setUnreadChat` state to the existing UIContext.

**Pattern** (copy existing state declarations at lines 10-41):
```jsx
const [unreadChat, setUnreadChat] = useState(0);
```

Add to the `value` useMemo (lines 71-81 area):
```jsx
unreadChat, setUnreadChat,
```

The `ChatScreen` calls `ui.setUnreadChat(data.unreadCount)` when the messages query resolves, keeping the TabBar badge live.

---

## Shared Patterns

### CSS Scoping (applies to ChatScreen only — primary concern)

**Source:** `src/screens/sheets/NotificationsSheet.jsx` lines 39-150

The pattern is: every selector in `const CSS` is prefixed with the screen's root class name. The reference ChatScreen uses un-prefixed global selectors (`:root`, `body.dark`, `html, body`). The porting rule:

| Reference selector | Ported selector |
|---|---|
| `:root { --accent: ...; }` | `.chat-root { --accent: ...; }` |
| `body.dark { --accent: ...; }` | `.chat-root.dark { --accent: ...; }` |
| `html, body { font-family: ...; }` | `.chat-root { font-family: var(--font); }` (already set by `.chat-root`) |
| `.bubble { ... }` | `.chat-root .bubble { ... }` OR keep as-is if `.chat-root` wraps all content |
| `.screen { ... }` | `.chat-root .screen { ... }` |

The NotificationsSheet approach prefixes every rule: `.notif-screen .seg { ... }`. Mirror exactly.

Selectors to STRIP entirely (no scoped equivalent needed):
- `.stage`, `.device`, `.device-inner`, `.island`, `.status-bar`, `.home-indicator`
- `.tweaks`, `.tweak-*`
- `.tabbar`, `.tabbar-item`, `.tab-badge` (existing PWA TabBar owns these)

### Auth / CSRF

**Source:** `src/lib/clientFetcher.ts`

All `clientRequest` calls automatically:
- Send `credentials: 'include'` (httpOnly `cc_client_access` cookie).
- Add `X-CSRF-Token: <clubcore_client_csrf>` on mutations (POST, PATCH, DELETE).
- Single-flight refresh on 401 (not applicable to WS — cookie is sent on upgrade).

No caller action needed. The `useUploadAttachment` FormData body is handled correctly by clientFetcher lines 179-181 (FormData bypasses JSON.stringify, no Content-Type header set — browser sets multipart/form-data boundary automatically).

### React Query Conventions

**Source:** `src/lib/clientQueries.ts` lines 137-147 (`useClientHome`) — representative query hook.

```typescript
return useQuery({
  queryKey: clientPortalKeys.<key>(),
  queryFn: async () => {
    const res = await clientRequest('get', '/api/v1/client/<path>')
    return (res as { data: T }).data
  },
  staleTime: 30_000,
})
```

Key conventions:
- `staleTime: 30_000` on all read queries.
- `refetchOnWindowFocus: false` is set globally on `queryClient.ts` (not per-hook).
- Mutations use `onSettled` for invalidation (never `onSuccess` alone — covers error paths).
- Envelope unwrap: `(res as { data: T }).data` — the backend wraps all responses in `{ data: ... }`.

### Error Handling

**Source:** `src/screens/sheets/NotificationsSheet.jsx` lines 496-497

```jsx
const isLoading = query.isLoading
const isError = query.isError && !query.isFetching
```

Use `isError && !query.isFetching` for the error branch so that a refetch in progress doesn't re-show the error state while data is being retried.

### Toast

**Source:** `src/screens/sheets/NotificationsSheet.jsx` lines 247-252 and lines 139-149 (CSS)

```jsx
const toast = useCallback((msg) => {
  setToastMsg(msg)
  setToastShow(true)
  clearTimeout(toastTimer.current)
  toastTimer.current = setTimeout(() => setToastShow(false), 1700)
}, [])
```

CSS:
```css
.notif-screen .toast { position: absolute; left: 50%; bottom: 40px; transform: translate(-50%, 16px);
  z-index: 90; background: var(--text); color: var(--bg); font-size: 13.5px; font-weight: 600;
  padding: 11px 18px; border-radius: 999px; box-shadow: 0 12px 30px rgba(0,0,0,0.28);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1); white-space: nowrap; }
.notif-screen .toast.show { opacity: 1; transform: translate(-50%, 0); }
```

Chat version: `bottom: 96px` (reference value — above the TabBar), otherwise identical.

### Pointer Event Gesture Cleanup

**Source:** `src/screens/sheets/NotificationsSheet.jsx` lines 292-344

The swipe/long-press gesture pattern registers document-level pointer events in `useEffect` and cleans them up in the return function:
```jsx
useEffect(() => {
  const onMove = (e) => { /* ... */ }
  const onUp = () => { /* ... */ }
  const onCancel = () => { /* ... */ }
  document.addEventListener('pointermove', onMove)
  document.addEventListener('pointerup', onUp)
  document.addEventListener('pointercancel', onCancel)
  return () => {
    document.removeEventListener('pointermove', onMove)
    document.removeEventListener('pointerup', onUp)
    document.removeEventListener('pointercancel', onCancel)
  }
}, [markRead, runCardTap])
```

Mirror verbatim in ChatScreen — reference already uses this pattern (lines 924-972).

---

## Backend Contract Summary

All REST endpoints mount under `/api/v1/client/` (Vite dev proxy: `/api` → `localhost:8000`).

| Operation | Method + Path | Request | Response (camelCase wire) |
|---|---|---|---|
| List messages | `GET /api/v1/client/messages` | `?page=N&after=<uuid>` | `{ data: { items, total, page, pageSize, unreadCount } }` |
| Send message | `POST /api/v1/client/messages` | `{ body?, attachmentId? }` + `Idempotency-Key` header | `{ data: MessageItem }` |
| Mark all read | `PATCH /api/v1/client/messages/read` | — (no body) | 204 No Content |
| Upload photo | `POST /api/v1/client/messages/attachments` | `multipart/form-data` field `file` | `{ data: { attachmentId, previewUrl } }` |
| Serve photo | `GET /api/v1/client/messages/attachments/{attachment_id}` | — (cookie auth) | Binary stream (authenticated proxy) |
| WebSocket | `WS /api/v1/client/ws/messages` | cookie auth on upgrade (no URL token) | server-push frames (below) |

**WS frame shapes** (camelCase via `alias_generator=to_camel` in Pydantic):
```json
{ "type": "new_message", "messageId": "<uuid>" }
{ "type": "read_receipt", "readAt": "<ISO 8601 datetime>" }
{ "type": "typing", "actor": "staff" }
{ "type": "ping" }
```

**`readAt` watermark semantics** (schemas.py lines 196-200, LOCKED): `readAt` in a `read_receipt` frame is `max(sentAt)` of the just-read client messages — a send-time cutoff, NOT the read timestamp. Mark every own message with `sentAt <= readAt` as ✓✓. Do NOT display it as "прочитано в HH:MM".

**`MessageItem` camelCase fields on the wire:**
- `id`, `role` (`'client'`|`'staff'`), `body`, `sentAt`, `readAt` (null = unread), `threadId`
- `attachment`: null OR `{ id, mimeType, sizeBytes, url }` where `url` = `/api/v1/client/messages/attachments/{id}`

**`SendMessageRequest` validity matrix:**
- `body` only → valid
- `attachmentId` only → valid
- both → valid
- neither → 422
- whitespace-only body → 422

---

## No Analog Found

No files in this phase lack an analog — however the WS hook (`useClientMessagingWS.ts`) has no direct WS precedent and must be built from scratch using the effect-cleanup analog from AuthContext.

| File | Gap | Resolution |
|---|---|---|
| `src/lib/useClientMessagingWS.ts` | No WebSocket code exists anywhere in `apps/client-pwa` | Build from scratch; effect-cleanup structure mirrors `AuthContext.jsx` lines 68-76; WS frame handling guided by `schemas.py` |

---

## Metadata

**Analog search scope:** `apps/client-pwa/src/screens/`, `apps/client-pwa/src/lib/`, `apps/client-pwa/src/context/`, `apps/client-pwa/src/components/`, `apps/client-pwa/src/data/`, `apps/backend/app/modules/messaging/`
**Files scanned:** 14
**Pattern extraction date:** 2026-06-08
