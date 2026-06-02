import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { BUSY_SLOTS, CALENDAR, TIME_SLOTS, UPCOMING_BOOKING, useCancelBooking } from '@/data';
import { monthName } from '@/utils/format.js';

export const BookingManageSheet = ({ booking, onClose, onCancelled, onRescheduled, onChat, onRules }) => {
  const [view, setView] = React.useState('overview'); // overview | cancel | reschedule | done-cancel | done-reschedule
  const [newDay, setNewDay] = React.useState(null);
  const [newSlot, setNewSlot] = React.useState(null);
  const [cancelError, setCancelError] = React.useState(null);
  const cancelMutation = useCancelBooking();

  const b = booking || UPCOMING_BOOKING;
  const freeCancel = b.hoursTo >= 6;
  const refundPct = freeCancel ? 100 : 50;
  const refundAmount = Math.round(b.price * refundPct / 100);

  // ─── Done states ─────────────────────────────────────
  if (view === 'done-cancel') {
    return (
      <DoneState
        icon="close"
        accentBg="var(--danger-soft)"
        accentColor="var(--danger)"
        title="Запись отменена"
        body={refundPct === 100
          ? 'Деньги вернутся на карту в течение 1–3 рабочих дней.'
          : `Возврат ${refundAmount.toLocaleString('ru-RU')} ₽ (50%) — отмена позже чем за 6 часов.`}
        onClose={() => { onCancelled && onCancelled(); onClose(); }}
      />
    );
  }
  if (view === 'done-reschedule') {
    const day = CALENDAR.find(d => d.key === newDay);
    return (
      <DoneState
        icon="check"
        accentBg="var(--accent-soft)"
        accentColor="var(--accent-deep)"
        title="Перенесли"
        body={`Новое время: ${day?.dow}, ${day?.num} ${monthName(day?.month)} в ${newSlot}.`}
        onClose={() => { onRescheduled && onRescheduled({ day: newDay, slot: newSlot }); onClose(); }}
      />
    );
  }

  // ─── Cancel confirm ──────────────────────────────────
  if (view === 'cancel') {
    return (
      <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <StatusBar />
        <ManageTopBar title="Отмена" onBack={() => setView('overview')} />

        <div className="scroller" style={{ paddingTop: 0 }}>
          <div style={{ padding: '8px 20px 16px' }}>
            <div className="t-h1" style={{ marginTop: 4 }}>Точно отменить?</div>
            <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 8 }}>
              {freeCancel
                ? 'До тренировки больше 6 часов — отмена бесплатная, вернём всю сумму.'
                : 'До тренировки осталось меньше 6 часов. По правилам спишется 50% — вернётся половина.'}
            </div>
          </div>

          <div style={{ padding: '4px 16px 0' }}>
            <div className="card" style={{ padding: 4 }}>
              <RowItem icon="user" label="Тренер" value={b.trainer} sub={b.focus}
                       avatar={<Avatar initials={b.trainerInitials} bg={b.trainerBg} color={b.trainerColor} size={36} />} />
              <Divider />
              <RowItem icon="calendar" label="Когда"
                       value={`${b.date}, ${b.time}`} sub={`${b.duration} мин`} />
              <Divider />
              <RowItem
                icon="card"
                label="Возврат"
                value={`${refundAmount.toLocaleString('ru-RU')} ₽`}
                sub={`${refundPct}% от ${b.price.toLocaleString('ru-RU')} ₽ · на карту •••• 4821`}
                accent={freeCancel}
              />
            </div>
          </div>

          {!freeCancel && (
            <div style={{ padding: '12px 24px 0' }}>
              <div style={{
                padding: 14, background: 'var(--warn-soft)', borderRadius: 12,
                display: 'flex', gap: 10, alignItems: 'flex-start',
              }}>
                <Icon name="info" size={18} color="#a36a16" />
                <div className="t-small" style={{ color: 'var(--text)', lineHeight: 1.5 }}>
                  Если перенесёшь, а не отменишь — без штрафа. Тренер тоже не будет ждать зря.
                </div>
              </div>
            </div>
          )}

          <div style={{ height: 140 }} />
        </div>

        {cancelError && (
          <div
            aria-live="polite"
            aria-atomic="true"
            style={{
              position: 'absolute', left: 16, right: 16, bottom: 102,
              zIndex: 10,
              background: 'var(--danger-soft)',
              color: 'var(--danger)',
              border: '1px solid var(--danger)',
              borderRadius: 14,
              padding: '11px 13px',
              display: 'flex', alignItems: 'center', gap: 11,
              boxShadow: '0 8px 24px rgba(28, 25, 23, 0.12)',
            }}
          >
            <span style={{
              width: 26, height: 26, borderRadius: 7, flexShrink: 0,
              background: 'var(--danger)', color: '#fff',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6}
                   strokeLinecap="round" strokeLinejoin="round" style={{ width: 15, height: 15 }}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </span>
            <span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 650, lineHeight: 1.25 }}>
              {cancelError}
            </span>
          </div>
        )}

        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 0,
          padding: '12px 16px 20px',
          background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          {!freeCancel && (
            <button
              onClick={() => setView('reschedule')}
              className="btn btn-ghost"
              style={{ width: '100%', height: 50 }}
            >
              Лучше перенесу
            </button>
          )}
          <button
            disabled={cancelMutation.isPending}
            onClick={async () => {
              setCancelError(null);
              try {
                await cancelMutation.mutateAsync({ bookingId: b.id });
                setView('done-cancel');
              } catch (err) {
                const code = err && typeof err === 'object' && 'code' in err ? err.code : null;
                if (code === 'cancel_window_expired') {
                  setCancelError('Окно отмены истекло — обратитесь на ресепшн');
                } else {
                  setCancelError('Не удалось отменить запись. Попробуйте ещё раз.');
                }
              }
            }}
            className="btn"
            style={{
              width: '100%', height: 54,
              background: 'var(--danger)', color: '#fff',
              opacity: cancelMutation.isPending ? 0.7 : 1,
            }}
          >
            {cancelMutation.isPending ? 'Отмена…' : 'Отменить запись'}
          </button>
        </div>
      </div>
    );
  }

  // ─── Reschedule ──────────────────────────────────────
  if (view === 'reschedule') {
    const day = newDay ? CALENDAR.find(d => d.key === newDay) : null;
    const trainerKey = 't1'; // Аня in mock
    const busy = BUSY_SLOTS[trainerKey] || [];

    return (
      <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <StatusBar />
        <ManageTopBar title="Перенос" onBack={() => setView('overview')} />

        <div className="scroller" style={{ paddingTop: 0 }}>
          <div style={{ padding: '8px 20px 8px' }}>
            <div className="t-h1" style={{ marginTop: 4 }}>Когда удобнее?</div>
            <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
              Текущее: {b.date}, {b.time} · {b.trainer}
            </div>
          </div>

          {/* Date strip */}
          <div style={{ padding: '8px 20px 4px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>1 · Дата</div>
          </div>
          <div style={{ overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: `repeat(${CALENDAR.length}, 60px)`,
              gap: 8, padding: '4px 20px 8px',
            }}>
              {CALENDAR.slice(1).map(d => (
                <button
                  key={d.key}
                  onClick={() => { if (d.hasSlot) { setNewDay(d.key); setNewSlot(null); } }}
                  disabled={!d.hasSlot}
                  className={`cal-day ${newDay === d.key ? 'selected' : ''} ${d.hasSlot ? 'has-slot' : 'disabled'}`}
                >
                  <span className="dow">{d.dow}</span>
                  <span className="num">{d.num}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Time grid */}
          {newDay && (
            <div className="fade-up">
              <div style={{ padding: '14px 20px 4px' }}>
                <div className="t-mini" style={{ color: 'var(--text-3)' }}>2 · Время</div>
                <div className="t-small" style={{ marginTop: 4 }}>
                  {day?.dow}, {day?.num} {monthName(day?.month)} · {b.trainer}
                </div>
              </div>
              {(() => {
                const periods = [
                  { id: 'morning', label: 'Утро',  hint: 'до 11:00',   icon: 'sunrise', range: [0, 11] },
                  { id: 'day',     label: 'День',  hint: '11:00–17:00', icon: 'sun',     range: [11, 17] },
                  { id: 'evening', label: 'Вечер', hint: 'после 17:00', icon: 'moon',    range: [17, 24] },
                ];
                return periods.map(p => {
                  const slots = TIME_SLOTS.filter(s => {
                    const h = parseInt(s.split(':')[0], 10);
                    return h >= p.range[0] && h < p.range[1];
                  });
                  if (!slots.length) return null;
                  const freeCount = slots.filter(s => !busy.includes(s)).length;
                  const allBusy = freeCount === 0;
                  return (
                    <div key={p.id} style={{ padding: '10px 16px 0' }}>
                      <div className="period-card" data-empty={allBusy ? 'true' : 'false'}>
                        <div className="period-card__head">
                          <Icon name={p.icon} size={16} color="var(--text-2)" strokeWidth={1.8} />
                          <div className="t-h3" style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.3, textTransform: 'uppercase' }}>
                            {p.label}
                          </div>
                          <div className="t-mini" style={{ color: 'var(--text-3)', flex: 1 }}>{p.hint}</div>
                          <div className="t-mini" style={{
                            color: allBusy ? 'var(--text-3)' : 'var(--accent-deep)',
                            fontVariantNumeric: 'tabular-nums', fontWeight: 600,
                          }}>
                            {freeCount} свободно
                          </div>
                        </div>
                        <div className="period-card__grid">
                          {slots.map(s => {
                            const isBusy = busy.includes(s);
                            return (
                              <div key={s}>
                                <button
                                  disabled={isBusy}
                                  onClick={() => !isBusy && setNewSlot(s)}
                                  className={`slot-chip ${newSlot === s ? 'selected' : ''} ${isBusy ? 'busy' : ''}`}
                                >
                                  {s}
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          )}

          <div style={{ padding: '12px 24px 0' }}>
            <div className="t-small" style={{ color: 'var(--text-3)', lineHeight: 1.5, fontSize: 12 }}>
              Перенос — без доплат и штрафов. Тренер получит уведомление автоматически.
            </div>
          </div>

          <div style={{ height: 140 }} />
        </div>

        {newSlot && (
          <div style={{
            position: 'absolute', left: 0, right: 0, bottom: 0,
            padding: '12px 16px 20px',
            background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
          }}>
            <button
              onClick={() => setView('done-reschedule')}
              className="btn btn-accent fade-up"
              style={{ width: '100%', height: 54 }}
            >
              Перенести на {day?.num} {monthName(day?.month)}, {newSlot}
            </button>
          </div>
        )}
      </div>
    );
  }

  // ─── Overview ────────────────────────────────────────
  return (
    <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ManageTopBar title="Запись" onClose={onClose} />

      <div className="scroller" style={{ paddingTop: 0 }}>
        <div style={{ padding: '8px 20px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>{b.date}, {b.time}</div>
          <div className="t-display" style={{ marginTop: 4, letterSpacing: -0.8 }}>
            {b.focus}
          </div>
          <div className="row" style={{ marginTop: 10, gap: 10 }}>
            <Avatar initials={b.trainerInitials} bg={b.trainerBg} color={b.trainerColor} size={32} />
            <div>
              <div className="t-h3" style={{ fontSize: 14 }}>{b.trainer}</div>
              <div className="t-small">Личный тренер</div>
            </div>
          </div>
        </div>

        {/* Countdown / window */}
        <div style={{ padding: '0 16px 16px' }}>
          <div className={`card`} style={{
            padding: 16,
            borderColor: freeCancel ? 'var(--border)' : 'rgba(233,162,59,0.4)',
            background: freeCancel ? 'var(--surface)' : 'var(--warn-soft)',
          }}>
            <div className="row" style={{ gap: 12, alignItems: 'center' }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: freeCancel ? 'var(--accent-soft)' : 'rgba(233,162,59,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name="clock" size={22}
                      color={freeCancel ? 'var(--accent-deep)' : '#a36a16'}
                      strokeWidth={2} />
              </div>
              <div style={{ flex: 1 }}>
                <div className="t-h3" style={{ fontSize: 14 }}>
                  {freeCancel
                    ? `Бесплатная отмена ещё ${b.hoursTo - 6} ч`
                    : `До тренировки ${b.hoursTo} ч`}
                </div>
                <div className="t-small" style={{ marginTop: 2 }}>
                  {freeCancel
                    ? 'Отменить или перенести можно без штрафа'
                    : 'Отмена — −50% штраф. Перенос — без штрафа.'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="stack-2" style={{ padding: '0 16px' }}>
          <ActionRow
            icon="calendar"
            title="Перенести"
            sub="Бесплатно · выбрать новое время"
            onClick={() => setView('reschedule')}
          />
          <ActionRow
            icon="chat"
            title="Написать тренеру"
            sub="Спросить про разминку или перенос"
            onClick={onChat}
          />
          <ActionRow
            icon="info"
            title="Правила отмены"
            sub="За 6 ч — бесплатно, позже — 50%"
            onClick={onRules}
          />
          <ActionRow
            icon="close"
            title="Отменить запись"
            sub={freeCancel ? 'Полный возврат на карту' : `Вернётся ${refundAmount.toLocaleString('ru-RU')} ₽ из ${b.price.toLocaleString('ru-RU')} ₽`}
            danger
            onClick={() => setView('cancel')}
          />
        </div>

        <div style={{ height: 32 }} />
      </div>
    </div>
  );
};

function ActionRow({ icon, title, sub, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      className="press card"
      style={{
        appearance: 'none', textAlign: 'left', cursor: 'pointer',
        padding: '14px 14px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: 'var(--text)',
      }}
    >
      <div style={{
        width: 38, height: 38, borderRadius: 10,
        background: danger ? 'var(--danger-soft)' : 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={icon} size={20}
              color={danger ? 'var(--danger)' : 'var(--text-2)'}
              strokeWidth={2} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{
          fontSize: 15,
          color: danger ? 'var(--danger)' : 'var(--text)',
        }}>{title}</div>
        <div className="t-small" style={{ marginTop: 2 }}>{sub}</div>
      </div>
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </button>
  );
}

function DoneState({ icon, accentBg, accentColor, title, body, onClose }) {
  return (
    <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', padding: '0 32px',
      }}>
        <div className="scale-in haptic" style={{
          width: 84, height: 84, borderRadius: 999, background: accentBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={42} color={accentColor} strokeWidth={2.4} />
        </div>
        <div className="t-display" style={{ marginTop: 24, textAlign: 'center', letterSpacing: -0.8 }}>
          {title}
        </div>
        <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 10, textAlign: 'center', maxWidth: 300 }}>
          {body}
        </div>
      </div>
      <div style={{ padding: '12px 16px 20px' }}>
        <button onClick={onClose} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Готово
        </button>
      </div>
    </div>
  );
}

function ManageTopBar({ title, onClose, onBack }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '54px 12px 8px',
    }}>
      <button onClick={onBack || onClose} style={{
        width: 40, height: 40, borderRadius: 999, border: '0.5px solid var(--border)',
        background: 'var(--surface)', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name={onBack ? 'chevronLeft' : 'close'} size={18} color="var(--text)" strokeWidth={2.2} />
      </button>
      <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)' }}>{title}</div>
      <div style={{ width: 40 }} />
    </div>
  );
}

