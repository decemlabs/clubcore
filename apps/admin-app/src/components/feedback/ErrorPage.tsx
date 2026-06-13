import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Search,
  Lock,
  TriangleAlert,
  Wrench,
  WifiOff,
  Home,
  ArrowLeft,
  RefreshCw,
  Link2,
  Shield,
  Code,
} from '@/components/icons';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';

export type ErrorCode = 404 | 403 | 500 | 503 | 'offline';

type GlyphTone = 'accent' | 'warning' | 'danger' | 'neutral';

interface ErrorAction {
  label: string;
  icon?: LucideIcon;
  /** Целевой маршрут (рендерится как <Link>). */
  to?: string;
  /** Обработчик клика (reload / history.back / запрос доступа). */
  onClick?: () => void;
  variant?: 'primary' | 'ghost';
}

interface ErrorVariant {
  /** Надпись-надзаголовок над кодом + тон точки. */
  eyebrow: string;
  tone: GlyphTone;
  /** Большой код, разбитый на «до глифа» / «после глифа» (напр. 4·4, 4·3, 5·0). */
  codeLead?: string;
  codeTail?: string;
  glyph: LucideIcon;
  title: string;
  lead: ReactNode;
  actions: ErrorAction[];
  detail?: { icon: LucideIcon; label: string; value: string };
  /** Подвал с подсказками-ссылками. */
  helplinks?: ReactNode;
}

const DOT_TONE: Record<GlyphTone, string> = {
  accent: 'bg-primary',
  warning: 'bg-warning',
  danger: 'bg-danger',
  neutral: 'bg-fg-subtle',
};

const GLYPH_TONE: Record<GlyphTone, string> = {
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warning: 'bg-warning-soft text-warning-deep',
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-surface-3 text-fg-muted',
};

function requestAccess() {
  toast.success('Заявка на доступ отправлена', {
    description: 'Администратор рассмотрит её в течение рабочего дня.',
  });
}

const back: ErrorAction = {
  label: 'Назад',
  icon: ArrowLeft,
  variant: 'ghost',
  onClick: () => window.history.back(),
};
const toDashboard = (label = 'На дашборд'): ErrorAction => ({
  label,
  icon: Home,
  to: ROUTES.dashboard,
  variant: 'primary',
});

const VARIANTS: Record<ErrorCode, ErrorVariant> = {
  404: {
    eyebrow: 'Страница не найдена',
    tone: 'accent',
    codeLead: '4',
    codeTail: '4',
    glyph: Search,
    title: 'Такой страницы нет',
    lead: 'Ссылка устарела или была перемещена. Проверьте адрес или вернитесь на дашборд.',
    actions: [toDashboard(), back],
    // value подставляется на рендере живым путём (см. requestedPath ниже).
    detail: { icon: Link2, label: 'Запрошенный адрес', value: '/' },
    helplinks: (
      <>
        Часто ищут:{' '}
        <Link
          className="font-semibold text-primary-deep hover:underline dark:text-primary"
          to={ROUTES.clients}
        >
          Клиенты
        </Link>
        <span className="mx-2 opacity-50">·</span>
        <Link
          className="font-semibold text-primary-deep hover:underline dark:text-primary"
          to={ROUTES.schedule}
        >
          Расписание
        </Link>
        <span className="mx-2 opacity-50">·</span>
        <Link
          className="font-semibold text-primary-deep hover:underline dark:text-primary"
          to={ROUTES.reports}
        >
          Отчёты
        </Link>
      </>
    ),
  },
  403: {
    eyebrow: 'Доступ запрещён',
    tone: 'warning',
    codeLead: '4',
    codeTail: '3',
    glyph: Lock,
    title: 'Доступ к разделу закрыт',
    lead: (
      <>
        У вашей роли <b className="font-semibold text-fg">«Ресепшн»</b> нет прав на просмотр этой
        страницы. Если доступ нужен для работы — запросите его у администратора.
      </>
    ),
    actions: [
      toDashboard('Вернуться на дашборд'),
      { label: 'Запросить доступ', variant: 'ghost', onClick: requestAccess },
    ],
    detail: { icon: Shield, label: 'Требуется право', value: 'reports.view · role: manager+' },
  },
  500: {
    eyebrow: 'Ошибка сервера',
    tone: 'danger',
    codeLead: '5',
    codeTail: '0',
    glyph: TriangleAlert,
    title: 'Что-то пошло не так',
    lead: 'На нашей стороне произошёл сбой. Мы уже получили уведомление и работаем над этим. Попробуйте обновить страницу через минуту.',
    actions: [
      {
        label: 'Обновить страницу',
        icon: RefreshCw,
        variant: 'primary',
        onClick: () => window.location.reload(),
      },
      toDashboard(),
    ],
    detail: { icon: Code, label: 'Код инцидента — сообщите в поддержку', value: 'ERR-50031-A7F2' },
    helplinks: (
      <>
        Проблема не уходит?{' '}
        <button
          type="button"
          className="font-semibold text-primary-deep hover:underline dark:text-primary"
          onClick={() => toast('Откроется чат с поддержкой')}
        >
          Написать в поддержку
        </button>
      </>
    ),
  },
  503: {
    eyebrow: 'Технические работы',
    tone: 'warning',
    codeLead: '5',
    codeTail: '3',
    glyph: Wrench,
    title: 'Идёт обслуживание',
    lead: 'Мы ненадолго отключили систему для обновления. Обычно это занимает несколько минут — попробуйте обновить страницу чуть позже.',
    actions: [
      {
        label: 'Обновить страницу',
        icon: RefreshCw,
        variant: 'primary',
        onClick: () => window.location.reload(),
      },
    ],
    detail: { icon: Code, label: 'Окно работ', value: 'до 03:30 МСК' },
  },
  offline: {
    eyebrow: 'Нет подключения',
    tone: 'warning',
    glyph: WifiOff,
    title: 'Нет соединения',
    lead: 'Проверьте интернет. Мы автоматически обновим данные, как только связь восстановится.',
    actions: [
      {
        label: 'Повторить',
        icon: RefreshCw,
        variant: 'primary',
        onClick: () => window.location.reload(),
      },
      toDashboard(),
    ],
  },
};

