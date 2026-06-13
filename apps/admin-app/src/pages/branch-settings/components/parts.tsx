import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { ChevronLeft, Users, Dumbbell, Activity } from '@/components/icons';
import { Switch } from '@/components/settings/controls';
import { useSettingsDirty } from '@/components/settings/context';
import { BranchStatusPill } from '@/features/branches/StatusPill';
import type { Branch, WorkingDay, Zone, ZoneKind } from '@/features/branches/types';

/* ---------- Page head ---------- */

export function BranchSettingsHead({ branch }: { branch: Branch }) {
  return (
    <div>
      <Link
        to={ROUTES.branches}
        className="inline-flex items-center gap-1 text-[13px] font-medium text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="size-3.5" />
        Филиалы
      </Link>
      <div className="mt-2 flex items-center gap-3.5">
        <span
          style={{ background: branch.gradient }}
          className="grid size-[46px] shrink-0 place-items-center rounded-[13px] text-[17px] font-extrabold text-white"
        >
          {branch.mark}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.5px] sm:text-[26px]">
              {branch.name}
            </h1>
            <BranchStatusPill status={branch.status} />
          </div>
          <p className="mt-1 text-[13px] text-fg-subtle">
            м. {branch.metro} · {branch.addr} · #{branch.code}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ---------- Hours editor ---------- */

function TimeInput({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  return (
    <input
      type="text"
      inputMode="numeric"
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-[34px] w-14 rounded-[9px] border-[0.5px] border-border-strong bg-surface-2 text-center text-[13px] tabular-nums text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)] sm:w-16"
    />
  );
}

export function HoursEditor({ hours, sectionId }: { hours: WorkingDay[]; sectionId: string }) {
  const { markDirty } = useSettingsDirty();
  const [days, setDays] = useState<WorkingDay[]>(hours);

  const patch = (i: number, p: Partial<WorkingDay>) => {
    setDays((prev) => prev.map((d, idx) => (idx === i ? { ...d, ...p } : d)));
    markDirty(sectionId);
  };

  return (
    <div>
      {days.map((d, i) => (
        <div
          key={d.day}
          className="grid grid-cols-[64px_1fr_auto] items-center gap-2 border-b-[0.5px] border-border py-2.5 last:border-b-0 sm:grid-cols-[90px_1fr_auto] sm:gap-3"
        >
          <span className={cn('text-[13px] font-semibold', d.closed && 'text-fg-subtle')}>
            {d.day}
          </span>
          <div className="flex items-center gap-2">
            {d.closed ? (
              <span className="text-[13px] text-fg-subtle">Выходной</span>
            ) : (
              <>
                <TimeInput
                  value={d.open}
                  onChange={(v) => patch(i, { open: v })}
                  label={`${d.day}: открытие`}
                />
                <span className="text-fg-subtle">—</span>
                <TimeInput
                  value={d.close}
                  onChange={(v) => patch(i, { close: v })}
                  label={`${d.day}: закрытие`}
                />
              </>
            )}
          </div>
          <Switch
            checked={!d.closed}
            ariaLabel={`${d.day}: рабочий день`}
            onChange={(open) => patch(i, { closed: !open })}
          />
        </div>
      ))}
    </div>
  );
}

/* ---------- Zone row ---------- */

const ZONE_ICON: Record<ZoneKind, typeof Users> = {
  group: Users,
  personal: Dumbbell,
  cardio: Activity,
};

export function ZoneRow({ zone }: { zone: Zone }) {
  const Icon = ZONE_ICON[zone.kind];
  return (
    <div className="flex items-center gap-3 border-b-[0.5px] border-border py-3 last:border-b-0">
      <span className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-surface-3 text-fg-muted">
        <Icon className="size-4" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold">{zone.name}</div>
        <div className="mt-px text-[11.5px] text-fg-subtle">{zone.sub}</div>
      </div>
      <span className="shrink-0 text-[13px] font-[650] tabular-nums text-fg-muted">
        {zone.capacity}
      </span>
    </div>
  );
}

/* ---------- Danger row ---------- */

export function DangerRow({
  title,
  desc,
  action,
  first,
}: {
  title: string;
  desc: string;
  action: ReactNode;
  first?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-x-4 gap-y-2 py-3.5',
        !first && 'border-t-[0.5px] border-danger/20',
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold">{title}</div>
        <div className="mt-0.5 max-w-[460px] text-[12px] leading-relaxed text-fg-subtle">
          {desc}
        </div>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  );
}
