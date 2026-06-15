/**
 * Доменные типы экрана «Сообщения» (Messages.html) — командный инбокс:
 * лента диалогов, тред-переписка с composer, панель клиента.
 */

export type ConvSource = 'client' | 'trainer' | 'bot' | 'group';
export type ConvChannel = 'app' | 'telegram' | 'email' | 'bot';
export type TagTone = 'urgent' | 'neutral' | 'staff' | 'complaint' | 'review';

export interface ConvTag {
  label: string;
  tone: TagTone;
}

/** Цветной префикс превью последнего сообщения. */
export interface LastPrefix {
  text: string;
  tone: 'draft' | 'note';
}

export interface Conversation {
  id: string;
  initials: string;
  color: string;
  verified?: boolean;
  source: ConvSource;
  channel?: ConvChannel;
  name: string;
  sub: string;
  last: string;
  lastPrefix?: LastPrefix;
  tags: ConvTag[];
  time: string;
  unread?: number;
  snoozed?: boolean;
  day: 'today' | 'yesterday';
}

/* ---------- Тред ---------- */
export type BubbleType = 'them' | 'me' | 'note' | 'sys';
export interface DaySep {
  kind: 'daysep';
  label: string;
}
export interface Bubble {
  kind: 'msg';
  id: string;
  type: BubbleType;
  text: string;
  meta?: string;
  /** Заголовок внутренней заметки, напр. «Внутренняя заметка · Денис К. → Маша». */
  noteHead?: string;
  /** Подпись фото-вложения (плейсхолдер). */
  photo?: string;
}
export type ThreadItem = DaySep | Bubble;

export interface QuickReply {
  key: string;
  text: string;
}

/* ---------- Панель клиента ---------- */
export interface ClientChip {
  label: string;
  ok?: boolean;
}
export interface PlanRow {
  label: string;
  value: string;
  note?: string;
}
export interface UpcomingRow {
  icon: 'star' | 'money';
  title: string;
  sub: string;
  right: string;
  ok?: boolean;
}
export interface ClientPanelData {
  initials: string;
  gradient: string;
  name: string;
  ptag: string;
  chips: ClientChip[];
  plan: { name: string; sub: string; rows: PlanRow[]; barPct: number };
  upcoming: UpcomingRow[];
}

/* ---------- Вкладки статуса ---------- */
export interface StatusTab {
  id: string;
  label: string;
  count?: number;
  tone?: 'accent' | 'danger';
}

export interface MessagesData {
  unreadDialogs: number;
  mineCount: number;
  statusTabs: StatusTab[];
  conversations: Conversation[];
  thread: ThreadItem[];
  threadMeta: string;
  draft: string;
  quickReplies: QuickReply[];
  client: ClientPanelData;
}

// ---------------------------------------------------------------------------
// Wire types for real staff endpoints (Phase 116)
// These match the EXACT camelCase field names from 116-01-SUMMARY wire shapes.
// ---------------------------------------------------------------------------

export interface StaffThread {
  id: string
  clientId: string
  clientName: string
  clientInitials: string
  lastMessageAt: string | null // ISO or null if no messages yet
  lastMessageBody: string | null
  lastMessageRole: 'client' | 'staff' | null
  staffUnreadCount: number
}

export interface StaffMessage {
  id: string
  role: string // open string per 116-01 (backend ships 'client'|'staff'; forward compat)
  body: string
  sentAt: string // ISO
}

export interface StaffInboxData {
  items: StaffThread[]
  total: number
}

export interface StaffThreadData {
  threadId: string
  messages: StaffMessage[]
}
