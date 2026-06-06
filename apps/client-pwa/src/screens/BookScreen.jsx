import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '@/components/Icon.jsx';
import { LoadError } from '@/components/LoadError.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { SearchBar } from '@/components/SearchBar.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { ApiError, useClientAvailableSlots, useCreateBooking } from '@/data';
import { monthName } from '@/utils/format.js';

/* ============================================================================
   Экран «Запись» — дизайн из макета (quick 260606-toj), интегрированный поверх
   реального API (quick 260606-u22). Гибрид:
     • Реальные данные/действия: /client/slots → дни/тренеры/слоты, /client/booking.
     • Декор поверх реального trainerId: рейтинг ★, стаж, цена, специализация,
       цвет аватара, переключатель длительности 30/60/90 + цены. Бронь игнорирует
       длительность (слот фиксированной длины) и не списывает деньги при записи —
       оплата идёт из PT-пакета (422 no_active_pt_package → экран «Планы»).
   Рамка/таб-бар/фейковый статус-бар убраны — экран живёт в app-shell (.page +
   StatusBar + .scroller), таб-бар рисует оболочка. Глобальные классы дизайн-системы
   (.card/.press/.cal-day/.period-card/.slot-chip/.chip/.ava/.btn/.fade-up/.toast)
   переиспользуются; инлайн — только специфика макета (book-summary, CTA, декор-чипы).
   ============================================================================ */

// ─── MSK helpers (WR-04: bucket by Europe/Moscow, not browser-local) ───────────
const MSK_PARTS = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Europe/Moscow',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false,
});

function mskParts(startTime) {
  const parts = MSK_PARTS.formatToParts(new Date(startTime));
  const get = (type) => parts.find((p) => p.type === type)?.value ?? '';
  const rawHour = get('hour');
  const hour = rawHour === '24' ? '00' : rawHour;
  return { year: get('year'), month: get('month'), day: get('day'), hour: Number(hour), minute: get('minute') };
}

function parseSlotDate(startTime) {
  const d = new Date(startTime);
  const p = mskParts(startTime);
  const key = `${p.year}-${p.month}-${p.day}`;
  const todayKey = (() => { const t = mskParts(Date.now()); return `${t.year}-${t.month}-${t.day}`; })();
  return {
    key,
    dow: d.toLocaleDateString('ru-RU', { weekday: 'short', timeZone: 'Europe/Moscow' }),
    num: Number(p.day),
    month: Number(p.month) - 1,
    isToday: key === todayKey,
  };
}

function parseSlotTime(startTime) {
  const p = mskParts(startTime);
  return `${String(p.hour).padStart(2, '0')}:${p.minute}`;
}

