import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';

const TRAINER_BIOS = {
  t1: 'Готовлю к первому марафону и помогаю наладить технику базы. Программы под текущий уровень, без перегруза.',
  t2: 'Кроссфит с прицелом на функциональную силу. Работаю с любителями и спортсменами на соревнования.',
  t3: 'Хатха и виньяса. Помогаю раскрыться телу без боли — много работы с дыханием и опорами.',
  t4: 'Постановка удара, спарринги, физуха. Готовлю к любительским турнирам — бокс и K-1.',
  t5: 'Пилатес для спины и осанки. Работаю с реабилитацией после травм и с беременными.',
  t6: 'Бодибилдинг и набор массы. План питания, тренировки в режиме "под план", разбор техники.',
};

const TRAINER_REVIEWS = [
  { id: 'r1', author: 'Маша К.', rating: 5, time: '2 нед назад', body: 'Очень внимательная, объясняет всё по шагам. После 2 месяцев — сдвиги по тяге заметные.' },
  { id: 'r2', author: 'Илья Б.', rating: 5, time: 'месяц назад', body: 'Чёткие программы, без воды. Подстраивается под усталость, не гонит на износ.' },
  { id: 'r3', author: 'Олег Д.', rating: 4, time: 'месяц назад', body: 'Хороший тренер. Иногда занятия чуть короче чем хочется, но в целом — рекомендую.' },
];

const TRAINER_NEAR_SLOTS = {
  t1: [{ d: 'Сегодня', t: '18:00' }, { d: 'Завтра', t: '08:00' }, { d: 'Завтра', t: '19:00' }, { d: 'Сб', t: '10:00' }],
  t2: [{ d: 'Завтра', t: '09:00' }, { d: 'Чт', t: '18:00' }, { d: 'Пт', t: '07:30' }],
  t3: [{ d: 'Сегодня', t: '20:30' }, { d: 'Завтра', t: '08:30' }, { d: 'Ср', t: '19:00' }, { d: 'Сб', t: '11:00' }],
  t4: [{ d: 'Завтра', t: '17:00' }, { d: 'Чт', t: '18:00' }],
  t5: [{ d: 'Завтра', t: '10:00' }, { d: 'Ср', t: '17:30' }, { d: 'Чт', t: '19:00' }],
  t6: [{ d: 'Завтра', t: '13:00' }, { d: 'Чт', t: '15:00' }, { d: 'Пт', t: '19:00' }, { d: 'Вс', t: '12:00' }],
};

