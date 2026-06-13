import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/app/routes';
import { cn } from '@/lib/cn';
import { formatInt } from '@/lib/format';
import { Initials } from '@/components/ui/initials';
import { MetricTile } from '@/components/ui/MetricTile';
import { useModals } from '@/components/modals/modals-context';
import {
  MapPin,
  Clock,
  Users,
  User,
  Banknote,
  Settings,
  SquarePen,
  Plus,
} from '@/components/icons';
import { BranchStatusPill } from '@/features/branches/StatusPill';
import type { Branch } from '@/features/branches/types';

const GHOST =
  'inline-flex h-[34px] items-center justify-center gap-1.5 rounded-[9px] border-[0.5px] border-border-strong bg-surface px-3 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/* ---------- Summary strip tile ---------- */

export function SummaryTile(props: { label: string; value: ReactNode; unit?: string }) {
  return <MetricTile {...props} />;
}

/* ---------- Branch card ---------- */

function KpiCell({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="bg-surface px-4 py-[13px]">
      <div className="flex items-center gap-1.5 text-[11px] text-fg-subtle">
        <Icon className="size-3.5 shrink-0" strokeWidth={2} />
        {label}
      </div>
      <div className="mt-1 text-[17px] font-bold tabular-nums tracking-[-0.3px]">
        {value}
        {unit ? <span className="text-[12px] font-semibold text-fg-subtle">{unit}</span> : null}
      </div>
    </div>
  );
}

export function BranchCard({ branch }: { branch: Branch }) {
  const { open } = useModals();
  const isSoon = branch.status === 'soon';

  return (
    <div className="flex flex-col overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2">
      {/* Top */}
      <div className="flex items-start gap-3 px-[18px] pb-3.5 pt-[18px]">
        <span
          style={{ background: branch.gradient }}
          className="grid size-[46px] shrink-0 place-items-center rounded-[13px] text-[17px] font-extrabold text-white"
        >
          {branch.mark}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[16px] font-bold tracking-[-0.3px]">{branch.name}</span>
            <BranchStatusPill status={branch.status} />
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[12.5px] text-fg-subtle">
            <MapPin className="size-3.5 shrink-0" strokeWidth={2} />
            <span className="truncate">
              м. {branch.metro} · {branch.addr}
            </span>
          </div>
        </div>
      </div>

      {/* Manager bar */}
      <div className="flex items-center gap-2.5 border-y-[0.5px] border-border bg-surface-2 px-[18px] py-3">
        {branch.manager ? (
          <Initials
            initials={branch.manager.initials}
            color={branch.manager.gradient}
            className="size-7 text-[11px]"
          />
        ) : (
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-3 text-[11px] font-bold text-fg-subtle">
            —
          </span>
        )}
        <div className="min-w-0">
          <div className="truncate text-[12.5px] font-semibold">
            {branch.manager?.name ?? 'Не назначен'}
          </div>
          <div className="text-[11px] text-fg-subtle">Управляющий</div>
        </div>
      </div>

      {/* KPI grid */}
      {isSoon ? (
        <div className="bg-surface px-4 py-3.5">
          <div className="flex items-center gap-1.5 text-[11px] text-fg-subtle">
            <Clock className="size-3.5 shrink-0" strokeWidth={2} />
            {branch.opening}
          </div>
          <div className="mt-1 text-[14px] text-fg-muted">Идёт подготовка зала</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-px bg-border">
          <KpiCell icon={Users} label="Клиенты" value={formatInt(branch.clients)} />
          <KpiCell icon={User} label="Тренеры" value={String(branch.trainers)} />
          <KpiCell icon={Clock} label="Заполн." value={String(branch.occ)} unit="%" />
          <KpiCell icon={Banknote} label="Выручка" value={formatInt(branch.mrr)} unit=" ₽" />
        </div>
      )}

      {/* Footer */}
      <div className="mt-auto flex gap-2 px-[18px] py-3.5">
        <Link to={ROUTES.branch(branch.id)} className={cn(GHOST, 'flex-1')}>
          <Settings className="size-3.5" strokeWidth={2} />
          Настройки
        </Link>
        <button
          type="button"
          onClick={() => open('branch', { branch: { branchId: branch.id } })}
          className={cn(GHOST, 'flex-1')}
        >
          <SquarePen className="size-3.5" strokeWidth={2} />
          Изменить
        </button>
      </div>
    </div>
  );
}

/* ---------- "Add branch" draft card ---------- */

export function DraftCard() {
  const { open } = useModals();
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[18px] border border-dashed border-border-strong bg-surface-2 px-6 text-center">
      <span className="mb-3.5 grid size-[52px] place-items-center rounded-[15px] bg-surface-3 text-fg-subtle">
        <Plus className="size-6" strokeWidth={2} />
      </span>
      <div className="text-[14.5px] font-[650]">Добавить филиал</div>
      <p className="mb-4 mt-1 max-w-[220px] text-[12.5px] text-fg-subtle">
        Новый зал появится в переключателе и отчётах
      </p>
      <button type="button" onClick={() => open('branch')} className={GHOST}>
        Создать
      </button>
    </div>
  );
}
