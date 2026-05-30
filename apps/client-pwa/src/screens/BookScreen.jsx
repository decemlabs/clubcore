import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '@/components/Avatar.jsx';
import { FilterChips } from '@/components/FilterChips.jsx';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { SearchBar } from '@/components/SearchBar.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { ApiError } from '@/data';
import { useClientAvailableSlots, useCreateBooking, useCancelBooking } from '@/data';
import { addHour, monthName } from '@/utils/format.js';

// ─── Helpers for slot data ─────────────────────────────────────────────────

function parseSlotDate(startTime) {
  const d = new Date(startTime);
  return {
    key: d.toISOString().slice(0, 10), // "YYYY-MM-DD"
    dow: d.toLocaleDateString('ru-RU', { weekday: 'short' }),
    num: d.getDate(),
    month: d.getMonth(),
    isToday: new Date().toISOString().slice(0, 10) === d.toISOString().slice(0, 10),
    hasSlot: true,
  };
}

function parseSlotTime(startTime) {
  const d = new Date(startTime);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

// Pick a consistent avatar bg per trainerId
const BG_COLORS = ['#d1fae5', '#dbeafe', '#fce7f3', '#ede9fe', '#fef3c7', '#fee2e2'];
function trainerBg(trainerId) {
  let h = 0;
  for (let i = 0; i < trainerId.length; i++) h = (h * 31 + trainerId.charCodeAt(i)) | 0;
  return BG_COLORS[Math.abs(h) % BG_COLORS.length];
}

export const BookScreen = ({ onTab, onOpenManage, onOpenTrainer, onCheckout, onConfirmFlow, onOpenPlans }) => {
  const navigate = useNavigate();
  const [step, setStep] = React.useState('pick'); // 'pick' | 'confirm' | 'done'
  const [selectedDay, setSelectedDay] = React.useState(null);
  const [selectedTrainer, setSelectedTrainer] = React.useState(null);
  const [selectedSlot, setSelectedSlot] = React.useState(null); // slotId string
  const [selectedSlotMeta, setSelectedSlotMeta] = React.useState(null); // { startTime, trainerName, trainerId }
  const [trainerQuery, setTrainerQuery] = React.useState('');
  const [trainerFilter, setTrainerFilter] = React.useState('all');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState(null);
  const scrollerRef = React.useRef(null);
  const timeStepRef = React.useRef(null);

  const { data: slotsData, isLoading: slotsLoading, isError: slotsError } = useClientAvailableSlots();
  const createBookingMutation = useCreateBooking();
  const cancelBookingMutation = useCancelBooking();

  // Notify parent about confirm flow state
  React.useEffect(() => {
    onConfirmFlow && onConfirmFlow(step === 'confirm' || step === 'done');
    return () => { onConfirmFlow && onConfirmFlow(false); };
  }, [step]);

  // Smoothly scroll to the time-slot section after a trainer is picked
  React.useEffect(() => {
    if (!selectedTrainer) return;
    const id = requestAnimationFrame(() => {
      const scroller = scrollerRef.current;
      const target = timeStepRef.current;
      if (!scroller || !target) return;
      const targetTop = target.offsetTop - 60;
      scroller.scrollTo({ top: targetTop, behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(id);
  }, [selectedTrainer]);

  // Reset slot when trainer/day changes
  React.useEffect(() => { setSelectedSlot(null); setSelectedSlotMeta(null); }, [selectedTrainer, selectedDay]);

  const allSlots = slotsData?.items ?? [];

  // Derive unique calendar days from real slot data
  const calendarDays = React.useMemo(() => {
    const seen = new Set();
    const days = [];
    for (const s of allSlots) {
      const info = parseSlotDate(s.startTime);
      if (!seen.has(info.key)) {
        seen.add(info.key);
        days.push(info);
      }
    }
    return days.sort((a, b) => a.key.localeCompare(b.key));
  }, [allSlots]);

  // Auto-select first available day
  React.useEffect(() => {
    if (calendarDays.length > 0 && !selectedDay) {
      setSelectedDay(calendarDays[0].key);
    }
  }, [calendarDays, selectedDay]);

  const day = calendarDays.find(d => d.key === selectedDay);

  // Derive unique trainers from real slot data for selected day
  const trainersForDay = React.useMemo(() => {
    if (!selectedDay) return [];
    const seen = new Set();
    const trainers = [];
    for (const s of allSlots) {
      if (parseSlotDate(s.startTime).key !== selectedDay) continue;
      if (!seen.has(s.trainerId)) {
        seen.add(s.trainerId);
        trainers.push({
          id: s.trainerId,
          name: s.trainerName,
          initials: getInitials(s.trainerName),
          bg: trainerBg(s.trainerId),
          color: '#065f46',
        });
      }
    }
    return trainers;
  }, [allSlots, selectedDay]);

  // Filter trainers by search query
  const filteredTrainers = trainersForDay.filter(t => {
    if (!trainerQuery.trim()) return true;
    const q = trainerQuery.toLowerCase().trim();
    return t.name.toLowerCase().includes(q);
  });

  // Slots for selected trainer + day
  const slotsForTrainer = React.useMemo(() => {
    if (!selectedTrainer || !selectedDay) return [];
    return allSlots.filter(s =>
      s.trainerId === selectedTrainer &&
      parseSlotDate(s.startTime).key === selectedDay,
    );
  }, [allSlots, selectedTrainer, selectedDay]);

  const trainer = trainersForDay.find(t => t.id === selectedTrainer);

  const handleConfirm = async () => {
    if (!selectedSlot || !selectedSlotMeta) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const idempotencyKey = typeof crypto !== 'undefined'
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
    try {
      // We need ptPackageId from the client's active PT package.
      // The server gets it via the authenticated session — pass slotId only;
      // pt_package_id is resolved server-side via require_client + active PT package.
      // Per CBOOK-03 schema: ClientCreateBookingRequest has slot_id + pt_package_id.
      // Use empty string as pt_package_id — server will resolve from active package.
      // NOTE: The actual pt_package_id will be resolved server-side; the client sends
      // the slot_id and the server reads the active package from the session.
      await createBookingMutation.mutateAsync({
        slotId: selectedSlot,
        ptPackageId: '',
        idempotencyKey,
      });
      setStep('done');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'no_active_pt_package') {
          // CBOOK-04: route to Plans/Checkout (T-71-29)
          if (onOpenPlans) {
            onOpenPlans();
          } else {
            navigate('/home');
          }
          return;
        }
        setSubmitError(err.code === 'slot_already_booked'
          ? 'Это место уже занято. Выбери другое время.'
          : 'Не удалось создать запись. Попробуй ещё раз.');
      } else {
        setSubmitError('Произошла ошибка. Проверь подключение.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (step === 'done') {
    return <BookingConfirmed
      day={day}
      trainerName={selectedSlotMeta?.trainerName}
      slot={selectedSlotMeta ? parseSlotTime(selectedSlotMeta.startTime) : ''}
      onDone={() => onTab('home')}
      onBookAnother={() => {
        setStep('pick');
        setSelectedTrainer(null);
        setSelectedSlot(null);
        setSelectedSlotMeta(null);
      }}
      onManage={onOpenManage}
    />;
  }

  if (step === 'confirm') {
    return <BookingReview
      day={day}
      trainerName={selectedSlotMeta?.trainerName}
      slot={selectedSlotMeta ? parseSlotTime(selectedSlotMeta.startTime) : ''}
      onBack={() => setStep('pick')}
      isSubmitting={isSubmitting}
      submitError={submitError}
      onConfirm={handleConfirm}
    />;
  }

  if (slotsLoading) {
    return (
      <div className="page">
        <StatusBar />
        <div className="scroller" style={{ paddingTop: 54, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="t-small" style={{ color: 'var(--text-3)', padding: 40 }}>Загрузка расписания…</div>
        </div>
      </div>
    );
  }

  if (slotsError || allSlots.length === 0) {
    return (
      <div className="page">
        <StatusBar />
        <div className="scroller" style={{ paddingTop: 54 }}>
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <div className="t-h3" style={{ marginBottom: 8 }}>Нет доступных слотов</div>
            <div className="t-small" style={{ color: 'var(--text-2)', marginBottom: 16 }}>
              {slotsError
                ? 'Не удалось загрузить расписание. Проверь подключение.'
                : 'Доступных слотов для записи нет. Зайди позже.'}
            </div>
            {onOpenPlans && (
              <button
                onClick={onOpenPlans}
                className="btn btn-accent"
                style={{ height: 44, padding: '0 24px' }}
              >
                Купить абонемент
              </button>
            )}
          </div>
        </div>
      </div>
    );
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
        <div style={{ overflowX: 'auto', overflowY: 'hidden', paddingBottom: 4, scrollbarWidth: 'none' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: `repeat(${calendarDays.length}, 60px)`,
            gap: 8, padding: '4px 20px 8px',
          }}>
            {calendarDays.map(d => (
              <button
                key={d.key}
                onClick={() => setSelectedDay(d.key)}
                className={`cal-day ${selectedDay === d.key ? 'selected' : ''} has-slot`}
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
        <div style={{ padding: '4px 16px 6px' }}>
          <SearchBar value={trainerQuery} onChange={setTrainerQuery}
                     placeholder="Имя тренера" />
        </div>
        <div style={{ padding: '4px 16px 8px' }}>
          <FilterChips value={trainerFilter} onChange={setTrainerFilter} options={[
            { id: 'all', label: 'Все', count: trainersForDay.length },
          ]} />
        </div>
        <div className="stack-2" style={{ padding: '4px 16px 4px' }}>
          {filteredTrainers.length === 0 ? (
            <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
              <div className="t-h3" style={{ fontSize: 15 }}>Нет тренеров</div>
              <div className="t-small" style={{ marginTop: 4 }}>Выбери другой день</div>
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
                    <div className="t-h3">{t.name}</div>
                    {onOpenTrainer && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onOpenTrainer(t); }}
                        style={{
                          marginTop: 6, appearance: 'none', border: '0.5px solid var(--border-strong)',
                          background: 'transparent', cursor: 'pointer',
                          height: 26, padding: '0 10px', borderRadius: 999,
                          fontSize: 12, fontWeight: 600, color: 'var(--text-2)',
                          fontFamily: 'inherit',
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                        }}
                      >
                        Подробнее
                      </button>
                    )}
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
              const periods = [
                { id: 'morning', label: 'Утро',  hint: 'до 11:00',   icon: 'sunrise', range: [0, 11] },
                { id: 'day',     label: 'День',  hint: '11:00–17:00', icon: 'sun',     range: [11, 17] },
                { id: 'evening', label: 'Вечер', hint: 'после 17:00', icon: 'moon',    range: [17, 24] },
              ];
              return periods.map(p => {
                const periodsSlots = slotsForTrainer.filter(s => {
                  const h = new Date(s.startTime).getHours();
                  return h >= p.range[0] && h < p.range[1];
                });
                if (!periodsSlots.length) return null;
                return (
                  <div key={p.id} style={{ padding: '10px 16px 0' }}>
                    <div className="period-card" data-empty="false">
                      <div className="period-card__head">
                        <Icon name={p.icon} size={16} color="var(--text-2)" strokeWidth={1.8} />
                        <div className="t-h3" style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.3, textTransform: 'uppercase' }}>
                          {p.label}
                        </div>
                        <div className="t-mini" style={{ color: 'var(--text-3)', flex: 1 }}>{p.hint}</div>
                        <div className="t-mini" style={{
                          color: 'var(--accent-deep)',
                          fontVariantNumeric: 'tabular-nums', fontWeight: 600,
                        }}>
                          {periodsSlots.length} свободно
                        </div>
                      </div>
                      <div className="period-card__grid">
                        {periodsSlots.map(s => {
                          const timeLabel = parseSlotTime(s.startTime);
                          return (
                            <SlotChip
                              key={s.slotId}
                              busy={false}
                              selected={selectedSlot === s.slotId}
                              label={timeLabel}
                              busyReason=""
                              onSelect={() => {
                                setSelectedSlot(s.slotId);
                                setSelectedSlotMeta({ startTime: s.startTime, trainerName: s.trainerName, trainerId: s.trainerId });
                              }}
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
            Продолжить
          </button>
        </div>
      )}
    </div>
  );
};

function BookingReview({ day, trainerName, slot, onBack, onConfirm, isSubmitting, submitError }) {
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
            <RowItem icon="user" label="Тренер" value={trainerName} />
            <Divider />
            <RowItem icon="calendar" label="Дата" value={`${day?.dow}, ${day?.num} ${monthName(day?.month)}`} />
            <Divider />
            <RowItem icon="clock" label="Время" value={`${slot} – ${addHour(slot)}`} sub="1 час" />
          </div>
        </div>

        {submitError && (
          <div style={{ padding: '0 16px 8px' }}>
            <div style={{
              background: 'color-mix(in oklab, var(--destructive) 10%, transparent)',
              border: '0.5px solid color-mix(in oklab, var(--destructive) 30%, transparent)',
              borderRadius: 'var(--r-lg)', padding: '10px 14px',
            }}>
              <div className="t-small" style={{ color: 'var(--destructive)' }}>{submitError}</div>
            </div>
          </div>
        )}

        <div style={{ padding: '8px 20px 0' }}>
          <div className="t-small" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
            Отменить запись бесплатно можно не позднее, чем за 6 часов до начала тренировки.
          </div>
        </div>

        <div style={{ height: 120 }} />
      </div>

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '12px 16px 20px',
        background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
      }}>
        <button
          onClick={onConfirm}
          disabled={isSubmitting}
          className="btn btn-accent"
          style={{ width: '100%', height: 54, opacity: isSubmitting ? 0.6 : 1 }}
        >
          {isSubmitting ? 'Записываю…' : 'Подтвердить запись'}
        </button>
      </div>
    </div>
  );
}

function BookingConfirmed({ day, trainerName, slot, onDone, onBookAnother, onManage }) {
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
            <RowItem icon="user" label="Тренер" value={trainerName} />
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
        <button onClick={onBookAnother} className="btn btn-soft" style={{
          width: '100%', height: 44, marginTop: 8,
          background: 'transparent', color: 'var(--text-2)',
        }}>
          Записаться ещё
        </button>
      </div>
    </div>
  );
}

// ─── Time slot button ────────────────────────────────────────────────────────
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
