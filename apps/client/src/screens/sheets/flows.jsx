import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { Divider3, FormRow } from '@/screens/sheets/ProfileExtraSheets.jsx';

// ─── Shared chrome ─────────────────────────────────────────────
export function FlowSheet({ children, color = 'var(--bg)' }) {
  return (
    <div role="dialog" aria-modal="true" style={{
      position: 'absolute', inset: 0, zIndex: 230, background: color,
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      {children}
    </div>
  );
}

export function FlowHeader({ title, onClose, onBack, action }) {
  const left = onBack || onClose;
  return (
    <div style={{
      position: 'relative', padding: '50px 12px 8px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
    }}>
      <button onClick={left} aria-label={onBack ? 'Назад' : 'Закрыть'} style={{
        width: 36, height: 36, borderRadius: 999, border: 0,
        background: 'var(--surface)', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name={onBack ? 'chevronLeft' : 'close'} size={onBack ? 22 : 20} color="var(--text)" strokeWidth={2.2} />
      </button>
      <span className="t-h3" style={{
        fontSize: 15, position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, calc(-50% + 21px))', pointerEvents: 'none',
        whiteSpace: 'nowrap',
      }}>{title}</span>
      <div style={{ minWidth: 36, display: 'flex', justifyContent: 'flex-end' }}>{action}</div>
    </div>
  );
}

// Big icon + title + body + actions — used by all confirmation/error variants
export function ResultLayout({ tone = 'success', icon, title, body, primary, secondary, extras }) {
  const palette = {
    success: { bg: 'var(--accent-soft)', fg: 'var(--accent-deep)', ring: 'var(--accent)' },
    error:   { bg: 'var(--danger-soft)', fg: 'var(--danger)',      ring: 'var(--danger)' },
    warn:    { bg: 'var(--warn-soft)',   fg: '#a36a16',            ring: 'var(--warn)' },
    info:    { bg: 'var(--surface-2)',   fg: 'var(--text-2)',      ring: 'var(--text-3)' },
  }[tone];
  return (
    <div className="scroller" style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '20px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="haptic" style={{
          width: 92, height: 92, borderRadius: 999,
          background: palette.bg, color: palette.fg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 18,
        }}>
          <Icon name={icon} size={44} color="currentColor" strokeWidth={2} />
        </div>
        <div className="t-display" style={{ marginTop: 22, textAlign: 'center', letterSpacing: -0.8, fontSize: 28, lineHeight: 1.15 }}>
          {title}
        </div>
        <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 8, textAlign: 'center', maxWidth: 300 }}>
          {body}
        </div>
        {extras && <div style={{ width: '100%', marginTop: 22 }}>{extras}</div>}
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ padding: '16px 16px 28px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {primary && <button className="btn btn-accent" onClick={primary.onClick}
                            style={{ width: '100%', height: 54 }}>{primary.label}</button>}
        {secondary && <button className="btn" onClick={secondary.onClick} style={{
          width: '100%', height: 50, background: 'var(--surface)',
          color: 'var(--text)', border: '0.5px solid var(--border-strong)',
        }}>{secondary.label}</button>}
      </div>
    </div>
  );
}

// ─── 1. Booking confirmed (post Book → Checkout success) ───────
export const BookingConfirmedSheet = ({ booking, onClose, onAddToCal }) => {
  const b = booking || { date: 'Среда, 30 апреля', time: '18:00', trainer: 'Аня Соколова', kind: 'Ноги + спина' };
  return (
    <FlowSheet>
      <FlowHeader title="Запись" onClose={onClose} />
      <ResultLayout
        tone="success"
        icon="check"
        title="Ты записан!"
        body={`${b.date} в ${b.time}. Напомним за час — приходи в форме.`}
        extras={
          <div className="card" style={{ padding: 0, margin: '0 8px' }}>
            <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <Avatar initials={b.trainer.split(' ').map(s => s[0]).join('')} bg="var(--surface-2)" color="var(--text)" size={40} />
              <div style={{ flex: 1 }}>
                <div className="t-h3" style={{ fontSize: 14 }}>{b.trainer}</div>
                <div className="t-small">{b.kind}</div>
              </div>
              <Icon name="user" size={18} color="var(--text-3)" />
            </div>
          </div>
        }
        primary={{ label: 'Готово', onClick: onClose }}
        secondary={{ label: 'Добавить в календарь', onClick: onAddToCal || onClose }}
      />
    </FlowSheet>
  );
};

