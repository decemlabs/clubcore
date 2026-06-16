import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Command as CommandPrimitive } from 'cmdk';
import {
  Command,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from '@/components/ui/command';
import { useModals, type ModalKey } from '@/components/modals/modals-context';
import {
  Search,
  QrCode,
  UserPlus,
  CreditCard,
  Calendar,
  SlidersHorizontal,
} from '@/components/icons';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { NAV_SECTIONS } from './nav-items';
import {
  searchIndex,
  SEARCH_GROUP_LABEL,
  searchTotals,
  type SearchKind,
  type SearchResult,
} from '@/features/search';
import { ROUTES } from '@/app/routes';
import { formatInt } from '@/lib/format';
import { cn } from '@/lib/cn';

type Filter = 'all' | 'clients' | 'trainers' | 'plans' | 'actions';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Везде' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'trainers', label: 'Тренеры' },
  { key: 'plans', label: 'Абонементы' },
  { key: 'actions', label: 'Действия' },
];

interface QuickAction {
  key: ModalKey;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { key: 'new-client', label: 'Добавить клиента', icon: UserPlus, shortcut: '⌘N' },
  { key: 'checkin', label: 'Чек-ин по QR', icon: QrCode },
  { key: 'extend', label: 'Продлить абонемент', icon: CreditCard },
  { key: 'book', label: 'Записать на тренировку', icon: Calendar },
];

const SAVED_FILTERS = [
  { label: 'Истекают на этой неделе', sub: 'Клиенты · абонемент истекает ≤ 7 дней', count: 23 },
  { label: 'Неактивные 30+ дней', sub: 'Клиенты · нет визитов более 30 дней', count: 64 },
  { label: 'VIP · годовой абонемент', sub: 'Клиенты · тариф «Год»', count: 128 },
];

const RESULT_TAG: Record<SearchKind, string> = {
  client: 'Клиент',
  trainer: 'Тренер',
  tariff: 'Тариф',
};

const navItems = NAV_SECTIONS.flatMap((section) => section.items);
const byKind = (kind: SearchKind) => searchIndex.filter((r) => r.kind === kind);

/**
 * Подстрочный фильтр вместо дефолтного fuzzy-subsequence от cmdk (тот для «анна»
 * подсвечивал «Финансы»/«Антон»). Совпадение — если запрос входит в значение/ключевые
 * слова как подстрока; так поиск по имени/телефону ведёт себя предсказуемо.
 */
function substringFilter(value: string, search: string, keywords?: string[]): number {
  const needle = search.trim().toLowerCase();
  if (!needle) return 1;
  const haystack = `${value} ${keywords?.join(' ') ?? ''}`.toLowerCase();
  return haystack.includes(needle) ? 1 : 0;
}

