import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { formatDateRu } from '@/lib/format';
import type { ClientData } from '@/features/clients/schemas';

/** Строка клиента в списке (для реального ClientData из backend). */
export function ClientRow({ client: c }: { client: ClientData }) {
  const initials = [c.lastName, c.firstName]
    .filter(Boolean)
    .map((s) => s[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2);

  const fullName = [c.lastName, c.firstName, c.middleName].filter(Boolean).join(' ');

  // Default avatar color: emerald gradient (brand primary) when no per-entity color
  const avatarColor = 'linear-gradient(135deg,#2dd4a4,#059669)';

  return (
    <Link
      to={ROUTES.client(c.id)}
      className="flex items-center gap-3 border-b-[0.5px] border-border px-4 py-3 transition-colors hover:bg-surface-2 last:border-b-0"
    >
      <Initials initials={initials} color={avatarColor} className="size-9 shrink-0 text-xs" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-semibold leading-[1.25] tracking-[-0.1px] text-fg">
          {fullName}
        </div>
        <div className="mt-px truncate text-[11.5px] tabular-nums text-fg-subtle">{c.phone}</div>
      </div>
      {c.email && (
        <div className="hidden min-w-0 max-w-[200px] truncate text-[12.5px] text-fg-muted sm:block">
          {c.email}
        </div>
      )}
      {c.tags.length > 0 && (
        <div className="hidden items-center gap-1 sm:flex">
          {c.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className={cn(
                'inline-flex h-[22px] items-center rounded-full border-[0.5px] border-border bg-surface-2 px-2 text-[11px] font-medium text-fg-muted',
              )}
            >
              {tag}
            </span>
          ))}
          {c.tags.length > 3 && (
            <span className="text-[11px] text-fg-subtle">+{c.tags.length - 3}</span>
          )}
        </div>
      )}
      <div className="shrink-0 text-right text-[11.5px] tabular-nums text-fg-subtle">
        {formatDateRu(c.createdAt)}
      </div>
    </Link>
  );
}
