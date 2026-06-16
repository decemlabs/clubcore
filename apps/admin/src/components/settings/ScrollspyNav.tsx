import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import {
  Bell,
  Building2,
  Calendar,
  ChevronRight,
  Clock,
  Code,
  CreditCard,
  Download,
  FileText,
  Gift,
  History,
  LayoutGrid,
  Link2,
  Lock,
  Mail,
  MessageSquare,
  Monitor,
  Percent,
  Shield,
  SlidersHorizontal,
  Smartphone,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  Users,
} from '@/components/icons';

/** Иконки sub-nav (ключ → lucide). Общий словарь для всех настроечных страниц. */
const ICON: Record<string, LucideIcon> = {
  user: User,
  lock: Lock,
  building: Building2,
  clock: Clock,
  calendar: Calendar,
  card: CreditCard,
  bell: Bell,
  smartphone: Smartphone,
  users: Users,
  shield: Shield,
  code: Code,
  gift: Gift,
  danger: TriangleAlert,
  monitor: Monitor,
  link: Link2,
  message: MessageSquare,
  mail: Mail,
  history: History,
  file: FileText,
  zones: LayoutGrid,
  percent: Percent,
  trash: Trash2,
  upload: Upload,
  download: Download,
  sliders: SlidersHorizontal,
};

export interface ScrollspyNavLink {
  id: string;
  label: string;
  icon: string;
  pill?: string;
  /** Ссылка на отдельную страницу (а не якорь-скролл внутри текущей). */
  external?: boolean;
  /** Маршрут перехода для external-ссылки. */
  to?: string;
  danger?: boolean;
}
export interface ScrollspyNavGroup {
  title: string;
  links: ScrollspyNavLink[];
}

const BASE =
  'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/**
 * Закреплённая sub-nav с подсветкой активной секции по scroll (IntersectionObserver)
 * и плавным скроллом по клику. Ссылки с `external` ведут на отдельный маршрут (router Link)
 * и не участвуют в scrollspy. Источник — settings-страницы; вынесено в общий слой,
 * т.к. переиспользуется System-Settings и Branch-Settings.
 */
export function ScrollspyNav({
  groups,
  className,
}: {
  groups: ScrollspyNavGroup[];
  className?: string;
}) {
  const ids = groups.flatMap((g) => g.links.filter((l) => !l.external).map((l) => l.id));
  const [active, setActive] = useState(ids[0] ?? '');

  useEffect(() => {
    const first = ids[0] ? document.getElementById(ids[0]) : null;
    let root: HTMLElement | null = first?.parentElement ?? null;
    while (root) {
      const oy = getComputedStyle(root).overflowY;
      if (oy === 'auto' || oy === 'scroll') break;
      root = root.parentElement;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { root, rootMargin: '-80px 0px -70% 0px', threshold: 0 },
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActive(id);
  };

  return (
    <nav
      className={cn(
        'sticky top-4 hidden max-h-[calc(100vh-6rem)] flex-col gap-4 self-start overflow-y-auto pb-4 [scrollbar-width:none] lg:flex',
        className,
      )}
    >
      {groups.map((g) => (
        <div key={g.title}>
          {g.title ? (
            <div className="px-2.5 pb-1.5 text-[10px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
              {g.title}
            </div>
          ) : null}
          <div className="flex flex-col gap-0.5">
            {g.links.map((l) => {
              const Icon = ICON[l.icon] ?? User;
              if (l.external && l.to) {
                return (
                  <Link
                    key={l.id}
                    to={l.to}
                    className={cn(
                      BASE,
                      'group text-fg-muted hover:bg-surface-2 hover:text-fg',
                      l.danger && 'text-danger hover:bg-danger-soft',
                    )}
                  >
                    <Icon className="size-3.5 shrink-0" />
                    <span className="truncate">{l.label}</span>
                    {l.pill ? (
                      <span className="ml-auto rounded-full bg-surface-3 px-1.5 py-px text-[10px] font-bold tabular-nums text-fg-muted">
                        {l.pill}
                      </span>
                    ) : null}
                    <ChevronRight
                      className={cn(
                        'size-3 shrink-0 text-fg-subtle transition-transform group-hover:translate-x-0.5',
                        l.pill ? '' : 'ml-auto',
                      )}
                      strokeWidth={2.4}
                    />
                  </Link>
                );
              }
              const isActive = active === l.id;
              return (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => go(l.id)}
                  className={cn(
                    BASE,
                    l.danger
                      ? 'mt-2 text-danger hover:bg-danger-soft'
                      : isActive
                        ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                        : 'text-fg-muted hover:bg-surface-2 hover:text-fg',
                  )}
                >
                  <Icon className="size-3.5 shrink-0" />
                  <span className="truncate">{l.label}</span>
                  {l.pill ? (
                    <span
                      className={cn(
                        'ml-auto rounded-full px-1.5 py-px text-[10px] font-bold tabular-nums',
                        isActive ? 'bg-bg/20 dark:bg-[#06120c]/20' : 'bg-surface-3 text-fg-muted',
                      )}
                    >
                      {l.pill}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