export const TrainerDetailSheet = ({ trainer, onClose, onBook, onCheckout }) => {
  if (!trainer) return null;
  const bio = TRAINER_BIOS[trainer.id] || '';
  const slots = TRAINER_NEAR_SLOTS[trainer.id] || [];

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* Header */}
      <div style={{
        padding: '50px 12px 4px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <button onClick={onClose} style={{
          width: 36, height: 36, borderRadius: 999, border: 0,
          background: 'var(--surface)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span className="t-h3" style={{ fontSize: 15 }}>Тренер</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Hero portrait */}
        <div style={{ padding: '4px 16px 14px' }}>
          <div style={{
            position: 'relative',
            aspectRatio: '4 / 3',
            borderRadius: 'var(--r-xl)',
            background: `linear-gradient(135deg, ${trainer.bg} 0%, color-mix(in oklab, ${trainer.color} 40%, ${trainer.bg}) 100%)`,
            overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {/* Stripe placeholder pattern */}
            <svg width="100%" height="100%" style={{
              position: 'absolute', inset: 0, opacity: 0.18,
            }}>
              <defs>
                <pattern id={`stripe-${trainer.id}`} width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <line x1="0" y1="0" x2="0" y2="14" stroke={trainer.color} strokeWidth="1.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill={`url(#stripe-${trainer.id})`} />
            </svg>
            <div style={{
              position: 'relative', width: 120, height: 120, borderRadius: '50%',
              background: trainer.color, color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 48, fontWeight: 600, letterSpacing: -1,
              boxShadow: '0 12px 30px rgba(0,0,0,0.18)',
            }}>
              {trainer.initials}
            </div>
            <div style={{
              position: 'absolute', bottom: 14, left: 14,
              padding: '4px 10px', background: 'rgba(255,255,255,0.92)',
              borderRadius: 999, fontSize: 11, fontWeight: 600,
              color: '#0a0a0a', letterSpacing: 0.4, textTransform: 'uppercase',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            }}>
              ФОТО ТРЕНЕРА
            </div>
          </div>
        </div>

        {/* Name + spec */}
        <div style={{ padding: '0 20px 14px' }}>
          <div className="t-h1" style={{ fontSize: 26 }}>{trainer.name}</div>
          <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 4 }}>
            {trainer.spec}
          </div>
        </div>

        {/* Stat row */}
        <div style={{ padding: '0 16px 14px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          <StatBlock big={trainer.rating.toFixed(1)} label={`★ ${trainer.reviews} отзывов`} />
          <StatBlock big={trainer.exp} label="опыта" />
          <StatBlock big={`${trainer.price.toLocaleString('ru-RU')}`} label="₽ / час" />
        </div>

        {/* Bio */}
        {bio && (
          <div style={{ padding: '0 16px 14px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>О тренере</div>
            <div className="card" style={{ padding: 16 }}>
              <div className="t-body" style={{ color: 'var(--text-2)', lineHeight: 1.55 }}>
                {bio}
              </div>
            </div>
          </div>
        )}

        {/* Specializations chips */}
        <div style={{ padding: '0 16px 14px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Работает с</div>
          <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
            {(trainer.spec.split(',').map(s => s.trim())).map((s, i) => (
              <span key={i} className="chip">{s}</span>
            ))}
            <span className="chip">Начинающие</span>
            <span className="chip">Опытные</span>
          </div>
        </div>

        {/* Nearest slots */}
        {slots.length > 0 && (
          <div style={{ padding: '0 16px 14px' }}>
            <div className="row-between" style={{ padding: '4px 4px 8px' }}>
              <div className="t-mini" style={{ color: 'var(--text-3)' }}>Ближайшие окна</div>
              <button onClick={() => onBook(trainer)} style={{
                background: 'transparent', border: 0, color: 'var(--accent-deep)',
                fontSize: 13, fontWeight: 600, cursor: 'pointer', padding: 0,
                fontFamily: 'inherit',
              }}>Все →</button>
            </div>
            <div className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {slots.slice(0, 4).map((s, i) => (
                <button key={i}
                  onClick={() => onCheckout && onCheckout({
                    kind: 'training',
                    title: `Тренировка с ${trainer.name.split(' ')[0]}`,
                    subtitle: `${s.d}, ${s.t} · 1 час`,
                    amount: trainer.price,
                  })}
                  className="press"
                  style={{
                    border: 0, background: 'var(--surface-2)',
                    padding: '10px 14px', borderRadius: 12,
                    display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                    textAlign: 'left', color: 'var(--text)', fontFamily: 'inherit',
                  }}
                >
                  <Icon name="clock" size={18} color="var(--text-2)" />
                  <div style={{ flex: 1 }}>
                    <span className="t-h3" style={{ fontSize: 14 }}>{s.d}</span>
                    <span className="t-small" style={{ marginLeft: 8 }}>· {s.t}</span>
                  </div>
                  <span className="t-small t-num" style={{ color: 'var(--text-2)', fontWeight: 600 }}>
                    {trainer.price.toLocaleString('ru-RU')} ₽
                  </span>
                  <Icon name="chevronRight" size={14} color="var(--text-3)" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Reviews */}
        <div style={{ padding: '0 16px 18px' }}>
          <div className="row-between" style={{ padding: '4px 4px 8px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>
              Отзывы · {trainer.reviews}
            </div>
            <div className="t-small" style={{ color: 'var(--text-2)', fontWeight: 600 }}>
              ★ {trainer.rating.toFixed(1)}
            </div>
          </div>
          <div className="stack-2">
            {TRAINER_REVIEWS.map(r => (
              <div key={r.id} className="card" style={{ padding: 14 }}>
                <div className="row-between" style={{ marginBottom: 6 }}>
                  <div className="t-h3" style={{ fontSize: 14 }}>{r.author}</div>
                  <div className="t-mini" style={{
                    fontSize: 10, color: 'var(--text-3)',
                    textTransform: 'none', letterSpacing: 0,
                  }}>{r.time}</div>
                </div>
                <div className="t-small" style={{ color: 'var(--accent-deep)', marginBottom: 6 }}>
                  {'★'.repeat(r.rating)}
                  <span style={{ color: 'var(--text-3)' }}>{'★'.repeat(5 - r.rating)}</span>
                </div>
                <div className="t-body" style={{ color: 'var(--text-2)', lineHeight: 1.45 }}>
                  {r.body}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ height: 110 }} />
      </div>

      {/* Sticky CTA */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: 16,
        background: 'color-mix(in oklab, var(--bg) 85%, transparent)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        borderTop: '0.5px solid var(--border)',
      }}>
        <button onClick={() => onBook(trainer)} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Записаться · от {trainer.price.toLocaleString('ru-RU')} ₽
        </button>
      </div>
    </div>
  );
};

function StatBlock({ big, label }) {
  return (
    <div style={{
      background: 'var(--surface)', borderRadius: 'var(--r-lg)',
      border: '0.5px solid var(--border)',
      padding: '14px 12px', textAlign: 'center',
    }}>
      <div className="t-h2 t-num" style={{ fontSize: 22 }}>{big}</div>
      <div className="t-mini" style={{
        color: 'var(--text-3)', marginTop: 4,
        textTransform: 'none', letterSpacing: 0, fontWeight: 500, fontSize: 11,
      }}>{label}</div>
    </div>
  );
}

