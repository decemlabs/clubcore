import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ROUTES } from '@/app/routes';
import { cn } from '@/lib/cn';
import { pluralRu } from '@/lib/format';
import { useRoles } from '@/features/roles/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { PermLevel, Role, RolesData } from '@/features/roles/types';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/feedback/EmptyState';
import { FileText, Plus, Lock, Search, Check } from '@/components/icons';
import { Panel } from '@/components/layout/Panel';
import { AvatarStack, PcHead, RoleIco, Seg } from './components/parts';
import { MODULE_ICON } from './components/helpers';

const onCreateRole = () => toast('Откроется мастер создания роли');

export function RolesPage() {
  const { data, isPending, isError, refetch } = useRoles();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  return <RolesEditor data={data} />;
}

function RolesEditor({ data }: { data: RolesData }) {
  const initial = data.roles.find((r) => r.id === 'manager') ?? data.roles[0]!;
  const [selectedId, setSelectedId] = useState(initial.id);
  const [working, setWorking] = useState<PermLevel[]>(initial.perms);
  const [savedPerms, setSavedPerms] = useState<PermLevel[]>(initial.perms);
  const [lastAction, setLastAction] = useState<'none' | 'saved' | 'reset'>('none');
  const [search, setSearch] = useState('');

  const role = data.roles.find((r) => r.id === selectedId) ?? data.roles[0]!;

  useEffect(() => {
    const r = data.roles.find((x) => x.id === selectedId);
    if (r) {
      setWorking(r.perms);
      setSavedPerms(r.perms);
      setLastAction('none');
    }
  }, [selectedId, data.roles]);

  const dirty = !role.locked && working.join(',') !== savedPerms.join(',');

  const changePerm = (idx: number, lvl: PermLevel) => {
    setWorking((prev) => prev.map((p, i) => (i === idx ? lvl : p)));
    setLastAction('none');
  };
  const save = () => {
    setSavedPerms(working);
    setLastAction('saved');
    toast.success(`Права роли «${role.name}» сохранены`);
  };
  const reset = () => {
    setWorking(savedPerms);
    setLastAction('reset');
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Роли и права доступа"
        subtitle="Настройте, что видят и могут делать сотрудники. Системные роли изменять нельзя — создавайте собственные под задачи зала."
        actions={
          <>
            <Link
              to={ROUTES.audit}
              className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:hidden"
            >
              <FileText className="size-[14px]" />
              Журнал доступа
            </Link>
            <Button
              onClick={onCreateRole}
              className="h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold"
            >
              <Plus className="size-[15px]" strokeWidth={2.4} />
              Создать роль
            </Button>
          </>
        }
      />

      <div className="grid items-start gap-[18px] lg:grid-cols-[320px_minmax(0,1fr)]">
        {/* Role list */}
        <Panel>
          <PcHead title="Роли" count={data.roles.length} />
          <div className="flex flex-col gap-0.5 p-1.5">
            {data.roles.map((r) => (
              <RoleItem
                key={r.id}
                role={r}
                active={r.id === selectedId}
                onClick={() => setSelectedId(r.id)}
              />
            ))}
          </div>
          <div className="px-1.5 pb-1.5">
            <button
              type="button"
              onClick={onCreateRole}
              className="flex w-full items-center justify-center gap-1.5 rounded-[14px] border border-dashed border-border-strong px-3 py-[11px] text-[13px] font-semibold text-fg-muted transition-colors hover:border-fg-subtle hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Plus className="size-3.5" strokeWidth={2.4} />
              Новая роль
            </button>
          </div>
        </Panel>

        {/* Role detail */}
        <RoleDetail
          role={role}
          modules={data.modules}
          working={working}
          dirty={dirty}
          lastAction={lastAction}
          search={search}
          onSearch={setSearch}
          onChangePerm={changePerm}
          onSave={save}
          onReset={reset}
        />
      </div>
    </div>
  );
}

function RoleItem({ role, active, onClick }: { role: Role; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'relative flex w-full items-center gap-3 rounded-[14px] border border-transparent px-3 py-[11px] text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active ? 'border-border bg-surface-2 shadow-1' : 'hover:bg-surface-2',
      )}
    >
      {active ? (
        <span className="absolute inset-y-3 left-0 w-[3px] rounded-r-[3px] bg-fg dark:bg-primary" />
      ) : null}
      <RoleIco icoClass={role.icoClass} icon={role.icon} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-[13.5px] font-[650]">
          {role.name}
          {role.locked ? <Lock className="size-3 text-fg-subtle" /> : null}
        </div>
        <div className="text-[11.5px] text-fg-subtle">
          {role.sys ? 'Системная роль' : 'Пользовательская роль'}
        </div>
      </div>
      <span className="shrink-0 text-[12px] font-bold tabular-nums text-fg-muted">
        {role.count}
      </span>
    </button>
  );
}

