import { cn } from '@/lib/cn';

/**
 * Цветной аватар-инициалы. Цвет приходит из данных (per-entity), поэтому задаётся
 * инлайн-стилем, а не токеном. Размер по умолчанию — size-7; переопределяется className.
 * Декоративный (aria-hidden) — имя клиента всегда читается рядом.
 */
export function Initials({
  initials,
  color,
  className,
}: {
  initials: string;
  color: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      style={{ background: color }}
      className={cn(
        'grid size-7 shrink-0 place-items-center rounded-full text-[10.5px] font-bold tracking-[-0.2px] text-white',
        className,
      )}
    >
      {initials}
    </span>
  );
}