function ResultRow({ result, onRun }: { result: SearchResult; onRun: () => void }) {
  return (
    <CommandItem
      value={result.title}
      keywords={[result.sub, result.keywords ?? '']}
      onSelect={onRun}
      className="gap-3 rounded-[10px] px-3 py-[9px]"
    >
      {result.initials ? (
        <span
          className="grid size-[34px] shrink-0 place-items-center rounded-[9px] text-[12px] font-bold text-white"
          style={{ background: result.color }}
        >
          {result.initials}
        </span>
      ) : (
        <span className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-surface-3 text-fg-muted">
          <CreditCard className="size-4" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-semibold text-fg">{result.title}</span>
        <span className="block truncate text-[11.5px] text-fg-subtle">{result.sub}</span>
      </span>
      <span className="rounded-full bg-surface-3 px-[7px] py-px text-[10px] font-bold uppercase tracking-[0.3px] text-fg-muted">
        {RESULT_TAG[result.kind]}
      </span>
    </CommandItem>
  );
}

/** Иконочная строка (навигация / быстрые действия). */
function CommandRow({
  icon: Icon,
  label,
  shortcut,
  tone = 'neutral',
  onRun,
}: {
  icon: LucideIcon;
  label: string;
  shortcut?: string;
  tone?: 'neutral' | 'primary';
  onRun: () => void;
}) {
  return (
    <CommandItem value={label} onSelect={onRun} className="gap-3 rounded-[10px] px-3 py-[9px]">
      <span
        className={cn(
          'grid size-[34px] shrink-0 place-items-center rounded-[9px]',
          tone === 'primary'
            ? 'bg-primary-soft text-primary-deep dark:text-primary'
            : 'bg-surface-3 text-fg-muted',
        )}
      >
        <Icon className="size-[17px]" strokeWidth={2} />
      </span>
      <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold text-fg">{label}</span>
      {shortcut ? (
        <kbd className="rounded-md border border-border px-1.5 py-0.5 font-mono text-[11px] text-fg-subtle">
          {shortcut}
        </kbd>
      ) : null}
    </CommandItem>
  );
}

/**
 * Глобальная ⌘K-палитра (design/Search.html). Рендерится внутри AppLayout →
 * useNavigate работает. Группы: навигация (NAV_SECTIONS), быстрые действия (useModals),
 * мок-результаты (клиенты/тренеры/тарифы из features/search). Чипы сужают категорию;
 * cmdk фильтрует по тексту внутри показанных групп.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const { open: openModal } = useModals();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  // Сброс при закрытии — следующее открытие начинается с чистого состояния.
  useEffect(() => {
    if (!open) {
      setQuery('');
      setFilter('all');
    }
  }, [open]);

  const run = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  const hasQuery = query.trim().length > 0;
  const showNav = filter === 'all' || filter === 'actions';
  const showActions = filter === 'all' || filter === 'actions';
  const showClients = filter === 'clients' || (filter === 'all' && hasQuery);
  const showTrainers = filter === 'trainers' || (filter === 'all' && hasQuery);
  const showTariffs = filter === 'plans' || (filter === 'all' && hasQuery);
  const showSaved = !hasQuery && (filter === 'all' || filter === 'clients');

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[6px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            'fixed left-1/2 top-[12vh] z-50 w-[min(620px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-[18px] border border-border bg-surface shadow-2xl outline-none',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'max-sm:left-0 max-sm:top-0 max-sm:h-[100dvh] max-sm:w-full max-sm:translate-x-0 max-sm:rounded-none',
          )}
        >
          <DialogPrimitive.Title className="sr-only">Глобальный поиск</DialogPrimitive.Title>
          <Command
            shouldFilter
            loop
            filter={substringFilter}
            className="flex h-full max-h-[min(64vh,520px)] flex-col bg-transparent max-sm:max-h-none"
          >
            {/* Поисковая строка */}
            <div className="flex items-center gap-3 border-b border-border px-[18px] py-4">
              <Search className="size-5 shrink-0 text-fg-subtle" strokeWidth={2} />
              <CommandPrimitive.Input
                autoFocus
                value={query}
                onValueChange={setQuery}
                placeholder="Клиенты, тренеры, абонементы, действия…"
                className="flex-1 bg-transparent text-[16px] text-fg outline-none placeholder:text-fg-subtle"
              />
              <kbd className="hidden rounded-md border border-border px-1.5 py-0.5 font-mono text-[11px] text-fg-subtle sm:inline-block">
                ESC
              </kbd>
            </div>

            {/* Чипы-фильтры */}
            <div className="flex flex-wrap gap-1.5 px-2.5 pb-1 pt-2.5">
              {FILTERS.map((f) => {
                const on = filter === f.key;
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setFilter(f.key)}
                    className={cn(
                      'rounded-full border px-3 py-[5px] text-[12px] font-semibold transition-colors',
                      on
                        ? 'border-fg bg-fg text-bg dark:border-border-strong dark:bg-surface-3 dark:text-fg'
                        : 'border-border bg-surface text-fg-muted hover:bg-surface-3',
                    )}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>

            <CommandList className="min-h-0 max-h-none flex-1 overflow-y-auto px-2 pb-2">
              <CommandEmpty className="px-6 py-12 text-center">
                <span className="block text-[15px] font-bold text-fg">Ничего не найдено</span>
                <span className="mt-1.5 block text-[12.5px] text-fg-subtle">
                  По запросу «{query}» ничего нет. Проверьте написание или поищите по телефону.
                </span>
              </CommandEmpty>

              {showNav ? (
                <CommandGroup heading="Навигация">
                  {navItems.map((item) => (
                    <CommandRow
                      key={item.to}
                      icon={item.icon}
                      label={item.label}
                      onRun={() => run(() => navigate(item.to))}
                    />
                  ))}
                </CommandGroup>
              ) : null}

              {showActions ? (
                <CommandGroup heading="Быстрые действия">
                  {QUICK_ACTIONS.map((action) => (
                    <CommandRow
                      key={action.key}
                      icon={action.icon}
                      label={action.label}
                      shortcut={action.shortcut}
                      tone="primary"
                      onRun={() => run(() => openModal(action.key))}
                    />
                  ))}
                </CommandGroup>
              ) : null}

              {showClients ? (
                <CommandGroup heading={SEARCH_GROUP_LABEL.client}>
                  {byKind('client').map((r) => (
                    <ResultRow key={r.id} result={r} onRun={() => run(() => navigate(r.to))} />
                  ))}
                </CommandGroup>
              ) : null}

              {showTrainers ? (
                <CommandGroup heading={SEARCH_GROUP_LABEL.trainer}>
                  {byKind('trainer').map((r) => (
                    <ResultRow key={r.id} result={r} onRun={() => run(() => navigate(r.to))} />
                  ))}
                </CommandGroup>
              ) : null}

              {showTariffs ? (
                <CommandGroup heading={SEARCH_GROUP_LABEL.tariff}>
                  {byKind('tariff').map((r) => (
                    <ResultRow key={r.id} result={r} onRun={() => run(() => navigate(r.to))} />
                  ))}
                </CommandGroup>
              ) : null}

              {showSaved ? (
                <CommandGroup heading="Сохранённые фильтры">
                  {SAVED_FILTERS.map((s) => (
                    <CommandItem
                      key={s.label}
                      value={s.label}
                      onSelect={() =>
                        run(() => {
                          navigate(ROUTES.clients);
                          toast(`Фильтр «${s.label}» применён`);
                        })
                      }
                      className="gap-3 rounded-[10px] px-3 py-[9px]"
                    >
                      <span className="grid size-[30px] shrink-0 place-items-center rounded-lg bg-indigo-500/15 text-indigo-600 dark:text-indigo-300">
                        <SlidersHorizontal className="size-[15px]" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-semibold text-fg">
                          {s.label}
                        </span>
                        <span className="block truncate text-[11px] text-fg-subtle">{s.sub}</span>
                      </span>
                      <span className="rounded-full bg-surface-3 px-2 py-px text-[11px] font-bold text-fg-muted">
                        {s.count}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ) : null}
            </CommandList>

            {/* Футер с хоткеями */}
            <div className="flex items-center gap-4 border-t border-border bg-surface-2 px-4 py-2.5 text-[11.5px] text-fg-subtle">
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border px-1 font-mono">↑↓</kbd>навигация
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border px-1 font-mono">↵</kbd>открыть
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border px-1 font-mono">esc</kbd>закрыть
              </span>
              <span className="ml-auto max-sm:hidden">
                Поиск по {formatInt(searchTotals.clients)} клиентам · {searchTotals.trainers}{' '}
                тренерам
              </span>
            </div>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
