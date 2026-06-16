import { Lock, ShieldCheck, CheckCircle2 } from '@/components/icons';
import type { LucideIcon } from 'lucide-react';

const FEATURES: { icon: LucideIcon; label: string }[] = [
  { icon: Lock, label: 'Шифрованное соединение и двухфакторная защита' },
  { icon: ShieldCheck, label: 'Гибкие роли и права доступа для сотрудников' },
  { icon: CheckCircle2, label: 'Журнал входов и активность по филиалам' },
];

/**
 * Левая брендовая панель логина — всегда тёмная (вне зависимости от темы), поэтому
 * цвета фиксированные: проектный тёмный градиент + изумрудное radial-свечение.
 * Скрыта ниже 860px (форма занимает весь экран).
 */
export function BrandPanel() {
  return (
    <aside
      className="relative hidden flex-col overflow-hidden p-[48px_56px] text-[#f5f5f4] min-[860px]:flex"
      style={{ background: 'linear-gradient(160deg,#1c1917,#2a2826)' }}
    >
      {/* Изумрудное свечение сверху-справа */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-[160px] -top-[180px] size-[460px] rounded-full"
        style={{
          background:
            'radial-gradient(circle, color-mix(in oklab, var(--color-primary) 26%, transparent), transparent 68%)',
        }}
      />

      {/* Лого */}
      <div className="relative flex items-center gap-2.5">
        <span className="grid size-[34px] place-items-center rounded-[10px] bg-primary text-[17px] font-extrabold text-primary-foreground">
          М
        </span>
        <span className="text-[16px] font-bold tracking-[-0.3px]">Мой&nbsp;зал</span>
        <span className="ml-auto rounded-full bg-white/[0.07] px-[9px] py-[3px] text-[10px] font-bold tracking-[0.5px] text-[#f5f5f4]/55">
          ADMIN
        </span>
      </div>

      {/* Геро */}
      <div className="relative my-auto max-w-[420px]">
        <h2 className="text-balance text-[34px] font-bold leading-[1.12] tracking-[-0.8px]">
          Управляйте залом <span className="text-primary">из одного окна.</span>
        </h2>
        <p className="mt-3.5 text-[14.5px] leading-[1.6] text-[#f5f5f4]/60">
          Клиенты, абонементы, расписание и касса — всё под рукой. Войдите, чтобы продолжить работу.
        </p>

        <ul className="mt-[30px] flex flex-col gap-[13px]">
          {FEATURES.map(({ icon: Icon, label }) => (
            <li key={label} className="flex items-center gap-3">
              <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
                <Icon className="size-[15px]" strokeWidth={2} />
              </span>
              <span className="text-[13.5px] text-[#f5f5f4]/80">{label}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Подвал */}
      <div className="relative flex flex-wrap items-center gap-4 text-[12px] text-[#f5f5f4]/40">
        <span>© 2026 «Мой зал»</span>
        <span className="size-1 rounded-full bg-current" />
        <span>Тверская · Сокольники · Новокосино</span>
      </div>
    </aside>
  );
}
