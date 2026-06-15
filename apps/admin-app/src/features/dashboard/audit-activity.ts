/**
 * Pure audit-log → ActivityFeed mapper (Phase 115-04 ANL-04).
 *
 * mapAuditToActivityFeed: AuditLogData → ActivityFeedData
 *
 * No React, no fetch — testable pure function.
 * The mapping table mirrors the 115-UI-SPEC "ActivityFeed audit-log mapping" section.
 *
 * Threat T-115-D2: switch default branch ('alert') prevents a crash on any
 * future/unrecognized audit action — the dashboard never breaks on a drifted
 * audit taxonomy.
 *
 * Threat T-115-D3: display name resolution never invents client names —
 * uses actorEmailSnapshot local-part or a generic "Событие" label.
 */
import { formatRelativeRu } from '@/lib/format'
import type { ActivityEvent, ActivityFeedData, ActivityType } from './types'
import type { AuditEvent, AuditLogData } from '@/features/audit/schemas'

// ---------------------------------------------------------------------------
// Title builders
// ---------------------------------------------------------------------------

function titleFor(type: ActivityType, name: string): string {
  switch (type) {
    case 'checkin':
      return `${name} · чек-ин`
    case 'payment':
      return `${name} · оплата`
    case 'training':
      return `${name} · запись подтверждена`
    case 'cancel':
      return `${name} · отмена записи`
    case 'expire':
      return `${name} · абонемент истёк`
    case 'signup':
      return `${name} · новый клиент`
    case 'alert':
      // Handled separately in mapSingleEvent — this branch is unreachable for alert type
      return name
  }
}

// ---------------------------------------------------------------------------
// Display name extraction
// ---------------------------------------------------------------------------

/**
 * Resolves a display name from the audit event.
 * Priority: payload.clientName > payload.name > actor email local-part > generic label.
 * Never invents names — falls back gracefully (T-115-D3).
 */
function resolveName(event: AuditEvent): string {
  const p = event.payload
  if (p && typeof p['clientName'] === 'string' && p['clientName']) {
    return p['clientName']
  }
  if (p && typeof p['name'] === 'string' && p['name']) {
    return p['name']
  }
  if (event.actorEmailSnapshot) {
    // Use the local-part (before @)
    return event.actorEmailSnapshot.split('@')[0] ?? event.actorEmailSnapshot
  }
  return 'Событие'
}

/**
 * Resolves a short subLead string (actor or resource context).
 * Shows the actor email local-part or the resource type as context.
 */
function resolveSubLead(event: AuditEvent): string {
  if (event.actorEmailSnapshot) {
    return event.actorEmailSnapshot.split('@')[0] ?? event.actorEmailSnapshot
  }
  return event.resourceType
}

// ---------------------------------------------------------------------------
// Single event mapper
// ---------------------------------------------------------------------------

function mapSingleEvent(event: AuditEvent): ActivityEvent {
  const action = event.action
  let type: ActivityType

  // Check exact action matches first, then prefix/resource-type matches
  if (action === 'booking.confirmed') {
    type = 'training'
  } else if (action === 'booking.cancelled') {
    type = 'cancel'
  } else if (action === 'membership.expired') {
    type = 'expire'
  } else if (action === 'client.registered') {
    type = 'signup'
  } else if (action.startsWith('visit')) {
    type = 'checkin'
  } else if (action.startsWith('payment')) {
    type = 'payment'
  } else {
    // T-115-D2: unrecognized action → alert, never throws
    type = 'alert'
  }

  const name = resolveName(event)
  const title = type === 'alert' ? action : titleFor(type, name)
  const subLead = resolveSubLead(event)
  // IN-05: formatRelativeRu (date-fns formatDistanceToNowStrict) throws a RangeError
  // on an unparseable createdAt. The mapper is contractually "never throws", so guard
  // defensively and fall back to a safe label rather than crashing the feed.
  let timeLabel: string
  try {
    timeLabel = formatRelativeRu(event.createdAt)
  } catch {
    timeLabel = '—'
  }

  return {
    id: event.id,
    type,
    title,
    subLead,
    timeLabel,
  }
}

// ---------------------------------------------------------------------------
// Count-aware subtitle
// ---------------------------------------------------------------------------

function buildSubtitle(count: number): string {
  const m10 = count % 10
  const m100 = count % 100
  let label: string
  if (count === 0) {
    label = 'нет событий'
  } else if (m10 === 1 && m100 !== 11) {
    label = `${count} событие`
  } else if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) {
    label = `${count} события`
  } else {
    label = `${count} событий`
  }
  return `Последние события · ${label}`
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Maps an audit-log paginated response to the ActivityFeedData shape
 * consumed by the ActivityFeed component.
 *
 * Pure function — no side effects, no React, no fetch.
 *
 * @param audit - Parsed AuditLogData (items + pagination meta)
 * @returns ActivityFeedData ready for <ActivityFeed data={...} />
 */
export function mapAuditToActivityFeed(audit: AuditLogData): ActivityFeedData {
  const events = audit.items.map(mapSingleEvent)
  return {
    events,
    subtitle: buildSubtitle(events.length),
    repliedToday: 0, // no chat-reply concept in this app
  }
}