function RoleDetail({
  role,
  modules,
  working,
  dirty,
  lastAction,
  search,
  onSearch,
  onChangePerm,
  onSave,
  onReset,
}: {
  role: Role;
  modules: RolesData['modules'];
  working: PermLevel[];
  dirty: boolean;
  lastAction: 'none' | 'saved' | 'reset';
  search: string;
  onSearch: (v: string) => void;
  onChangePerm: (idx: number, lvl: PermLevel) => void;
  onSave: () => void;
  onReset: () => void;
}) {
  const counts: [number, number, number] = [0, 0, 0];
  working.forEach((l) => {
    counts[l] += 1;
  });
  const q = search.trim().toLowerCase();
  const visible = modules
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => !q || m.name.toLowerCase().includes(q) || m.sub.toLowerCase().includes(q));

  const footInfo: ReactNode = role.locked ? (
    'Системная роль — только просмотр.'
  ) : dirty ? (
    <b className="font-semibold text-fg">Есть несохранённые изменения.</b>
  ) : lastAction === 'saved' ? (
    'Все изменения сохранены.'
  ) : lastAction === 'reset' ? (
    'Изменения отменены.'
  ) : (
    'Все изменения сохраняются автоматически.'
  );

  return (
    <Panel>
      {/* Header */}
      <div className="flex flex-wrap items-start gap-3.5 border-b-[0.5px] border-border px-5 py-[18px]">
        <RoleIco icoClass={role.icoClass} icon={role.icon} size="lg" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-[17px] font-bold tracking-[-0.3px]">{role.name}</h2>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.3px]',
                role.sys
                  ? 'bg-primary-soft text-primary-deep dark:text-primary'
                  : 'bg-surface-3 text-fg-muted',
              )}
            >
              {role.sys ? 'Системная' : 'Своя роль'}
            </span>
          </div>
          <p className="mt-1 max-w-[520px] text-[13px] text-fg-muted">{role.desc}</p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1.5">
          <AvatarStack avas={role.avas} />
          <div className="text-[11.5px] text-fg-subtle">
            <b className="font-semibold text-fg-muted">{role.count}</b>{' '}
            {pluralRu(role.count, ['сотрудник', 'сотрудника', 'сотрудников'])}
          </div>
        </div>
      </div>

      {/* Perms toolbar */}
      <div className="flex flex-wrap items-center gap-3 border-b-[0.5px] border-border bg-surface-2 px-5 py-3">
        <div className="relative max-w-[280px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            type="search"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Найти раздел…"
            className="h-[34px] w-full rounded-lg border-[0.5px] border-border-strong bg-surface pl-8 pr-3 text-[12.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-primary focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          />
        </div>
        <div className="ml-auto text-[12px] text-fg-muted max-sm:w-full">
          <b className="font-semibold text-fg">{counts[2]}</b> управление ·{' '}
          <b className="font-semibold text-fg">{counts[1]}</b> просмотр ·{' '}
          <b className="font-semibold text-fg">{counts[0]}</b> закрыто
        </div>
      </div>

      {/* Column header */}
      <div className="hidden grid-cols-[1fr_312px] gap-4 border-b-[0.5px] border-border px-5 py-2.5 text-[10.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle sm:grid">
        <div>Раздел</div>
        <div className="grid grid-cols-3 gap-[3px] text-center">
          <span>Нет</span>
          <span>Просмотр</span>
          <span>Управление</span>
        </div>
      </div>

      {/* Lock note */}
      {role.locked ? (
        <div className="mx-5 mt-3.5 flex items-start gap-2.5 rounded-[10px] border-[0.5px] border-border bg-surface-2 px-3.5 py-3 text-[12.5px] text-fg-muted">
          <Lock className="mt-px size-4 shrink-0 text-fg-subtle" />
          <span>
            <b className="font-semibold text-fg">Системная роль.</b> Права заданы платформой и не
            редактируются. Чтобы настроить доступ под себя — создайте копию роли.
          </span>
        </div>
      ) : null}

      {/* Perm rows */}
      {visible.length === 0 ? (
        <EmptyState
          icon={Search}
          title="Ничего не найдено"
          message="Не нашли раздел по этому запросу. Попробуйте другое слово."
        />
      ) : (
        <div className="py-1">
          {visible.map(({ m, i }) => {
            const Icon = MODULE_ICON[m.icon];
            return (
              <div
                key={m.id}
                className="grid grid-cols-1 gap-3 border-b-[0.5px] border-border px-5 py-3 last:border-b-0 sm:grid-cols-[1fr_312px] sm:items-center sm:gap-4"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-[9px] bg-surface-3 text-fg-muted">
                    {Icon ? <Icon className="size-4" strokeWidth={2} /> : null}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[13.5px] font-semibold">{m.name}</div>
                    <div className="truncate text-[11.5px] text-fg-subtle">{m.sub}</div>
                  </div>
                </div>
                <Seg
                  value={working[i] ?? 0}
                  disabled={role.locked}
                  onChange={(lvl) => onChangePerm(i, lvl)}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="flex flex-wrap items-center gap-3 border-t-[0.5px] border-border bg-surface-2 px-5 py-3.5">
        <div className="text-[12.5px] text-fg-muted">{footInfo}</div>
        {!role.locked ? (
          <div className="ml-auto flex gap-2.5 max-sm:w-full">
            <button
              type="button"
              onClick={onReset}
              disabled={!dirty}
              className="inline-flex h-[34px] items-center rounded-lg border-[0.5px] border-border-strong bg-surface px-3.5 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 max-sm:flex-1 max-sm:justify-center"
            >
              Сбросить
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={!dirty}
              className="inline-flex h-[34px] items-center gap-1.5 rounded-lg bg-fg px-4 text-[12.5px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8] max-sm:flex-1 max-sm:justify-center"
            >
              <Check className="size-3.5" strokeWidth={2.6} />
              Сохранить
            </button>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