function ActionButton({ action }: { action: ErrorAction }) {
  const Icon = action.icon;
  const isPrimary = action.variant !== 'ghost';
  const inner = (
    <>
      {Icon ? <Icon className="size-4" strokeWidth={2.2} /> : null}
      {action.label}
    </>
  );
  const className = cn(
    'h-11 gap-2 rounded-[10px] px-5 text-[14px] font-semibold',
    isPrimary
      ? 'bg-fg text-bg hover:bg-fg/90 dark:bg-primary dark:text-primary-foreground dark:hover:bg-[#5ee9b8]'
      : 'border border-border-strong bg-surface text-fg hover:bg-surface-3',
  );
  if (action.to) {
    return (
      <Button asChild className={className}>
        <Link to={action.to}>{inner}</Link>
      </Button>
    );
  }
  return (
    <Button className={className} onClick={action.onClick}>
      {inner}
    </Button>
  );
}

/**
 * Полноэкранная страница ошибки (404 / 403 / 500 / 503 / offline) по design/Errors.html.
 * Большой код с глифом-плиткой в центре, надзаголовок с точкой, лид, действия,
 * деталь-чип (моно) и подсказки-ссылки. Работает в трёх контекстах:
 * как errorElement роутера, как catch-all '*' внутри AppLayout (с хромом) и как
 * chrome-less /error — поэтому h-full (родители по цепочке имеют заданную высоту).
 */
export function ErrorPage({ code = 404 }: { code?: ErrorCode }) {
  const v = VARIANTS[code] ?? VARIANTS[404];
  const Glyph = v.glyph;
  // Живой путь на рендере (для 404 «Запрошенный адрес»); не на уровне модуля — иначе
  // при SPA-переходе на битую ссылку чип покажет устаревший адрес.
  const requestedPath = typeof window !== 'undefined' ? window.location.pathname : '/';

  return (
    <div className="relative flex h-full flex-col items-center justify-center overflow-hidden px-6 py-12 text-center">
      {/* Декоративное изумрудное свечение сверху */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-[10%] left-1/2 size-[620px] -translate-x-1/2 rounded-full"
        style={{
          background:
            'radial-gradient(circle, color-mix(in oklab, var(--color-primary) 9%, transparent), transparent 66%)',
        }}
      />

      <div className="relative w-full max-w-[480px]">
        <div className="mb-[18px] inline-flex items-center gap-[7px] text-[11.5px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
          <span className={cn('size-1.5 rounded-full', DOT_TONE[v.tone])} />
          {v.eyebrow}
        </div>

        {v.codeLead ? (
          <div className="mb-1.5 flex items-center justify-center gap-1 text-[80px] font-extrabold leading-none tracking-tighter text-fg sm:text-[112px]">
            <span>{v.codeLead}</span>
            <span
              className={cn(
                'grid size-[72px] place-items-center rounded-[22px] sm:size-[92px] sm:rounded-[26px]',
                GLYPH_TONE[v.tone],
              )}
            >
              <Glyph className="size-9 sm:size-11" strokeWidth={1.7} />
            </span>
            <span>{v.codeTail}</span>
          </div>
        ) : (
          <div className="mb-1.5 flex justify-center">
            <span
              className={cn(
                'grid size-[88px] place-items-center rounded-[26px]',
                GLYPH_TONE[v.tone],
              )}
            >
              <Glyph className="size-11" strokeWidth={1.7} />
            </span>
          </div>
        )}

        <h1 className="mx-auto mb-2.5 mt-5 max-w-[420px] text-balance text-[27px] font-bold leading-[1.18] tracking-[-0.7px] text-fg">
          {v.title}
        </h1>
        <p className="mx-auto mb-[26px] max-w-[400px] text-[15px] leading-[1.6] text-fg-muted">
          {v.lead}
        </p>

        <div className="flex flex-wrap justify-center gap-2.5">
          {v.actions.map((action) => (
            <ActionButton key={action.label} action={action} />
          ))}
        </div>

        {v.detail ? (
          <div className="mx-auto mt-[26px] inline-flex max-w-full items-center gap-2.5 rounded-[14px] border border-border bg-surface px-[15px] py-[11px] text-left shadow-sm">
            <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-surface-3 text-fg-muted">
              <v.detail.icon className="size-[15px]" />
            </span>
            <span className="min-w-0">
              <span className="block text-[11px] text-fg-subtle">{v.detail.label}</span>
              <span className="block truncate font-mono text-[12px] font-semibold text-fg">
                {code === 404 ? requestedPath : v.detail.value}
              </span>
            </span>
          </div>
        ) : null}

        {v.helplinks ? <div className="mt-7 text-[13px] text-fg-subtle">{v.helplinks}</div> : null}
      </div>
    </div>
  );
}
