import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { FilterChips } from '@/components/FilterChips.jsx';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { SearchBar } from '@/components/SearchBar.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { BUSY_SLOTS, CALENDAR, TIME_SLOTS, TRAINERS } from '@/data';
import { addHour, monthName } from '@/utils/format.js';

export const BookScreen = ({ onTab, onOpenManage, onOpenTrainer, onCheckout, onConfirmFlow }) => {
  const [step, setStep] = React.useState('pick'); // 'pick' | 'confirm' | 'done'
  React.useEffect(() => {
    onConfirmFlow && onConfirmFlow(step === 'confirm' || step === 'done');
    return () => { onConfirmFlow && onConfirmFlow(false); };
  }, [step]);
  const [selectedDay, setSelectedDay] = React.useState(CALENDAR[1].key);
  const [selectedTrainer, setSelectedTrainer] = React.useState(null);
  const [selectedSlot, setSelectedSlot] = React.useState(null);
  const scrollerRef = React.useRef(null);
  const timeStepRef = React.useRef(null);

  // Smoothly scroll to the time-slot section after a trainer is picked
  React.useEffect(() => {
    if (!selectedTrainer) return;
    // Wait a frame for the Step 3 block to mount
    const id = requestAnimationFrame(() => {
      const scroller = scrollerRef.current;
      const target = timeStepRef.current;
      if (!scroller || !target) return;
      const targetTop = target.offsetTop - 60; // leave breathing room
      scroller.scrollTo({ top: targetTop, behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(id);
  }, [selectedTrainer]);

  const day = CALENDAR.find(d => d.key === selectedDay);
  const trainer = TRAINERS.find(t => t.id === selectedTrainer);

  // Trainer search + spec filter
  const [trainerQuery, setTrainerQuery] = React.useState('');
  const [trainerFilter, setTrainerFilter] = React.useState('all');
  const filteredTrainers = TRAINERS.filter(t => {
    const q = trainerQuery.toLowerCase().trim();
    const matchQ = !q || t.name.toLowerCase().includes(q) || t.spec.toLowerCase().includes(q);
    let matchF = true;
    if (trainerFilter === 'top')   matchF = t.rating >= 4.9;
    if (trainerFilter === 'cheap') matchF = t.price <= 2200;
    return matchQ && matchF;
  });

  // Reset slot when trainer changes
  React.useEffect(() => { setSelectedSlot(null); }, [selectedTrainer, selectedDay]);

  if (step === 'done') {
    return <BookingConfirmed
      day={day} trainer={trainer} slot={selectedSlot}
      onDone={() => onTab('home')}
      onBookAnother={() => { setStep('pick'); setSelectedTrainer(null); setSelectedSlot(null); }}
      onManage={onOpenManage}
    />;
  }

  if (step === 'confirm') {
    return <BookingReview
      day={day} trainer={trainer} slot={selectedSlot}
      onBack={() => setStep('pick')}
      onConfirm={() => {
        if (onCheckout) {
          onCheckout({
            kind: 'training',
            title: `Тренировка с ${trainer.name.split(' ')[0]}`,
            subtitle: `${day.dow}, ${day.num} · ${selectedSlot} · 1 час`,
            amount: trainer.price,
          });
          // Optimistic — move to done after the checkout sheet appears
          setTimeout(() => setStep('done'), 1700);
        } else {
          setStep('done');
        }
      }}
    />;
  }

  return (
    <div className="page">
      <StatusBar />
      <div className="scroller" ref={scrollerRef} style={{ paddingTop: 54 }}>
        <div style={{ padding: '8px 20px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Запись</div>
          <div className="t-h1" style={{ marginTop: 4 }}>На индивидуальную тренировку</div>
        </div>

        {/* Step 1: Date */}
        <div style={{ padding: '12px 20px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
            <span style={{ color: 'var(--text-3)', marginRight: 8 }}>1</span>
            Когда удобно
          </div>
        </div>
        <div style={{ overflowX: 'auto', overflowY: 'hidden', paddingBottom: 4, scrollbarWidth: 'none' }}
             onScroll={e => e.preventDefault}>
          <div style={{
            display: 'grid', gridTemplateColumns: `repeat(${CALENDAR.length}, 60px)`,
            gap: 8, padding: '4px 20px 8px',
          }}>
            {CALENDAR.map(d => (
              <button
                key={d.key}
                onClick={() => d.hasSlot && setSelectedDay(d.key)}
                disabled={!d.hasSlot}
                className={`cal-day ${selectedDay === d.key ? 'selected' : ''} ${d.hasSlot ? 'has-slot' : 'disabled'}`}
              >
                <span className="dow">{d.isToday ? 'Сег' : d.dow}</span>
                <span className="num">{d.num}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Trainer */}
        <div style={{ padding: '20px 20px 8px' }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
            <span style={{ color: 'var(--text-3)', marginRight: 8 }}>2</span>
            Свободные тренеры
          </div>
        </div>
        {/* Search + filter */}
        <div style={{ padding: '4px 16px 6px' }}>
          <SearchBar value={trainerQuery} onChange={setTrainerQuery}
                     placeholder="Имя или специализация" />
        </div>
        <div style={{ padding: '4px 16px 8px' }}>
          <FilterChips value={trainerFilter} onChange={setTrainerFilter} options={[
            { id: 'all',   label: 'Все',          count: TRAINERS.length },
            { id: 'top',   label: '★ Топ',        count: TRAINERS.filter(t => t.rating >= 4.9).length },
            { id: 'cheap', label: 'До 2200 ₽',    count: TRAINERS.filter(t => t.price <= 2200).length },
          ]} />
        </div>
        <div className="stack-2" style={{ padding: '4px 16px 4px' }}>
          {filteredTrainers.length === 0 ? (
            <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
              <div style={{
                width: 48, height: 48, borderRadius: 999, margin: '0 auto 12px',
                background: 'var(--surface-2)', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="22" height="22" viewBox="0 0 24 24">
                  <circle cx="11" cy="11" r="7" stroke="var(--text-3)" strokeWidth="1.8" fill="none" />
                  <path d="M16 16l4 4" stroke="var(--text-3)" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </div>
              <div className="t-h3" style={{ fontSize: 15 }}>Никто не подошёл</div>
              <div className="t-small" style={{ marginTop: 4 }}>
                Попробуй другой запрос или сними фильтр.
              </div>
              <button onClick={() => { setTrainerQuery(''); setTrainerFilter('all'); }}
                      className="press"
                      style={{
                        marginTop: 14, padding: '8px 16px', fontSize: 13, fontWeight: 600,
                        border: '0.5px solid var(--border-strong)', background: 'transparent',
                        color: 'var(--text)', borderRadius: 999, cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}>Сбросить</button>
            </div>
          ) : filteredTrainers.map(t => {
            const isSel = selectedTrainer === t.id;
            return (
              <div
                key={t.id}
                onClick={() => setSelectedTrainer(t.id)}
                className="press"
                style={{
                  border: 0, padding: 0, cursor: 'pointer',
                  background: 'var(--surface)', borderRadius: 'var(--r-lg)',
                  textAlign: 'left',
                  outline: isSel ? '2px solid var(--text)' : '0.5px solid var(--border)',
                  outlineOffset: isSel ? -2 : 0,
                }}
              >
                <div style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
                  <Avatar initials={t.initials} bg={t.bg} color={t.color} size={48} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="row-between">
                      <div className="t-h3">{t.name}</div>
                      <div className="row" style={{ gap: 3 }}>
                        <Icon name="starFill" size={14} color="#f59e0b" />
                        <span className="t-small" style={{ color: 'var(--text)', fontWeight: 600 }}>{t.rating}</span>
                      </div>
                    </div>
                    <div className="t-small" style={{ marginTop: 2 }}>{t.spec}</div>
                    <div className="row-between" style={{ marginTop: 8, gap: 8 }}>
                      <div className="row" style={{ gap: 8 }}>
                        <span className="chip" style={{ height: 22, fontSize: 11.5, padding: '0 9px' }}>{t.exp}</span>
                        <span className="t-small" style={{ color: 'var(--text-2)', fontWeight: 600 }}>
                          {t.price.toLocaleString('ru-RU')} ₽
                        </span>
                      </div>
                      {onOpenTrainer && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onOpenTrainer(t); }}
                          style={{
                            appearance: 'none', border: '0.5px solid var(--border-strong)',
                            background: 'transparent', cursor: 'pointer',
                            height: 26, padding: '0 10px', borderRadius: 999,
                            fontSize: 12, fontWeight: 600, color: 'var(--text-2)',
                            fontFamily: 'inherit',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          Подробнее
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Step 3: Time */}
        {selectedTrainer && (
          <div className="fade-up" ref={timeStepRef}>
            <div style={{ padding: '20px 20px 8px' }}>
              <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
                <span style={{ color: 'var(--text-3)', marginRight: 8 }}>3</span>
                Свободное время
              </div>
              <div className="t-small" style={{ marginTop: 2 }}>
                {trainer?.name.split(' ')[0]} · {day?.dow}, {day?.num} {monthName(day?.month)}
              </div>
            </div>

            {(() => {
              const busyList = BUSY_SLOTS[selectedTrainer] || [];
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
                const freeCount = slots.filter(s => !busyList.includes(s)).length;
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
                          const busy = busyList.includes(s);
                          return (
                            <SlotChip
                              key={s}
                              busy={busy}
                              selected={selectedSlot === s}
                              label={s}
                              busyReason={busyReason(selectedTrainer, s)}
                              onSelect={() => setSelectedSlot(s)}
                            />
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

        <div style={{ height: 100 }} />
      </div>

      {/* Sticky CTA */}
      {selectedSlot && (
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 0,
          padding: '12px 16px 20px',
          background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
          zIndex: 10,
        }}>
          <button
            className="btn btn-accent fade-up"
            style={{ width: '100%', height: 54 }}
            onClick={() => setStep('confirm')}
          >
            Продолжить · {trainer?.price.toLocaleString('ru-RU')} ₽
          </button>
        </div>
      )}
    </div>
  );
};

function BookingReview({ day, trainer, slot, onBack, onConfirm }) {
  return (
    <div className="page">
      <StatusBar />
      <div style={{ padding: '54px 16px 0' }}>
        <button onClick={onBack} style={{
          width: 40, height: 40, borderRadius: 999, border: '0.5px solid var(--border-strong)',
          background: 'var(--surface)', cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="chevronLeft" size={20} />
        </button>
      </div>
      <div className="scroller">
        <div style={{ padding: '20px 20px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Подтверждение</div>
          <div className="t-h1" style={{ marginTop: 4 }}>Проверь детали</div>
        </div>

        <div style={{ padding: '12px 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RowItem icon="user" label="Тренер" value={trainer?.name} sub={trainer?.spec}
                     avatar={<Avatar initials={trainer?.initials} bg={trainer?.bg} color={trainer?.color} size={36} />} />
            <Divider />
            <RowItem icon="calendar" label="Дата" value={`${day?.dow}, ${day?.num} ${monthName(day?.month)}`} />
            <Divider />
            <RowItem icon="clock" label="Время" value={`${slot} – ${addHour(slot)}`} sub="1 час" />
            <Divider />
            <RowItem icon="card" label="К оплате" value={`${trainer?.price.toLocaleString('ru-RU')} ₽`}
                     sub="спишется с привязанной карты" />
          </div>
        </div>

        <div style={{ padding: '8px 20px 0' }}>
          <div className="t-small" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
            Отменить запись бесплатно можно не позднее, чем за 6 часов до начала тренировки.
            Позже — спишется 50% стоимости.
          </div>
        </div>

        <div style={{ height: 120 }} />
      </div>

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '12px 16px 20px',
        background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
      }}>
        <button onClick={onConfirm} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Подтвердить запись
        </button>
      </div>
    </div>
  );
}

function BookingConfirmed({ day, trainer, slot, onDone, onBookAnother, onManage }) {
  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      <div className="scroller" style={{ paddingTop: 64 }}>
        <div style={{ padding: '20px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="scale-in haptic" style={{
            width: 76, height: 76, borderRadius: 999, background: 'var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 24px var(--accent-soft)',
          }}>
            <Icon name="check" size={40} color="#06120c" strokeWidth={2.5} />
          </div>
          <div className="t-display" style={{ marginTop: 24, textAlign: 'center', letterSpacing: -0.8 }}>
            Записан!
          </div>
          <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 6, textAlign: 'center', maxWidth: 280 }}>
            Напомним за час и за 15 минут до тренировки.
          </div>
        </div>

        <div style={{ padding: '28px 16px 12px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RowItem
              avatar={<Avatar initials={trainer?.initials} bg={trainer?.bg} color={trainer?.color} size={36} />}
              label="Тренер" value={trainer?.name} sub={trainer?.spec}
            />
            <Divider />
            <RowItem icon="calendar" label="Когда"
                     value={`${day?.dow}, ${day?.num} ${monthName(day?.month)}, ${slot}`}
                     sub="1 час" />
          </div>
        </div>

        <div style={{ padding: '8px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button className="btn btn-ghost" style={{ height: 48 }}>В календарь</button>
          <button onClick={onManage} className="btn btn-ghost" style={{ height: 48 }}>Управлять записью</button>
        </div>

        <div style={{ height: 120 }} />
      </div>

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '12px 16px 20px',
        background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
      }}>
        <button onClick={onDone} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Готово
        </button>
        <button onClick={onBookAnother} className="btn btn-soft" style={{ width: '100%', height: 44, marginTop: 8, background: 'transparent', color: 'var(--text-2)' }}>
          Записаться ещё
        </button>
      </div>
    </div>
  );
}

function RowItem_local() { /* moved to components.jsx — see components.jsx for shared RowItem/Divider/monthName/addHour */ }

// ─── Time slot button: shake + tooltip when tapping a busy slot ───
const BUSY_REASONS = {
  // trainer t1
  t1: { '09:00': 'утренняя группа', '13:00': 'персоналка с другим клиентом', '18:00': 'свободное окно недоступно' },
  t2: { '10:00': 'кроссфит-сбор', '15:00': 'тренировка',          '19:00': 'занят'                          },
  t3: { '08:00': 'йога-класс',     '11:30': 'персоналка',         '20:30': 'класс по стретчингу'             },
  t4: { '16:30': 'спарринг',       '19:00': 'групповая'                                                       },
  t5: { '09:00': 'класс пилатеса', '13:00': 'персоналка'                                                       },
  t6: { '11:30': 'тренировка',     '18:00': 'занят',              '20:30': 'персоналка'                       },
};
function busyReason(trainerId, slot) {
  return (BUSY_REASONS[trainerId] && BUSY_REASONS[trainerId][slot]) || 'занято';
}

function SlotChip({ busy, selected, label, busyReason, onSelect }) {
  const [shake, setShake] = React.useState(false);
  const [tip, setTip] = React.useState(false);

  const handleClick = () => {
    if (busy) {
      setShake(true); setTip(true);
      setTimeout(() => setShake(false), 420);
      setTimeout(() => setTip(false), 1800);
      return;
    }
    onSelect();
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={handleClick}
        className={`slot-chip ${selected ? 'selected' : ''} ${busy ? 'busy' : ''} ${shake ? 'shake' : ''}`}
        aria-disabled={busy}
      >
        {label}
      </button>
      {tip && (
        <div className="slot-tip" role="tooltip">
          {busyReason}
          <span className="slot-tip-arrow" />
        </div>
      )}
    </div>
  );
}
const SlotButton = SlotChip;