const addMinutes = (time, mins) => {
  const [h, m] = time.split(':').map(Number);
  const total = (h * 60 + m + mins) % (24 * 60);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

const fmt = (n) => n.toLocaleString('ru-RU');
const round50 = (n) => Math.round(n / 50) * 50;
const monthNm = (m) => ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'][m] || '';

// ─── Decor (deterministic per trainerId — stable across renders) ───────────────
const SPEC_POOL = ['Силовые, функционал', 'Кроссфит, выносливость', 'Йога, стретчинг', 'Бокс, ММА', 'Пилатес, осанка', 'Бодибилдинг'];
const EXP_POOL = ['4 года', '5 лет', '7 лет', '8 лет', '9 лет', '11 лет'];
const RATING_POOL = [4.7, 4.8, 4.9, 5.0];
const PRICE_POOL = [2000, 2100, 2200, 2400, 2500, 2800];
const COLOR_POOL = [
  { bg: '#fef3c7', color: '#f59e0b' }, { bg: '#dbeafe', color: '#0ea5e9' },
  { bg: '#f3e8ff', color: '#a855f7' }, { bg: '#fee2e2', color: '#dc2626' },
  { bg: '#d1fae5', color: '#10b981' }, { bg: '#e0e7ff', color: '#6366f1' },
];

function hashStr(s) {
  const str = String(s ?? '');
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function decorFor(trainerId) {
  const h = hashStr(trainerId);
  const c = COLOR_POOL[h % COLOR_POOL.length];
  return {
    spec: SPEC_POOL[h % SPEC_POOL.length],
    exp: EXP_POOL[(h >> 2) % EXP_POOL.length],
    rating: RATING_POOL[(h >> 4) % RATING_POOL.length],
    price: PRICE_POOL[(h >> 3) % PRICE_POOL.length],
    bg: c.bg,
    color: c.color,
  };
}

const DURATIONS = [
  { id: 30, label: '30 мин', short: '30 мин', mult: 0.6 },
  { id: 60, label: '1 час', short: '1 час', mult: 1 },
  { id: 90, label: '1,5 часа', short: '1,5 часа', mult: 1.45 },
];

// ─── Period (morning/day/evening) icons — inlined; not in app Icon set ─────────
const PERIOD_ICON = {
  sunrise: '<path d="M12 3v4M5.5 8.5l1.4 1.4M18.5 8.5l-1.4 1.4M3 17h18M7 17a5 5 0 0110 0M2 21h20"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
  moon: '<path d="M21 13A9 9 0 1111 3a7 7 0 0010 10z"/>',
};
function PeriodIco({ name }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="var(--text-2)"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
         dangerouslySetInnerHTML={{ __html: PERIOD_ICON[name] || '' }} />
  );
}

function Avatar({ initials, bg, color, size }) {
  const fs = Math.round(size * 0.38);
  return (
    <span className="ava" style={{ width: size, height: size, background: bg, color, fontSize: fs }}>
      {initials}
    </span>
  );
}

const PERIODS = [
  { id: 'morning', label: 'Утро', hint: 'до 11:00', icon: 'sunrise', range: [0, 11] },
  { id: 'day', label: 'День', hint: '11:00–17:00', icon: 'sun', range: [11, 17] },
  { id: 'evening', label: 'Вечер', hint: 'после 17:00', icon: 'moon', range: [17, 24] },
];

export const BookScreen = ({ onTab, onOpenManage, onOpenTrainer, onCheckout, onConfirmFlow, onOpenPlans }) => {
  void onCheckout;
  const navigate = useNavigate();
  const [step, setStep] = React.useState('pick'); // 'pick' | 'confirm' | 'done'
  const [selectedDay, setSelectedDay] = React.useState(null);
  const [selectedTrainer, setSelectedTrainer] = React.useState(null);
  const [selectedSlot, setSelectedSlot] = React.useState(null); // slotId
  const [selectedSlotMeta, setSelectedSlotMeta] = React.useState(null); // { startTime, trainerName, trainerId }
  const [duration, setDuration] = React.useState(60); // decor
  const [trainerQuery, setTrainerQuery] = React.useState('');
  const [trainerFilter, setTrainerFilter] = React.useState('all');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState(null);
  const [createdBooking, setCreatedBooking] = React.useState(null);

  const [toastMsg, setToastMsg] = React.useState('');
  const [toastShow, setToastShow] = React.useState(false);
  const toastTimer = React.useRef(null);

  const scrollerRef = React.useRef(null);
  const timeStepRef = React.useRef(null);

  const { data: slotsData, isLoading: slotsLoading, isError: slotsError, refetch: refetchSlots } = useClientAvailableSlots();
  const createBookingMutation = useCreateBooking();

  const toast = React.useCallback((msg) => {
    setToastMsg(msg);
    setToastShow(true);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastShow(false), 1700);
  }, []);

  React.useEffect(() => {
    onConfirmFlow && onConfirmFlow(step === 'confirm' || step === 'done');
    return () => { onConfirmFlow && onConfirmFlow(false); };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    if (!selectedTrainer) return;
    const id = requestAnimationFrame(() => {
      const sc = scrollerRef.current;
      const target = timeStepRef.current;
      if (sc && target) sc.scrollTo({ top: target.offsetTop - 60, behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(id);
  }, [selectedTrainer]);

  React.useEffect(() => { setSelectedSlot(null); setSelectedSlotMeta(null); }, [selectedTrainer, selectedDay]);

  const allSlots = slotsData?.items ?? [];

  const calendarDays = React.useMemo(() => {
    const seen = new Set();
    const days = [];
    for (const s of allSlots) {
      const info = parseSlotDate(s.startTime);
      if (!seen.has(info.key)) { seen.add(info.key); days.push(info); }
    }
    return days.sort((a, b) => a.key.localeCompare(b.key));
  }, [allSlots]);

  React.useEffect(() => {
    if (calendarDays.length > 0 && !selectedDay) setSelectedDay(calendarDays[0].key);
  }, [calendarDays, selectedDay]);

  const day = calendarDays.find((d) => d.key === selectedDay);

  const trainersForDay = React.useMemo(() => {
    if (!selectedDay) return [];
    const seen = new Set();
    const out = [];
    for (const s of allSlots) {
      if (parseSlotDate(s.startTime).key !== selectedDay) continue;
      if (!seen.has(s.trainerId)) {
        seen.add(s.trainerId);
        const dec = decorFor(s.trainerId);
        out.push({ id: s.trainerId, name: s.trainerName, initials: getInitials(s.trainerName), ...dec });
      }
    }
    return out;
  }, [allSlots, selectedDay]);

  const filterOpts = [
    { id: 'all', label: 'Все', count: trainersForDay.length },
    { id: 'top', label: '★ Топ', count: trainersForDay.filter((t) => t.rating >= 4.9).length },
    { id: 'cheap', label: 'До 2200 ₽', count: trainersForDay.filter((t) => t.price <= 2200).length },
  ];

  const filteredTrainers = trainersForDay.filter((t) => {
    const q = trainerQuery.toLowerCase().trim();
    const matchQ = !q || t.name.toLowerCase().includes(q) || t.spec.toLowerCase().includes(q);
    let matchF = true;
    if (trainerFilter === 'top') matchF = t.rating >= 4.9;
    if (trainerFilter === 'cheap') matchF = t.price <= 2200;
    return matchQ && matchF;
  });

  const slotsForTrainer = React.useMemo(() => {
    if (!selectedTrainer || !selectedDay) return [];
    return allSlots.filter((s) => s.trainerId === selectedTrainer && parseSlotDate(s.startTime).key === selectedDay);
  }, [allSlots, selectedTrainer, selectedDay]);

  const trainer = trainersForDay.find((t) => t.id === selectedTrainer) || null;
  const durObj = DURATIONS.find((d) => d.id === duration) || DURATIONS[1];
  const priceFor = (t) => (t ? round50(t.price * durObj.mult) : 0);

  // Nearest day (in calendar order) where this trainer has ≥1 free slot.
  const nearestAvailableDay = (trainerId, fromKey) => {
    const start = calendarDays.findIndex((d) => d.key === fromKey);
    for (let i = start + 1; i < calendarDays.length; i++) {
      const d = calendarDays[i];
      if (allSlots.some((s) => s.trainerId === trainerId && parseSlotDate(s.startTime).key === d.key)) return d;
    }
    for (let i = 0; i < start; i++) {
      const d = calendarDays[i];
      if (allSlots.some((s) => s.trainerId === trainerId && parseSlotDate(s.startTime).key === d.key)) return d;
    }
    return null;
  };

  const selectTrainer = (id) => { setSelectedTrainer(id); setSelectedSlot(null); setSelectedSlotMeta(null); };
  const jumpDay = (key) => { setSelectedDay(key); setSelectedSlot(null); setSelectedSlotMeta(null); };

  const handleConfirm = async () => {
    if (!selectedSlot || !selectedSlotMeta) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
    try {
      const created = await createBookingMutation.mutateAsync({ slotId: selectedSlot, idempotencyKey });
      setCreatedBooking(created);
      setStep('done');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'no_active_pt_package') {
          if (onOpenPlans) onOpenPlans(); else navigate('/home');
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

  // ─── Loading / error / empty ────────────────────────────────────────────────
  if (step === 'pick' && slotsLoading) {
    return (
      <div className="page">
        <StatusBar />
        <div className="scroller" style={{ paddingTop: 54, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="t-small" style={{ color: 'var(--text-3)', padding: 40 }}>Загрузка расписания…</div>
        </div>
      </div>
    );
  }

  if (step === 'pick' && slotsError) {
    return (
      <LoadError
        title="Не удалось загрузить расписание"
        subtitle="Проверьте подключение к интернету и попробуйте ещё раз."
        onRetry={() => refetchSlots()}
      />
    );
  }

  if (step === 'pick' && allSlots.length === 0) {
    return (
      <div className="page">
        <StatusBar />
        <div className="scroller" style={{ paddingTop: 54 }}>
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <div className="t-h3" style={{ marginBottom: 8 }}>Нет доступных слотов</div>
            <div className="t-small" style={{ color: 'var(--text-2)', marginBottom: 16 }}>
              Доступных слотов для записи нет. Зайди позже.
            </div>
            {onOpenPlans && (
              <button onClick={onOpenPlans} className="btn btn-accent" style={{ height: 44, padding: '0 24px' }}>
                Купить абонемент
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ─── REVIEW ───────────────────────────────────────────────────────────────
  if (step === 'confirm') {
    const slotLabel = selectedSlotMeta ? parseSlotTime(selectedSlotMeta.startTime) : '';
    return (
      <div className="page">
        <StatusBar />
        <div style={{ padding: '12px 16px 0' }}>
          <button
            onClick={() => setStep('pick')}
            style={{ width: 40, height: 40, borderRadius: 999, border: '0.5px solid var(--border-strong)', background: 'var(--surface)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
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
              <RowItem
                label="Тренер" value={trainer?.name} sub={trainer?.spec}
                avatar={trainer ? <Avatar initials={trainer.initials} bg={trainer.bg} color={trainer.color} size={36} /> : undefined}
              />
              <Divider />
              <RowItem icon="calendar" label="Дата" value={`${day?.dow}, ${day?.num} ${monthName(day?.month)}`} />
              <Divider />
              <RowItem icon="clock" label="Время" value={`${slotLabel} – ${addMinutes(slotLabel, duration)}`} sub={durObj.label} />
              <Divider />
              <RowItem icon="card" label="К оплате" value={`${fmt(priceFor(trainer))} ₽`} sub="спишется с привязанной карты" />
            </div>
          </div>
          {submitError && (
            <div style={{ padding: '0 16px 8px' }}>
              <div style={{ background: 'color-mix(in oklab, var(--destructive) 10%, transparent)', border: '0.5px solid color-mix(in oklab, var(--destructive) 30%, transparent)', borderRadius: 'var(--r-lg)', padding: '10px 14px' }}>
                <div className="t-small" style={{ color: 'var(--destructive)' }}>{submitError}</div>
              </div>
            </div>
          )}
          <div style={{ padding: '8px 20px 0' }}>
            <div className="t-small" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
              Отменить запись бесплатно можно не позднее, чем за 6 часов до начала тренировки. Позже — спишется 50% стоимости.
            </div>
          </div>
          <div style={{ height: 120 }} />
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '12px 16px 20px', background: 'linear-gradient(to top, var(--bg) 70%, transparent)' }}>
          <button onClick={handleConfirm} disabled={isSubmitting} className="btn btn-accent" style={{ width: '100%', height: 54, opacity: isSubmitting ? 0.6 : 1 }}>
            {isSubmitting ? 'Записываю…' : 'Подтвердить запись'}
          </button>
        </div>
      </div>
    );
  }

  // ─── DONE ───────────────────────────────────────────────────────────────────
  if (step === 'done') {
    const slotLabel = selectedSlotMeta ? parseSlotTime(selectedSlotMeta.startTime) : '';
    return (
      <div className="page" style={{ background: 'var(--bg)' }}>
        <StatusBar />
        <div className="scroller" style={{ paddingTop: 64 }}>
          <div style={{ padding: '20px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div className="scale-in" style={{ width: 76, height: 76, borderRadius: 999, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px var(--accent-soft)' }}>
              <Icon name="check" size={40} color="#06120c" strokeWidth={2.5} />
            </div>
            <div className="t-display" style={{ marginTop: 24, textAlign: 'center', letterSpacing: -0.8 }}>Записан!</div>
            <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 6, textAlign: 'center', maxWidth: 280 }}>
              Напомним за час и за 15 минут до тренировки.
            </div>
          </div>
          <div style={{ padding: '28px 16px 12px' }}>
            <div className="card" style={{ padding: 4 }}>
              <RowItem
                label="Тренер" value={trainer?.name || selectedSlotMeta?.trainerName} sub={trainer?.spec}
                avatar={trainer ? <Avatar initials={trainer.initials} bg={trainer.bg} color={trainer.color} size={36} /> : undefined}
              />
              <Divider />
              <RowItem icon="calendar" label="Когда" value={`${day?.dow}, ${day?.num} ${monthName(day?.month)}, ${slotLabel}`} sub={durObj.label} />
            </div>
          </div>
          <div style={{ padding: '8px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <button className="btn btn-ghost" onClick={() => toast('Добавлено в календарь')} style={{ height: 48 }}>В календарь</button>
            <button className="btn btn-ghost" onClick={() => onOpenManage && onOpenManage(createdBooking)} style={{ height: 48 }}>Управлять записью</button>
          </div>
          <div style={{ height: 120 }} />
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '12px 16px 20px', background: 'linear-gradient(to top, var(--bg) 70%, transparent)' }}>
          <button onClick={() => onTab('home')} className="btn btn-accent" style={{ width: '100%', height: 54 }}>Готово</button>
          <button
            onClick={() => { setStep('pick'); setSelectedTrainer(null); setSelectedSlot(null); setSelectedSlotMeta(null); }}
            className="btn btn-soft" style={{ width: '100%', height: 44, marginTop: 8, background: 'transparent', color: 'var(--text-2)' }}
          >
            Записаться ещё
          </button>
        </div>
        <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
      </div>
    );
  }

  // ─── PICK ─────────────────────────────────────────────────────────────────
  const busyList = []; // server returns only free slots — no busy chips
  const fullyBooked = !!selectedTrainer && slotsForTrainer.length === 0;
  const near = fullyBooked ? nearestAvailableDay(selectedTrainer, selectedDay) : null;

  return (
    <div className="page">
      <StatusBar />
      <div className="scroller no-sb" ref={scrollerRef} style={{ paddingTop: 54, paddingBottom: selectedSlot ? 150 : 100 }}>
        <div style={{ padding: '8px 20px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Запись</div>
          <div className="t-h1" style={{ marginTop: 4 }}>На индивидуальную тренировку</div>
        </div>

        {/* 1 · Date */}
        <div style={{ padding: '12px 20px 8px' }} className="row-between">
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
            <span style={{ color: 'var(--text-3)', marginRight: 8 }}>1</span>Когда удобно
          </div>
          {day && (
            <div className="t-mini" style={{ color: 'var(--text-3)', textTransform: 'none', letterSpacing: 0, fontWeight: 600, fontSize: 12 }}>
              {monthName(day.month)}
            </div>
          )}
        </div>
        <div className="no-sb" style={{ overflowX: 'auto', overflowY: 'hidden', paddingBottom: 4 }}>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${calendarDays.length}, 60px)`, gap: 8, padding: '4px 20px 8px' }}>
            {calendarDays.map((d) => (
              <button
                key={d.key}
                onClick={() => setSelectedDay(d.key)}
                className={`cal-day has-slot ${selectedDay === d.key ? 'selected' : ''}`}
              >
                <span className="dow">{d.isToday ? 'Сег' : d.dow}</span>
                <span className="num">{d.num}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 2 · Trainer */}
        <div style={{ padding: '20px 20px 8px' }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
            <span style={{ color: 'var(--text-3)', marginRight: 8 }}>2</span>Свободные тренеры
          </div>
        </div>
        <div style={{ padding: '4px 16px 6px' }}>
          <SearchBar value={trainerQuery} onChange={setTrainerQuery} placeholder="Имя или специализация" />
        </div>
        <div className="no-sb" style={{ padding: '4px 16px 8px', display: 'flex', gap: 8, overflowX: 'auto' }}>
          {filterOpts.map((o) => {
            const active = trainerFilter === o.id;
            return (
              <button
                key={o.id}
                className="press"
                onClick={() => setTrainerFilter(o.id)}
                style={{
                  flexShrink: 0, padding: '7px 13px', fontSize: 13, fontWeight: 500,
                  border: `0.5px solid ${active ? 'var(--text)' : 'var(--border-strong)'}`,
                  background: active ? 'var(--text)' : 'transparent',
                  color: active ? 'var(--bg)' : 'var(--text-2)',
                  borderRadius: 999, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'background .15s,color .15s',
                }}
              >
                {o.label}
                <span style={{ fontSize: 11, fontWeight: 600, background: active ? 'rgba(255,255,255,0.18)' : 'var(--surface-2)', color: active ? 'var(--bg)' : 'var(--text-3)', padding: '0 6px', height: 16, borderRadius: 999, lineHeight: '16px' }}>
                  {o.count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="stack-2" style={{ padding: '4px 16px 4px' }}>
          {filteredTrainers.length === 0 ? (
            <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
              <div className="t-h3" style={{ fontSize: 15 }}>Никто не подошёл</div>
              <div className="t-small" style={{ marginTop: 4 }}>Попробуй другой запрос или сними фильтр.</div>
              <button
                className="press"
                onClick={() => { setTrainerQuery(''); setTrainerFilter('all'); }}
                style={{ marginTop: 14, padding: '8px 16px', fontSize: 13, fontWeight: 600, border: '0.5px solid var(--border-strong)', background: 'transparent', color: 'var(--text)', borderRadius: 999, cursor: 'pointer' }}
              >
                Сбросить
              </button>
            </div>
          ) : (
            filteredTrainers.map((t) => {
              const isSel = selectedTrainer === t.id;
              return (
                <div
                  key={t.id}
                  className="press"
                  onClick={() => selectTrainer(t.id)}
                  style={{ cursor: 'pointer', background: 'var(--surface)', borderRadius: 'var(--r-lg)', outline: isSel ? '2px solid var(--text)' : '0.5px solid var(--border)', outlineOffset: isSel ? -2 : 0 }}
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
                          <span className="t-small" style={{ color: 'var(--text-2)', fontWeight: 600 }}>{fmt(t.price)} ₽</span>
                        </div>
                        {onOpenTrainer && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onOpenTrainer({ id: t.id, name: t.name, initials: t.initials, bg: t.bg, color: t.color }); }}
                            style={{ appearance: 'none', border: '0.5px solid var(--border-strong)', background: 'transparent', cursor: 'pointer', height: 26, padding: '0 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'inherit' }}
                          >
                            Подробнее
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* 3 · Duration + 4 · Time */}
        {trainer && (
          <div className="fade-up" ref={timeStepRef}>
            <div style={{ padding: '14px 16px 4px' }}>
              <div className="row-between" style={{ marginBottom: 8 }}>
                <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
                  <span style={{ color: 'var(--text-3)', marginRight: 8 }}>3</span>Длительность
                </div>
                <div className="t-small" style={{ fontSize: 12, color: 'var(--accent-deep)', fontWeight: 600 }}>{fmt(priceFor(trainer))} ₽</div>
              </div>
              <div style={{ display: 'flex', gap: 2, padding: 3, background: 'var(--surface-2)', border: '0.5px solid var(--border)', borderRadius: 999 }}>
                {DURATIONS.map((d) => {
                  const active = duration === d.id;
                  return (
                    <button
                      key={d.id}
                      onClick={() => setDuration(d.id)}
                      style={{
                        flex: 1, appearance: 'none', border: 0,
                        background: active ? 'var(--text)' : 'transparent',
                        color: active ? 'var(--bg)' : 'var(--text-2)',
                        height: 32, borderRadius: 999, fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
                        transition: 'background .15s,color .15s',
                        boxShadow: active ? '0 1px 4px rgba(0,0,0,0.18)' : 'none',
                      }}
                    >
                      {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={{ padding: '18px 20px 8px' }}>
              <div className="t-h3" style={{ fontSize: 15, color: 'var(--text-2)', fontWeight: 600 }}>
                <span style={{ color: 'var(--text-3)', marginRight: 8 }}>4</span>Свободное время
              </div>
              <div className="t-small" style={{ marginTop: 2 }}>
                {trainer.name.split(' ')[0]} · {day?.dow}, {day?.num} {monthNm(day?.month)}
              </div>
            </div>

            {fullyBooked ? (
              <div style={{ padding: '10px 16px 0' }}>
                <div className="card" style={{ padding: '24px 20px', textAlign: 'center' }}>
                  <div style={{ width: 48, height: 48, borderRadius: 999, margin: '0 auto 12px', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon name="calendar" size={22} color="var(--text-3)" strokeWidth={1.8} />
                  </div>
                  <div className="t-h3" style={{ fontSize: 15 }}>В этот день всё занято</div>
                  <div className="t-small" style={{ marginTop: 4 }}>
                    У {trainer.name.split(' ')[0]} на {day?.dow}, {day?.num} {monthNm(day?.month)} свободных окон нет.
                  </div>
                  {near ? (
                    <button
                      className="press"
                      onClick={() => jumpDay(near.key)}
                      style={{ marginTop: 16, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '10px 16px', fontSize: 13, fontWeight: 600, border: 0, background: 'var(--accent)', color: '#06120c', borderRadius: 999, cursor: 'pointer' }}
                    >
                      Ближайшее окно · {near.dow}, {near.num} {monthNm(near.month)} <Icon name="arrowRight" size={14} color="#06120c" strokeWidth={2} />
                    </button>
                  ) : (
                    <div className="t-small" style={{ marginTop: 14, color: 'var(--text-3)' }}>Свободных дней пока нет — попробуй другого тренера.</div>
                  )}
                </div>
              </div>
            ) : (
              PERIODS.map((p) => {
                const periodSlots = slotsForTrainer.filter((s) => { const h = mskParts(s.startTime).hour; return h >= p.range[0] && h < p.range[1]; });
                if (!periodSlots.length) return null;
                return (
                  <div key={p.id} style={{ padding: '10px 16px 0' }}>
                    <div className="period-card" data-empty="false">
                      <div className="period-card__head">
                        <PeriodIco name={p.icon} />
                        <div className="t-h3" style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.3px', textTransform: 'uppercase' }}>{p.label}</div>
                        <div className="t-mini" style={{ color: 'var(--text-3)', flex: 1, textTransform: 'none', letterSpacing: 0 }}>{p.hint}</div>
                        <div className="t-mini" style={{ color: 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums', fontWeight: 600, textTransform: 'none', letterSpacing: 0 }}>{periodSlots.length} свободно</div>
                      </div>
                      <div className="period-card__grid">
                        {periodSlots.map((s) => (
                          <SlotChip
                            key={s.slotId}
                            busy={busyList.includes(s.slotId)}
                            selected={selectedSlot === s.slotId}
                            label={parseSlotTime(s.startTime)}
                            onSelect={() => {
                              setSelectedSlot(s.slotId);
                              setSelectedSlotMeta({ startTime: s.startTime, trainerName: s.trainerName, trainerId: s.trainerId });
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Sticky CTA */}
      {selectedSlot && trainer && selectedSlotMeta && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '12px 16px 20px', background: 'linear-gradient(to top, var(--bg) 70%, transparent)', zIndex: 10 }}>
          <div className="fade-up" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: 'var(--surface)', border: '0.5px solid var(--border)', borderRadius: 16, boxShadow: 'var(--sh-2)' }}>
            <Avatar initials={trainer.initials} bg={trainer.bg} color={trainer.color} size={38} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t-h3" style={{ fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{trainer.name}</div>
              <div className="t-small" style={{ fontSize: 12, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                <span>{day?.dow}, {day?.num} {monthNm(day?.month)}</span>
                <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-3)', flexShrink: 0 }} />
                <span className="t-num">{parseSlotTime(selectedSlotMeta.startTime)}–{addMinutes(parseSlotTime(selectedSlotMeta.startTime), duration)}</span>
              </div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div className="t-num" style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.3px', color: 'var(--text)' }}>{fmt(priceFor(trainer))} ₽</div>
              <div className="t-small" style={{ fontSize: 11.5, marginTop: 1, color: 'var(--text-3)' }}>{durObj.short}</div>
            </div>
          </div>
          <button className="btn btn-accent fade-up" onClick={() => setStep('confirm')} style={{ width: '100%', height: 54, marginTop: 10 }}>
            Продолжить
          </button>
        </div>
      )}

      <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
    </div>
  );
};

// ─── Time slot button (busy/shake/tip kept for parity; never triggered — API
//     returns only free slots) ──────────────────────────────────────────────
function SlotChip({ busy, selected, label, onSelect }) {
  const [shake, setShake] = React.useState(false);
  const handleClick = () => {
    if (busy) { setShake(true); setTimeout(() => setShake(false), 420); return; }
    onSelect();
  };
  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={handleClick}
        aria-disabled={busy}
        className={`slot-chip ${selected ? 'selected' : ''} ${busy ? 'busy' : ''} ${shake ? 'shake' : ''}`}
      >
        {label}
      </button>
    </div>
  );
}