// ─── 2. Receipt / chek (post-pay) ──────────────────────────────
export const ReceiptSheet = ({ ctx, total, onClose }) => {
  const c = ctx || { title: 'Годовой абонемент', subtitle: 'Подписка на 365 дней', kind: 'sub' };
  const txId = 'TX-' + Math.floor(Math.random() * 9e6 + 1e6).toString();
  const now = new Date();
  const fmt = now.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' }) + ', ' +
              now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  return (
    <FlowSheet>
      <FlowHeader title="Чек" onClose={onClose} action={
        <button onClick={() => {}} style={{
          border: 0, background: 'transparent', color: 'var(--text)',
          fontSize: 13, fontWeight: 600, padding: '6px 10px', cursor: 'pointer',
          fontFamily: 'inherit',
        }}>Отправить</button>
      } />
      <div className="scroller" style={{ padding: '8px 16px 28px' }}>
        {/* Receipt "paper" */}
        <div className="receipt" style={{
          background: 'var(--surface)', borderRadius: 22,
          padding: '24px 22px 18px', position: 'relative', overflow: 'hidden',
          border: '0.5px solid var(--border)', boxShadow: 'var(--sh-2)',
        }}>
          {/* Perforated edges */}
          <div className="recp-perf top" />
          <div className="recp-perf bot" />
          <div className="t-mini" style={{ color: 'var(--text-3)', textAlign: 'center', marginBottom: 12 }}>
            Платёж прошёл
          </div>
          <div className="t-display" style={{ fontSize: 36, textAlign: 'center', letterSpacing: -1, lineHeight: 1 }}>
            {(total || 42000).toLocaleString('ru-RU')} ₽
          </div>
          <div className="t-small" style={{ textAlign: 'center', marginTop: 6, color: 'var(--text-2)' }}>
            {c.title}
          </div>
          <div style={{ height: 1, background: 'var(--border)', margin: '20px -4px', borderTop: '1px dashed var(--border-strong)' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <RecpRow k="Услуга" v={c.subtitle || '—'} />
            <RecpRow k="Способ" v="•••• 4821 · MIR" />
            <RecpRow k="Дата" v={fmt} />
            <RecpRow k="Транзакция" v={txId} mono />
          </div>
          <div style={{ height: 1, background: 'var(--border)', margin: '18px -4px', borderTop: '1px dashed var(--border-strong)' }} />
          <div className="t-mini" style={{ textAlign: 'center', color: 'var(--text-3)', lineHeight: 1.5 }}>
            ИП Кабанов А.Б. · ИНН 770000004821<br />
            Электронный чек отправлен на sasha@example.com
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
          <button className="btn" style={{
            flex: 1, height: 48, background: 'var(--surface)', color: 'var(--text)',
            border: '0.5px solid var(--border-strong)', display: 'flex', gap: 8,
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="copy" size={16} color="currentColor" />
            Скопировать №
          </button>
          <button className="btn" style={{
            flex: 1, height: 48, background: 'var(--surface)', color: 'var(--text)',
            border: '0.5px solid var(--border-strong)', display: 'flex', gap: 8,
            alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="image" size={16} color="currentColor" />
            Сохранить PDF
          </button>
        </div>
      </div>

      <style>{`
        .recp-perf {
          position: absolute; left: -8px; right: -8px; height: 16px;
          background-image: radial-gradient(circle at 8px 8px, var(--bg) 6px, transparent 6.5px);
          background-size: 16px 16px;
        }
        .recp-perf.top { top: -8px; }
        .recp-perf.bot { bottom: -8px; }
      `}</style>
    </FlowSheet>
  );
};

function RecpRow({ k, v, mono }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
      <span className="t-small" style={{ color: 'var(--text-3)' }}>{k}</span>
      <span className="t-small" style={{
        color: 'var(--text)', fontWeight: 500,
        fontFamily: mono ? 'ui-monospace, SFMono-Regular, Menlo, monospace' : 'inherit',
        fontSize: mono ? 12 : 13,
        textAlign: 'right',
      }}>{v}</span>
    </div>
  );
}

// ─── 3. Cancel booking with refund policy ──────────────────────
export const CancelBookingSheet = ({ booking, onClose, onConfirm }) => {
  const b = booking || { date: 'Сегодня', time: '18:00', trainer: 'Аня Соколова', amount: 2200, hoursLeft: 5 };
  // Refund schedule: >24h = 100%, 4-24h = 50%, <4h = 0%
  const refundPct = b.hoursLeft >= 24 ? 100 : b.hoursLeft >= 4 ? 50 : 0;
  const refundAmount = Math.round((b.amount * refundPct) / 100);
  const tone = refundPct === 100 ? 'success' : refundPct >= 50 ? 'warn' : 'error';
  return (
    <FlowSheet>
      <FlowHeader title="Отмена записи" onClose={onClose} />
      <div className="scroller" style={{ padding: '4px 16px 16px' }}>
        {/* Hero booking */}
        <div className="card" style={{ padding: 16, marginBottom: 14 }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Тренировка</div>
          <div className="t-h2" style={{ marginTop: 4 }}>{b.date} · {b.time}</div>
          <div className="t-small" style={{ marginTop: 4, color: 'var(--text-2)' }}>
            с {b.trainer} · до начала {b.hoursLeft} ч
          </div>
        </div>

        {/* Refund schedule */}
        <div className="t-mini" style={{ padding: '4px 4px 8px', color: 'var(--text-3)' }}>
          Правила возврата
        </div>
        <div className="card" style={{ padding: 0, marginBottom: 14, overflow: 'hidden' }}>
          <RefundRule active={b.hoursLeft >= 24}     tone="success" range="Больше 24 ч" pct="100 %" />
          <Divider3 />
          <RefundRule active={b.hoursLeft >= 4 && b.hoursLeft < 24} tone="warn" range="От 4 до 24 ч" pct="50 %" />
          <Divider3 />
          <RefundRule active={b.hoursLeft < 4}       tone="error" range="Меньше 4 ч" pct="0 %" />
        </div>

        {/* Computed refund */}
        <div className="card" style={{
          padding: 16, marginBottom: 14,
          background: tone === 'success' ? 'var(--accent-soft)' :
                      tone === 'warn' ? 'var(--warn-soft)' : 'var(--danger-soft)',
          border: 0,
        }}>
          <div className="t-mini" style={{
            color: tone === 'success' ? 'var(--accent-deep)' :
                   tone === 'warn' ? '#a36a16' : 'var(--danger)',
          }}>К возврату</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
            <span className="t-display" style={{
              fontSize: 32, letterSpacing: -0.5,
              color: tone === 'success' ? 'var(--accent-deep)' :
                     tone === 'warn' ? '#a36a16' : 'var(--danger)',
            }}>{refundAmount.toLocaleString('ru-RU')} ₽</span>
            <span className="t-small" style={{ color: 'var(--text-2)' }}>
              из {b.amount.toLocaleString('ru-RU')} ₽
            </span>
          </div>
          <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
            {refundPct === 100 && 'Полный возврат на карту в течение 3 дней.'}
            {refundPct === 50 && 'Половина суммы вернётся на карту в течение 3 дней.'}
            {refundPct === 0 && 'Возврат уже невозможен — слишком близко к началу.'}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button onClick={() => onConfirm?.({ refundAmount, refundPct })}
                  className="btn"
                  style={{ width: '100%', height: 52, background: 'var(--danger)', color: '#fff' }}>
            Отменить запись
          </button>
          <button onClick={onClose} className="btn" style={{
            width: '100%', height: 48, background: 'transparent', color: 'var(--text-2)',
            border: '0.5px solid var(--border-strong)',
          }}>Оставить как есть</button>
        </div>
      </div>
    </FlowSheet>
  );
};

function RefundRule({ active, tone, range, pct }) {
  const palette = {
    success: { fg: 'var(--accent-deep)', bg: 'var(--accent-soft)' },
    warn:    { fg: '#a36a16',            bg: 'var(--warn-soft)' },
    error:   { fg: 'var(--danger)',      bg: 'var(--danger-soft)' },
  }[tone];
  return (
    <div style={{
      padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12,
      background: active ? palette.bg : 'transparent',
      opacity: active ? 1 : 0.7,
    }}>
      <div style={{
        width: 24, height: 24, borderRadius: 999,
        border: `1.6px solid ${active ? palette.fg : 'var(--text-3)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {active && <div style={{ width: 10, height: 10, borderRadius: 999, background: palette.fg }} />}
      </div>
      <div style={{ flex: 1 }}>
        <div className="t-h3" style={{ fontSize: 14, color: active ? palette.fg : 'var(--text)' }}>{range}</div>
      </div>
      <div className="t-h3" style={{ fontSize: 15, color: active ? palette.fg : 'var(--text-2)' }}>{pct}</div>
    </div>
  );
}

// ─── 4. Subscription freeze / extend / refund ──────────────────
function pluralDays(n) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return 'дней';
  if (b > 1 && b < 5) return 'дня';
  if (b === 1) return 'день';
  return 'дней';
}
function addDaysLabel(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const m = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
  return `${d.getDate()} ${m[d.getMonth()]}`;
}

export const SubManageSheet = ({ mode = 'freeze', onClose, onConfirm }) => {
  // mode: 'freeze' | 'extend' | 'refund'
  const [days, setDays] = React.useState(mode === 'freeze' ? 14 : 30);
  const [reason, setReason] = React.useState('');
  const meta = {
    freeze: {
      title: 'Заморозить абонемент',
      lede: 'Пауза до 30 дней в год. Срок продлится на столько же дней.',
      icon: 'snowflake', tone: 'info',
      cta: `Заморозить на ${days} дн`,
      sliderMax: 30, sliderLabel: 'Длительность',
      tip: 'Заморозка стартует со следующего дня. Отменить можно в любой момент.',
    },
    extend: {
      title: 'Продлить абонемент',
      lede: 'Если есть промокод или подарочный сертификат — добавь сюда.',
      icon: 'plus', tone: 'success',
      cta: `Продлить на ${days} дн`,
      sliderMax: 365, sliderLabel: 'Дополнительно',
      tip: 'Цена будет рассчитана по текущему тарифу.',
    },
    refund: {
      title: 'Возврат абонемента',
      lede: 'Возврат за неиспользованные дни, минус 15% за обработку.',
      icon: 'arrowRight', tone: 'warn',
      cta: 'Подать заявку',
      tip: 'Заявку рассмотрим в течение 3 рабочих дней.',
    },
  }[mode];
  const palette = meta.tone === 'success' ? { bg: 'var(--accent-soft)', fg: 'var(--accent-deep)' } :
                  meta.tone === 'warn'    ? { bg: 'var(--warn-soft)',   fg: '#a36a16' } :
                                            { bg: 'var(--surface-2)',   fg: 'var(--text)' };
  return (
    <FlowSheet>
      <FlowHeader title={meta.title} onClose={onClose} />
      <div className="scroller" style={{ padding: '4px 16px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 4px 18px' }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: palette.bg, color: palette.fg,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name={meta.icon === 'snowflake' ? 'sparkle' : meta.icon} size={22} color="currentColor" strokeWidth={2} />
          </div>
          <div className="t-small" style={{ color: 'var(--text-2)', flex: 1 }}>{meta.lede}</div>
        </div>

        {/* Current sub card */}
        <div className="card" style={{ padding: 16, marginBottom: 14 }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Текущий</div>
          <div className="row-between" style={{ marginTop: 6, alignItems: 'baseline' }}>
            <span className="t-h2">Годовой</span>
            <span className="t-small" style={{ color: 'var(--text-2)' }}>47 дней · до 16 июня</span>
          </div>
        </div>

        {/* Duration slider — for freeze / extend */}
        {mode !== 'refund' && (() => {
          const presets = mode === 'freeze' ? [7, 14, 30] : [30, 90, 180, 365];
          const pct = ((days - 1) / (meta.sliderMax - 1)) * 100;
          const accentFg = palette.fg;
          return (
            <div className="card" style={{ padding: '18px 18px 16px', marginBottom: 14, position: 'relative', overflow: 'hidden' }}>
              <style>{`
                .dur-slider{ -webkit-appearance:none; appearance:none; width:100%; height:36px; background:transparent; outline:none; cursor:pointer; padding:0; margin:0; }
                .dur-slider::-webkit-slider-runnable-track{ height:36px; background:transparent; }
                .dur-slider::-moz-range-track{ height:36px; background:transparent; }
                .dur-slider::-webkit-slider-thumb{ -webkit-appearance:none; appearance:none; width:30px; height:30px; border-radius:999px; background:#fff; border:1.5px solid var(--border-strong); box-shadow:0 2px 8px rgba(0,0,0,0.12), 0 0 0 4px var(--surface); margin-top:3px; cursor:grab; transition:transform 0.12s; }
                .dur-slider::-webkit-slider-thumb:active{ transform:scale(1.08); cursor:grabbing; }
                .dur-slider::-moz-range-thumb{ width:30px; height:30px; border-radius:999px; background:#fff; border:1.5px solid var(--border-strong); box-shadow:0 2px 8px rgba(0,0,0,0.12); cursor:grab; }
                .dur-preset{ appearance:none; border:0.5px solid var(--border); background:var(--surface); color:var(--text-2); height:30px; padding:0 12px; border-radius:999px; font-family:inherit; font-size:12.5px; font-weight:600; cursor:pointer; font-variant-numeric:tabular-nums; transition:all 0.15s; }
                .dur-preset[data-active="true"]{ background:var(--text); color:var(--bg); border-color:var(--text); }
              `}</style>

              <div className="row-between" style={{ alignItems: 'baseline' }}>
                <div>
                  <div className="t-mini" style={{ color: 'var(--text-3)' }}>{meta.sliderLabel}</div>
                  <div style={{
                    display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4,
                  }}>
                    <span style={{
                      fontSize: 36, fontWeight: 700, letterSpacing: -1.2,
                      fontVariantNumeric: 'tabular-nums', lineHeight: 1, color: 'var(--text)',
                    }}>{days}</span>
                    <span className="t-small" style={{ color: 'var(--text-2)', fontWeight: 600 }}>
                      {pluralDays(days)}
                    </span>
                  </div>
                </div>
                <div className="t-mini" style={{
                  color: accentFg, fontWeight: 600,
                  padding: '6px 10px', background: palette.bg, borderRadius: 999,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  до {addDaysLabel(days)}
                </div>
              </div>

              {/* Custom slider track */}
              <div style={{ position: 'relative', marginTop: 18, marginBottom: 4, height: 36 }}>
                {/* Background track */}
                <div style={{
                  position: 'absolute', top: '50%', left: 0, right: 0, height: 8,
                  transform: 'translateY(-50%)', background: 'var(--surface-2)',
                  borderRadius: 999,
                }} />
                {/* Fill */}
                <div style={{
                  position: 'absolute', top: '50%', left: 0, width: `${pct}%`, height: 8,
                  transform: 'translateY(-50%)',
                  background: `linear-gradient(90deg, ${accentFg}, var(--accent))`,
                  borderRadius: 999, transition: 'width 0.12s',
                }} />
                {/* Tick marks for presets */}
                {presets.map(p => {
                  const tickPct = ((p - 1) / (meta.sliderMax - 1)) * 100;
                  return (
                    <div key={p} style={{
                      position: 'absolute', top: '50%', left: `${tickPct}%`,
                      transform: 'translate(-50%, -50%)',
                      width: 3, height: 3, borderRadius: 999,
                      background: p <= days ? 'rgba(255,255,255,0.7)' : 'var(--text-3)',
                      opacity: 0.6, pointerEvents: 'none',
                    }} />
                  );
                })}
                <input type="range" min={1} max={meta.sliderMax} value={days}
                       onChange={e => setDays(+e.target.value)}
                       className="dur-slider"
                       style={{ position: 'relative', zIndex: 2 }} />
              </div>

              {/* Preset chips */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                {presets.map(p => (
                  <button key={p} className="dur-preset press"
                          data-active={days === p}
                          onClick={() => setDays(p)}>
                    {p} дн
                  </button>
                ))}
              </div>
            </div>
          );
        })()}

        {/* Refund breakdown */}
        {mode === 'refund' && (
          <div className="card" style={{ padding: 0, marginBottom: 14 }}>
            <div style={{ padding: '14px 16px' }}>
              <div className="row-between">
                <span className="t-small">Стоимость абонемента</span>
                <span className="t-small">42 000 ₽</span>
              </div>
              <div className="row-between" style={{ marginTop: 6 }}>
                <span className="t-small">Использовано (318 дн)</span>
                <span className="t-small">−36 600 ₽</span>
              </div>
              <div className="row-between" style={{ marginTop: 6 }}>
                <span className="t-small">Комиссия за обработку (15%)</span>
                <span className="t-small">−810 ₽</span>
              </div>
            </div>
            <Divider3 />
            <div style={{ padding: '14px 16px' }} className="row-between">
              <span className="t-h3">К возврату</span>
              <span className="t-h2" style={{ color: 'var(--accent-deep)' }}>4 590 ₽</span>
            </div>
          </div>
        )}

        {/* Reason */}
        <div className="card" style={{ padding: '12px 14px', marginBottom: 14 }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', marginBottom: 6 }}>Причина (по желанию)</div>
          <textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder={mode === 'freeze' ? 'Уезжаю / болею / другое' : 'Что не так?'}
            rows={2}
            style={{
              width: '100%', resize: 'none', border: 0, outline: 0,
              fontSize: 15, color: 'var(--text)', fontFamily: 'inherit',
              background: 'transparent', padding: 0,
            }} />
        </div>

        <div className="t-small" style={{
          color: 'var(--text-3)', textAlign: 'center', padding: '0 16px 12px',
        }}>{meta.tip}</div>

        <button className="btn btn-accent" style={{ width: '100%', height: 52 }}
                onClick={() => onConfirm?.({ mode, days, reason })}>
          {meta.cta}
        </button>
      </div>
    </FlowSheet>
  );
};

// ─── 5. SMS verification (for phone / email change) ────────────
export const SmsVerifySheet = ({ target, channel = 'phone', onClose, onVerified }) => {
  const [code, setCode] = React.useState(['', '', '', '']);
  const [resendIn, setResendIn] = React.useState(58);
  const [error, setError] = React.useState(false);
  const refs = [React.useRef(), React.useRef(), React.useRef(), React.useRef()];
  React.useEffect(() => { refs[0].current?.focus(); }, []);
  React.useEffect(() => {
    if (resendIn <= 0) return;
    const id = setTimeout(() => setResendIn(r => r - 1), 1000);
    return () => clearTimeout(id);
  }, [resendIn]);
  const full = code.join('');
  React.useEffect(() => {
    if (full.length === 4) {
      // simulate verify; accept '0000' as wrong for demo
      const ok = full !== '0000';
      setTimeout(() => {
        if (ok) onVerified?.();
        else { setError(true); setTimeout(() => { setCode(['', '', '', '']); setError(false); refs[0].current?.focus(); }, 800); }
      }, 350);
    }
  }, [full]);
  const setDigit = (i, v) => {
    const cleaned = v.replace(/\D/g, '').slice(-1);
    setCode(c => { const n = [...c]; n[i] = cleaned; return n; });
    if (cleaned && i < 3) refs[i + 1].current?.focus();
  };
  const onKey = (i, e) => {
    if (e.key === 'Backspace' && !code[i] && i > 0) refs[i - 1].current?.focus();
  };
  return (
    <FlowSheet>
      <FlowHeader title="Подтверждение" onClose={onClose} />
      <div className="scroller" style={{ display: 'flex', flexDirection: 'column', padding: '0 24px' }}>
        <div style={{ flex: '0 0 12px' }} />
        <div className="t-h1" style={{ textAlign: 'center', fontSize: 22 }}>
          {channel === 'phone' ? 'Введи код из SMS' : 'Введи код из письма'}
        </div>
        <div className="t-body" style={{ textAlign: 'center', color: 'var(--text-2)', marginTop: 8 }}>
          Отправили 4-значный код на<br />
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{target || (channel === 'phone' ? '+7 916 555-12-34' : 'sasha@example.com')}</span>
        </div>

        {/* OTP boxes */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 36 }}>
          {code.map((d, i) => (
            <input
              key={i}
              ref={refs[i]}
              value={d}
              onChange={e => setDigit(i, e.target.value)}
              onKeyDown={e => onKey(i, e)}
              inputMode="numeric"
              maxLength={1}
              style={{
                width: 56, height: 64,
                fontSize: 28, fontWeight: 600, textAlign: 'center',
                background: 'var(--surface)', color: 'var(--text)',
                border: `1.5px solid ${error ? 'var(--danger)' : d ? 'var(--accent)' : 'var(--border-strong)'}`,
                borderRadius: 14, outline: 0, fontFamily: 'inherit',
                animation: error ? 'shake 0.4s' : 'none',
              }} />
          ))}
        </div>
        {error && (
          <div className="t-small" style={{ color: 'var(--danger)', textAlign: 'center', marginTop: 14 }}>
            Код не подошёл, попробуй ещё раз
          </div>
        )}

        <div style={{ marginTop: 36, display: 'flex', justifyContent: 'center' }}>
          {resendIn > 0 ? (
            <span className="t-small" style={{ color: 'var(--text-3)' }}>
              Отправить ещё через {resendIn} с
            </span>
          ) : (
            <button onClick={() => setResendIn(58)} style={{
              border: 0, background: 'transparent', color: 'var(--accent-deep)',
              fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
            }}>Отправить код ещё раз</button>
          )}
        </div>

        <div style={{ flex: 1 }} />
        <div className="t-mini" style={{
          color: 'var(--text-3)', textAlign: 'center', padding: '24px 0',
          textTransform: 'none', letterSpacing: 0,
        }}>
          Подсказка: введи любые 4 цифры. <span style={{ color: 'var(--text-2)' }}>0000</span> → ошибка.
        </div>
      </div>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          75% { transform: translateX(6px); }
        }
      `}</style>
    </FlowSheet>
  );
};

// ─── 6. Delete account ─────────────────────────────────────────
export const DeleteAccountSheet = ({ onClose, onDeleted }) => {
  const [step, setStep] = React.useState('info'); // info | confirm | done
  const [confirmText, setConfirmText] = React.useState('');
  if (step === 'done') {
    return (
      <FlowSheet>
        <ResultLayout
          tone="info"
          icon="check"
          title="Аккаунт удалён"
          body="Жаль, что уходишь. Все данные удалены из системы. До встречи!"
          primary={{ label: 'Закрыть', onClick: onDeleted || onClose }}
        />
      </FlowSheet>
    );
  }
  if (step === 'confirm') {
    return (
      <FlowSheet>
        <FlowHeader title="Удалить аккаунт" onBack={() => setStep('info')} />
        <div className="scroller" style={{ padding: '0 16px 16px' }}>
          <div style={{ padding: '8px 4px 18px' }}>
            <div className="t-h2">Точно удалить?</div>
            <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 8 }}>
              Это действие необратимо. Введи <b style={{ color: 'var(--text)' }}>УДАЛИТЬ</b> заглавными буквами, чтобы подтвердить.
            </div>
          </div>
          <div className="card" style={{ padding: '12px 14px', marginBottom: 16 }}>
            <input
              value={confirmText}
              onChange={e => setConfirmText(e.target.value.toUpperCase())}
              placeholder="УДАЛИТЬ"
              style={{
                width: '100%', border: 0, outline: 0, background: 'transparent',
                fontSize: 18, fontWeight: 600, letterSpacing: 1,
                color: 'var(--danger)', fontFamily: 'inherit', textAlign: 'center',
              }}
            />
          </div>
          <button
            disabled={confirmText !== 'УДАЛИТЬ'}
            onClick={() => setStep('done')}
            className="btn"
            style={{
              width: '100%', height: 52,
              background: confirmText === 'УДАЛИТЬ' ? 'var(--danger)' : 'var(--surface-2)',
              color: confirmText === 'УДАЛИТЬ' ? '#fff' : 'var(--text-3)',
              border: 0,
            }}>Удалить навсегда</button>
        </div>
      </FlowSheet>
    );
  }
  return (
    <FlowSheet>
      <FlowHeader title="Удалить аккаунт" onClose={onClose} />
      <div className="scroller" style={{ padding: '0 16px 16px' }}>
        <div style={{ padding: '16px 4px 18px' }}>
          <div style={{
            width: 60, height: 60, borderRadius: 16, background: 'var(--danger-soft)',
            color: 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16,
          }}>
            <Icon name="alert" size={28} color="currentColor" strokeWidth={2} />
          </div>
          <div className="t-h2">Что произойдёт</div>
        </div>
        <div className="card" style={{ padding: 0, marginBottom: 14 }}>
          {[
            { i: 'history', t: 'История посещений и тренировок', s: 'Удалится полностью' },
            { i: 'card', t: 'Платёжные данные', s: 'Удалятся из системы' },
            { i: 'chat', t: 'Переписка с тренерами и админом', s: 'Удалится с твоей стороны' },
            { i: 'tag', t: 'Активный абонемент', s: 'Сгорит без возврата' },
          ].map((r, i, a) => (
            <React.Fragment key={r.i}>
              <div style={{ padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: 'var(--surface-2)', color: 'var(--text-2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon name={r.i} size={18} color="currentColor" />
                </div>
                <div style={{ flex: 1 }}>
                  <div className="t-h3" style={{ fontSize: 14 }}>{r.t}</div>
                  <div className="t-small" style={{ color: 'var(--text-3)' }}>{r.s}</div>
                </div>
              </div>
              {i < a.length - 1 && <Divider3 />}
            </React.Fragment>
          ))}
        </div>

        <div className="t-small" style={{
          color: 'var(--text-3)', textAlign: 'center', padding: '8px 16px 18px',
        }}>
          Если есть активный абонемент — лучше сначала <a style={{ color: 'var(--accent-deep)' }}>оформить возврат</a>.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button onClick={() => setStep('confirm')} className="btn"
                  style={{ width: '100%', height: 52, background: 'var(--danger)', color: '#fff' }}>
            Удалить аккаунт
          </button>
          <button onClick={onClose} className="btn" style={{
            width: '100%', height: 48, background: 'transparent', color: 'var(--text-2)',
            border: '0.5px solid var(--border-strong)',
          }}>Передумал</button>
        </div>
      </div>
    </FlowSheet>
  );
};

// ─── 7. Payment methods manager ────────────────────────────────
export const PaymentMethodsSheet = ({ onClose }) => {
  const [cards, setCards] = React.useState([
    { id: 'c1', brand: 'MIR',        last4: '4821', exp: '09/27', primary: true },
    { id: 'c2', brand: 'Mastercard', last4: '1043', exp: '03/26', primary: false },
  ]);
  const [adding, setAdding] = React.useState(false);
  return (
    <FlowSheet>
      <FlowHeader title="Способы оплаты" onClose={onClose} />
      <PullToRefresh
        scrollPaddingTop={0}
        onRefresh={() => new Promise(r => setTimeout(r, 700))}
      >
        <div style={{ padding: '0 16px 16px' }}>
          {cards.length === 0 ? (
            <div className="card" style={{ padding: '36px 24px', textAlign: 'center', marginTop: 8 }}>
              <div style={{
                width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
                background: 'var(--surface-2)', color: 'var(--text-3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name="card" size={28} color="currentColor" />
              </div>
              <div className="t-h3" style={{ fontSize: 16 }}>Ещё нет карт</div>
              <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
                Привяжи карту — спишем 1 ₽ для проверки и вернём.
              </div>
              <button onClick={() => setAdding(true)} className="btn btn-accent"
                      style={{ marginTop: 16, height: 44, padding: '0 22px' }}>
                Привязать карту
              </button>
            </div>
          ) : (
            <>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '8px 4px' }}>Карты</div>
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {cards.map((c, i) => (
                <React.Fragment key={c.id}>
                  {i > 0 && <Divider3 />}
                  <SwipeRow
                    actionLabel="Удалить"
                    actionIcon="trash"
                    revealPx={100}
                    onAction={() => setCards(cs => cs.filter(x => x.id !== c.id))}
                  >
                  <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, background: 'var(--surface)' }}>
                    <div style={{
                      width: 44, height: 30, borderRadius: 6,
                      background: c.brand === 'MIR' ? '#0a0a0a' : '#1f2937',
                      color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                      border: '0.5px solid rgba(255,255,255,0.08)',
                    }}>{c.brand === 'MIR' ? 'МИР' : 'MC'}</div>
                    <div style={{ flex: 1 }}>
                      <div className="t-h3" style={{ fontSize: 14 }}>•••• {c.last4}</div>
                      <div className="t-small" style={{ color: 'var(--text-3)' }}>До {c.exp}</div>
                    </div>
                    {c.primary && (
                      <span className="chip chip-accent" style={{ height: 22, fontSize: 11, padding: '0 8px' }}>
                        основная
                      </span>
                    )}
                  </div>
                  </SwipeRow>
                </React.Fragment>
              ))}
              <Divider3 />
              <button onClick={() => setAdding(true)} className="press" style={{
                width: '100%', padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12,
                background: 'transparent', border: 0, cursor: 'pointer', color: 'var(--text)',
                fontFamily: 'inherit',
              }}>
                <div style={{
                  width: 44, height: 30, borderRadius: 6, background: 'var(--surface-2)',
                  border: '1px dashed var(--border-strong)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon name="plus" size={16} color="var(--text-2)" strokeWidth={2.4} />
                </div>
                <span className="t-h3" style={{ fontSize: 14 }}>Привязать карту</span>
              </button>
            </div>
            </>
          )}

        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '18px 4px 8px' }}>Быстрая оплата</div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {[
            { id: 'apple', t: 'Apple Pay', s: 'Touch ID · 1 касание', on: true },
            { id: 'sbp', t: 'СБП',       s: 'Оплата через банк', on: false },
            { id: 'gpay', t: 'Google Pay', s: 'Недоступно на iPhone', on: false, disabled: true },
          ].map((m, i, a) => <PayToggleRow key={m.id} {...m} last={i === a.length - 1} />)}
        </div>

        <div className="t-small" style={{ color: 'var(--text-3)', padding: '16px 4px', textAlign: 'center' }}>
          Данные карт хранятся у платёжного провайдера. Клуб видит только последние 4 цифры.
        </div>

          {/* Demo: clear-all button so reviewers can see empty state */}
          {cards.length > 0 && (
            <button onClick={() => setCards([])} style={{
              width: '100%', height: 38, marginTop: 4,
              border: 0, background: 'transparent', color: 'var(--text-3)',
              fontSize: 12, fontWeight: 500, fontFamily: 'inherit',
              cursor: 'pointer',
            }}>
              Очистить (для демо)
            </button>
          )}
        </div>
      </PullToRefresh>

      {adding && <AddCardSheet onClose={() => setAdding(false)}
                                onAdd={(card) => { setCards(cs => [...cs, card]); setAdding(false); }} />}
    </FlowSheet>
  );
};

function PayToggleRow({ t, s, on: initialOn, disabled, last }) {
  const [on, setOn] = React.useState(initialOn);
  return (
    <>
      <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, opacity: disabled ? 0.5 : 1 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8, background: 'var(--surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="card" size={18} color="var(--text-2)" />
        </div>
        <div style={{ flex: 1 }}>
          <div className="t-h3" style={{ fontSize: 14 }}>{t}</div>
          <div className="t-small" style={{ color: 'var(--text-3)' }}>{s}</div>
        </div>
        <button disabled={disabled} onClick={() => setOn(v => !v)} style={{
          width: 44, height: 26, borderRadius: 999, border: 0,
          background: on ? 'var(--accent)' : 'var(--border-strong)',
          position: 'relative', cursor: disabled ? 'default' : 'pointer',
          transition: 'background 0.2s', padding: 0,
        }}>
          <span style={{
            position: 'absolute', top: 2, left: on ? 20 : 2, width: 22, height: 22,
            borderRadius: 999, background: '#fff',
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)', transition: 'left 0.2s',
          }} />
        </button>
      </div>
      {!last && <Divider3 />}
    </>
  );
}

function AddCardSheet({ onClose, onAdd }) {
  const [num, setNum] = React.useState('');
  const [exp, setExp] = React.useState('');
  const [cvc, setCvc] = React.useState('');
  const ok = num.replace(/\s/g, '').length === 16 && /^\d{2}\/\d{2}$/.test(exp) && cvc.length === 3;
  const fmtNum = (s) => s.replace(/\D/g, '').slice(0, 16).replace(/(.{4})/g, '$1 ').trim();
  const fmtExp = (s) => {
    const d = s.replace(/\D/g, '').slice(0, 4);
    return d.length > 2 ? d.slice(0, 2) + '/' + d.slice(2) : d;
  };
  return (
    <FlowSheet>
      <FlowHeader title="Новая карта" onClose={onClose} />
      <div className="scroller" style={{ padding: '0 16px 16px' }}>
        {/* Mock card visual */}
        <div style={{
          height: 200, borderRadius: 22, padding: 20, marginTop: 8, marginBottom: 18,
          background: 'linear-gradient(135deg, #1c1917 0%, #292524 60%, #44403c 100%)',
          color: '#fff', display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          boxShadow: 'var(--sh-2)',
        }}>
          <div className="row-between">
            <div className="t-mini" style={{ color: 'rgba(255,255,255,0.6)' }}>Карта</div>
            <div style={{
              width: 36, height: 26, borderRadius: 5,
              background: 'linear-gradient(135deg, rgba(250,204,21,0.8), rgba(217,119,6,0.9))',
            }} />
          </div>
          <div style={{
            fontSize: 22, letterSpacing: 2, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          }}>
            {num || '0000 0000 0000 0000'}
          </div>
          <div className="row-between">
            <div className="t-mini" style={{ color: 'rgba(255,255,255,0.6)' }}>{exp || 'MM / YY'}</div>
            <div className="t-mini" style={{ color: 'rgba(255,255,255,0.6)' }}>CVC</div>
          </div>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <FormRow label="Номер" value={num} onChange={(v) => setNum(fmtNum(v))} type="tel" placeholder="0000 0000 0000 0000" />
          <Divider3 />
          <div style={{ display: 'flex' }}>
            <div style={{ flex: 1 }}>
              <FormRow label="Срок" value={exp} onChange={(v) => setExp(fmtExp(v))} type="tel" placeholder="MM/YY" />
            </div>
            <div style={{ width: 0.5, background: 'var(--border)' }} />
            <div style={{ flex: 1 }}>
              <FormRow label="CVC" value={cvc} onChange={(v) => setCvc(v.replace(/\D/g, '').slice(0, 3))} type="tel" placeholder="•••" />
            </div>
          </div>
        </div>

        <div style={{ height: 22 }} />
        <button disabled={!ok} onClick={() => onAdd?.({
          id: 'c' + Date.now(),
          brand: num.startsWith('2') ? 'MIR' : 'Mastercard',
          last4: num.replace(/\s/g, '').slice(-4),
          exp,
          primary: false,
        })} className="btn btn-accent" style={{ width: '100%', height: 52, opacity: ok ? 1 : 0.5 }}>
          Привязать карту
        </button>
        <div className="t-small" style={{
          color: 'var(--text-3)', textAlign: 'center', marginTop: 10,
        }}>
          Спишем 1 ₽ для проверки и вернём
        </div>
      </div>
    </FlowSheet>
  );
}

// ─── 8. Post-training review ──────────────────────────────────
export const ReviewSheet = ({ training, onClose, onSubmit }) => {
  const tr = training || { date: '29 апр, Ср', trainer: 'Аня Соколова', kind: 'Ноги + спина', initials: 'АС', bg: '#fef3c7', color: '#a36a16' };
  const [rating, setRating] = React.useState(0);
  const [hover, setHover] = React.useState(0);
  const [tags, setTags] = React.useState(new Set());
  const [text, setText] = React.useState('');
  const TAGS = ['Понятно объясняет', 'Внимательная', 'Чёткий план', 'В тонусе', 'Удобный темп', 'Хорошо подбадривает'];
  const toggle = (t) => setTags(s => { const n = new Set(s); n.has(t) ? n.delete(t) : n.add(t); return n; });
  return (
    <FlowSheet>
      <FlowHeader title="Оценка тренировки" onClose={onClose} />
      <div className="scroller" style={{ padding: '4px 16px 16px' }}>
        {/* Header */}
        <div className="card" style={{ padding: 16, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 14 }}>
          <Avatar initials={tr.initials} bg={tr.bg} color={tr.color} size={52} />
          <div>
            <div className="t-h3">{tr.trainer}</div>
            <div className="t-small">{tr.kind} · {tr.date}</div>
          </div>
        </div>

        {/* Star rating */}
        <div style={{ padding: '20px 0', textAlign: 'center' }}>
          <div className="t-h2" style={{ marginBottom: 14 }}>
            {rating === 0 ? 'Как прошло?' :
             rating <= 2 ? 'Жаль, что не зашло' :
             rating === 3 ? 'Нормально' :
             rating === 4 ? 'Хорошо!' : 'Огонь!'}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                onMouseEnter={() => setHover(n)}
                onMouseLeave={() => setHover(0)}
                onClick={() => setRating(n)}
                className="press"
                style={{
                  border: 0, background: 'transparent', cursor: 'pointer', padding: 4,
                  transform: rating === n ? 'scale(1.1)' : 'scale(1)',
                  transition: 'transform 0.2s',
                }}
              >
                <Icon name={(hover || rating) >= n ? 'starFill' : 'star'} size={38}
                      color={(hover || rating) >= n ? '#fbbf24' : 'var(--text-3)'} strokeWidth={1.6} />
              </button>
            ))}
          </div>
        </div>

        {/* Tags — appear after rating */}
        {rating > 0 && (
          <div className="fade-up" style={{ marginBottom: 14 }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 10px' }}>
              {rating >= 4 ? 'Что понравилось' : 'Что не зашло'}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {TAGS.map(t => (
                <button key={t} onClick={() => toggle(t)} className="press"
                        style={{
                          padding: '8px 14px', borderRadius: 999, fontSize: 13, fontWeight: 500,
                          border: `1px solid ${tags.has(t) ? 'var(--accent)' : 'var(--border-strong)'}`,
                          background: tags.has(t) ? 'var(--accent-soft)' : 'var(--surface)',
                          color: tags.has(t) ? 'var(--accent-deep)' : 'var(--text-2)',
                          cursor: 'pointer', fontFamily: 'inherit',
                        }}>{t}</button>
              ))}
            </div>
          </div>
        )}

        {/* Comment */}
        {rating > 0 && (
          <div className="fade-up card" style={{ padding: '12px 14px', marginBottom: 14, animationDelay: '0.08s' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', marginBottom: 6 }}>
              Комментарий (видит только тренер)
            </div>
            <textarea
              value={text} onChange={e => setText(e.target.value)}
              placeholder="Расскажи, как ощущения"
              rows={3}
              style={{
                width: '100%', resize: 'none', border: 0, outline: 0,
                fontSize: 15, color: 'var(--text)', fontFamily: 'inherit',
                background: 'transparent', padding: 0,
              }} />
          </div>
        )}

        <button disabled={rating === 0}
                onClick={() => onSubmit?.({ rating, tags: [...tags], text })}
                className="btn btn-accent"
                style={{ width: '100%', height: 52, opacity: rating ? 1 : 0.5 }}>
          {rating === 0 ? 'Поставь оценку' : 'Отправить'}
        </button>
      </div>
    </FlowSheet>
  );
};

// ─── 9. Trainer cancelled — pick new slot ─────────────────────
export const TrainerCancelledSheet = ({ onClose, onReschedule, onChat }) => {
  const slots = [
    { id: 's1', d: 'Завтра, Чт', t: '18:00', extra: '+ скидка 30 %', recommended: true },
    { id: 's2', d: 'Пт, 2 мая', t: '08:00', extra: 'утренний слот' },
    { id: 's3', d: 'Пт, 2 мая', t: '19:30' },
    { id: 's4', d: 'Сб, 3 мая', t: '11:00' },
  ];
  const [picked, setPicked] = React.useState('s1');
  return (
    <FlowSheet>
      <FlowHeader title="Что делаем?" onClose={onClose} />
      <div className="scroller" style={{ padding: '4px 16px 16px' }}>
        {/* Hero */}
        <div className="card" style={{ padding: 16, marginBottom: 14,
                                       background: 'var(--danger-soft)', border: 0 }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 12, background: 'var(--danger)', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <Icon name="alert" size={20} color="currentColor" strokeWidth={2} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="t-h3" style={{ color: 'var(--danger)' }}>Аня заболела</div>
              <div className="t-small" style={{ marginTop: 4, color: 'var(--text-2)' }}>
                Тренировка сегодня в 18:00 отменена.<br />
                Деньги уже вернулись на карту •••• 4821.
              </div>
            </div>
          </div>
        </div>

        <div className="t-mini" style={{ padding: '4px 4px 10px', color: 'var(--text-3)' }}>
          Перенести с Аней
        </div>
        <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 14 }}>
          {slots.map((s, i, a) => (
            <React.Fragment key={s.id}>
              <button onClick={() => setPicked(s.id)} className="press"
                      style={{
                        width: '100%', padding: '14px 16px', background: 'transparent', border: 0,
                        cursor: 'pointer', textAlign: 'left', color: 'var(--text)', fontFamily: 'inherit',
                        display: 'flex', alignItems: 'center', gap: 12,
                      }}>
                <div style={{
                  width: 22, height: 22, borderRadius: 999,
                  border: `1.5px solid ${picked === s.id ? 'var(--accent)' : 'var(--text-3)'}`,
                  background: picked === s.id ? 'var(--accent)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {picked === s.id && <Icon name="check" size={12} color="#06120c" strokeWidth={3} />}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="t-h3" style={{ fontSize: 15 }}>{s.d} · {s.t}</div>
                  {s.extra && (
                    <div className="t-small" style={{
                      marginTop: 2,
                      color: s.recommended ? 'var(--accent-deep)' : 'var(--text-3)',
                    }}>{s.extra}</div>
                  )}
                </div>
                {s.recommended && (
                  <span className="chip chip-accent" style={{ height: 22, fontSize: 11, padding: '0 8px' }}>
                    извинения
                  </span>
                )}
              </button>
              {i < a.length - 1 && <Divider3 />}
            </React.Fragment>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button onClick={() => onReschedule?.(slots.find(x => x.id === picked))}
                  className="btn btn-accent" style={{ width: '100%', height: 52 }}>
            Перенести
          </button>
          <button onClick={onChat} className="btn" style={{
            width: '100%', height: 48, background: 'transparent', color: 'var(--text-2)',
            border: '0.5px solid var(--border-strong)',
          }}>
            Найти другого тренера
          </button>
        </div>
      </div>
    </FlowSheet>
  );
};

// ─── 10. Chat attachment bottom sheet ─────────────────────────
export const ChatAttachSheet = ({ onClose, onPick }) => {
  const options = [
    { id: 'photo',  t: 'Фото',           s: 'Из галереи',          icon: 'image' },
    { id: 'camera', t: 'Камера',         s: 'Сделать снимок',      icon: 'image' },
    { id: 'file',   t: 'Файл',           s: 'PDF, doc, до 10 МБ',  icon: 'paperclip' },
    { id: 'voice',  t: 'Голосовое',      s: 'Удерживай для записи',icon: 'phone' },
  ];
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0, zIndex: 250,
        background: 'rgba(0,0,0,0.35)', animation: 'ctx-fade 0.2s ease-out',
      }} onClick={onClose} />
      <div style={{
        position: 'absolute', left: 12, right: 12, bottom: 12, zIndex: 251,
        background: 'var(--surface)', borderRadius: 20, padding: 12,
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        animation: 'sheet-up 0.28s cubic-bezier(0.32, 0.72, 0.2, 1)',
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {options.map(o => (
            <button key={o.id} onClick={() => { onPick?.(o.id); onClose(); }} className="press"
                    style={{
                      padding: '16px 14px', background: 'var(--surface-2)', border: 0, borderRadius: 14,
                      display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8,
                      cursor: 'pointer', color: 'var(--text)', fontFamily: 'inherit', textAlign: 'left',
                    }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, background: 'var(--accent-soft)',
                color: 'var(--accent-deep)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={o.icon} size={20} color="currentColor" />
              </div>
              <div>
                <div className="t-h3" style={{ fontSize: 14 }}>{o.t}</div>
                <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 1 }}>{o.s}</div>
              </div>
            </button>
          ))}
        </div>
        <button onClick={onClose} className="btn" style={{
          width: '100%', height: 48, marginTop: 10,
          background: 'transparent', color: 'var(--text-2)', border: '0.5px solid var(--border-strong)',
        }}>Отмена</button>
      </div>
    </>
  );
};

