import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { PLANS, PLAN_FEATURES } from '@/data';

export const PlansSheet = ({ onClose, onPick, currentPlanId }) => {
  // Default-select the popular plan; falls back to current if user already on one
  const [picked, setPicked] = React.useState(() => {
    return currentPlanId || PLANS.find(p => p.popular)?.id || PLANS[0].id;
  });
  const [confirming, setConfirming] = React.useState(false);

  const plan = PLANS.find(p => p.id === picked);

  if (confirming) {
    return <PlanConfirm
      plan={plan}
      onBack={() => setConfirming(false)}
      onPaid={() => { onPick && onPick(plan); onClose(); }}
    />;
  }

  return (
    <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <SheetTopBar title="Тарифы" onClose={onClose} />

      <div className="scroller" style={{ paddingTop: 4 }}>
        <div style={{ padding: '4px 20px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Подписка</div>
          <div className="t-h1" style={{ marginTop: 4 }}>Выбери свой ритм</div>
          <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)', maxWidth: 320 }}>
            Чем длиннее период — тем выгоднее в месяц. Заморозить или сменить можно в любой момент.
          </div>
        </div>

        {/* Plan cards — vertically stacked, "compare side-by-side" via a metric strip below */}
        <div className="stack-2" style={{ padding: '0 16px' }}>
          {PLANS.map(p => (
            <PlanCard
              key={p.id}
              plan={p}
              selected={picked === p.id}
              isCurrent={p.id === currentPlanId}
              onSelect={() => setPicked(p.id)}
            />
          ))}
        </div>

        {/* Comparison table */}
        <PlanCompareTable
          plans={PLANS}
          features={PLAN_FEATURES}
          picked={picked}
          onPick={setPicked}
        />

        {/* Disclaimers */}
        <div style={{ padding: '14px 24px 0' }}>
          <div className="t-small" style={{ color: 'var(--text-3)', lineHeight: 1.5, fontSize: 12 }}>
            Списание автоматическое в день окончания. Отменить продление — в один тап в профиле.
            Полный возврат — в течение 14 дней, если ни разу не приходил.
          </div>
        </div>

        <div style={{ height: 140 }} />
      </div>

      {/* Sticky CTA */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '12px 16px 20px',
        background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
      }}>
        <button
          className="btn btn-accent"
          style={{ width: '100%', height: 54 }}
          onClick={() => setConfirming(true)}
        >
          {plan?.id === currentPlanId
            ? `Текущий тариф`
            : `Оформить · ${plan?.priceTotal.toLocaleString('ru-RU')} ₽`}
        </button>
        <div className="t-small" style={{
          textAlign: 'center', color: 'var(--text-3)', marginTop: 8, fontSize: 12,
        }}>
          {plan && <>{plan.priceMonth.toLocaleString('ru-RU')} ₽ / мес · карта •••• 4821</>}
        </div>
      </div>
    </div>
  );
};

// Short labels for the comparison table header. The plan cards above
// keep the full name; in the narrow table columns we use a uniform
// numeric form ("1 мес / 6 мес / 12 мес") for rhythm and fit.
const PLAN_LABELS_SHORT = {
  monthly: '1 мес',
  half:    '6 мес',
  annual:  '12 мес',
};

// Short-form values for the compact comparison table.
// Keeps the source PLANS data verbose (used in cards), but the table needs
// values that fit one or two lines in a narrow column.
const PLAN_FEATURES_SHORT = {
  access:      { monthly: '8–22',        half: '24 / 7',        annual: '24 / 7' },
  freeze:      { monthly: null,          half: '14 дней',       annual: '30 дней' },
  guest:       { monthly: null,          half: '1 / мес',       annual: '2 / мес' },
  sauna:       { monthly: null,          half: 'Сауна',         annual: 'Сауна, бассейн' },
  group:       { monthly: '2 / нед',     half: 'Без лимита',    annual: 'Без лимита' },
  pt_discount: { monthly: null,          half: '−10%',          annual: '−15%' },
};

function PlanCompareTable({ plans, features, picked, onPick }) {
  // minmax(0, …) so columns ignore content min-widths and stay aligned
  // across every row (each row is its own grid).
  const GRID = 'minmax(0, 1.25fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr)';

  return (
    <div style={{ padding: '28px 16px 8px' }}>
      <div className="row" style={{
        padding: '0 4px 10px', justifyContent: 'space-between', alignItems: 'baseline',
      }}>
        <div className="t-mini" style={{ color: 'var(--text-3)' }}>Сравнение</div>
        <div className="t-mini" style={{ color: 'var(--text-3)', fontSize: 9.5, letterSpacing: 0.4 }}>
          ТАП ПО КОЛОНКЕ
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Header row — tappable plan columns with name + monthly price */}
        <div style={{
          display: 'grid', gridTemplateColumns: GRID,
          borderBottom: '0.5px solid var(--border)',
        }}>
          {/* Mirror the button's vertical structure so the caption sits on
              the exact same baseline as the per-plan monthly prices. */}
          <div style={{ padding: '16px 14px 14px' }}>
            <div aria-hidden="true" style={{
              fontSize: 12.5, fontWeight: 600, lineHeight: 1.2,
              visibility: 'hidden',
            }}>
              .
            </div>
            <div style={{
              fontSize: 9.5, marginTop: 4, lineHeight: 1.2,
              fontWeight: 600, letterSpacing: 0.5,
              color: 'var(--text-3)', textTransform: 'uppercase',
            }}>
              Цена / мес
            </div>
          </div>
          {plans.map((p) => {
            const isSel = picked === p.id;
            return (
              <button
                key={p.id}
                onClick={() => onPick(p.id)}
                className="press"
                style={{
                  appearance: 'none', border: 0, cursor: 'pointer',
                  padding: '16px 6px 14px',
                  background: isSel ? 'var(--text)' : 'transparent',
                  color: isSel ? 'var(--bg)' : 'var(--text)',
                  borderLeft: '0.5px solid var(--border)',
                  position: 'relative',
                  transition: 'background 0.15s, color 0.15s',
                }}>
                {p.popular && (
                  <div style={{
                    position: 'absolute', top: 5, left: '50%', transform: 'translateX(-50%)',
                    width: 4, height: 4, borderRadius: 999,
                    background: 'var(--accent)',
                  }} />
                )}
                <div style={{
                  fontSize: 12.5, fontWeight: 600, letterSpacing: -0.1,
                  opacity: isSel ? 1 : 0.85,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {PLAN_LABELS_SHORT[p.id] || p.name}
                </div>
                <div style={{
                  fontSize: 10.5, marginTop: 4, fontVariantNumeric: 'tabular-nums',
                  letterSpacing: 0.1,
                  opacity: isSel ? 0.7 : 0.55,
                }}>
                  {p.priceMonth.toLocaleString('ru-RU')} ₽/мес
                </div>
              </button>
            );
          })}
        </div>

        {/* Body — feature rows. Selected column gets matching tinted cells
            so the whole column reads as one continuous stripe. */}
        {features.map((f, i) => (
          <div key={f.key} style={{
            display: 'grid', gridTemplateColumns: GRID,
            borderTop: i === 0 ? 0 : '0.5px solid var(--border)',
            alignItems: 'stretch',
          }}>
            <div style={{
              fontSize: 12.5, fontWeight: 500, color: 'var(--text-2)',
              padding: '12px 14px', display: 'flex', alignItems: 'center',
            }}>
              {f.label}
            </div>
            {plans.map((p) => {
              const short = PLAN_FEATURES_SHORT[f.key]?.[p.id];
              const isSel = picked === p.id;
              return (
                <div key={p.id} style={{
                  padding: '12px 8px', textAlign: 'center',
                  borderLeft: '0.5px solid var(--border)',
                  background: isSel ? 'var(--surface-2)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {short ? (
                    <div style={{
                      fontSize: 11.5, lineHeight: 1.25,
                      color: isSel ? 'var(--text)' : 'var(--text-2)',
                      fontWeight: isSel ? 600 : 500,
                      letterSpacing: -0.1,
                      textWrap: 'balance',
                      wordBreak: 'normal',
                    }}>
                      {short}
                    </div>
                  ) : (
                    <div style={{
                      width: 10, height: 1, background: 'var(--text-3)', opacity: 0.5,
                    }} />
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {/* Total-price footer row */}
        <div style={{
          display: 'grid', gridTemplateColumns: GRID,
          borderTop: '0.5px solid var(--border)',
          background: 'var(--surface-2)',
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: 'var(--text-3)',
            padding: '12px 14px', display: 'flex', alignItems: 'center',
            letterSpacing: 0.4, textTransform: 'uppercase',
          }}>
            Итого
          </div>
          {plans.map((p) => {
            const isSel = picked === p.id;
            return (
              <div key={p.id} style={{
                padding: '12px 6px', textAlign: 'center',
                borderLeft: '0.5px solid var(--border)',
                background: isSel ? 'var(--text)' : 'transparent',
                color: isSel ? 'var(--bg)' : 'var(--text)',
              }}>
                <div style={{
                  fontSize: 12.5, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                  letterSpacing: -0.2,
                }}>
                  {p.priceTotal.toLocaleString('ru-RU')} ₽
                </div>
                <div style={{
                  fontSize: 9.5, marginTop: 2,
                  opacity: isSel ? 0.65 : 0.5,
                  letterSpacing: 0.2,
                }}>
                  за {p.period}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PlanCard({ plan, selected, isCurrent, onSelect }) {
  const isPopular = plan.popular;
  return (
    <button
      onClick={onSelect}
      className="press"
      style={{
        appearance: 'none', border: 0, padding: 0, cursor: 'pointer',
        textAlign: 'left', width: '100%',
        background: selected ? 'var(--text)' : 'var(--surface)',
        color: selected ? 'var(--bg)' : 'var(--text)',
        borderRadius: 'var(--r-xl)',
        outline: selected
          ? '2px solid var(--text)'
          : isPopular ? '1px solid var(--accent)' : '0.5px solid var(--border)',
        outlineOffset: selected ? -2 : (isPopular ? -1 : 0),
        transition: 'background 0.15s, color 0.15s',
        position: 'relative',
        overflow: 'hidden',
      }}>
      {/* badge */}
      {plan.badge && (
        <div style={{
          position: 'absolute', top: 14, right: 14,
          background: selected
            ? 'var(--accent)'
            : (isPopular ? 'var(--accent)' : 'var(--surface-2)'),
          color: selected
            ? '#06120c'
            : (isPopular ? '#06120c' : 'var(--text)'),
          fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase',
          padding: '4px 8px', borderRadius: 6,
        }}>
          {plan.badge}
        </div>
      )}

      <div style={{ padding: '18px 18px 16px' }}>
        <div className="row" style={{ gap: 10, alignItems: 'center' }}>
          {/* Selection indicator */}
          <div style={{
            width: 22, height: 22, borderRadius: 999,
            border: selected ? '2px solid var(--bg)' : '1.5px solid var(--border-strong)',
            background: selected ? 'var(--accent)' : 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            {selected && <Icon name="check" size={14} color="#06120c" strokeWidth={3} />}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 18, fontWeight: 600, letterSpacing: -0.3,
            }}>
              {plan.name}
            </div>
            <div style={{
              fontSize: 12.5, marginTop: 2,
              color: selected ? 'color-mix(in srgb, var(--bg) 65%, transparent)' : 'var(--text-2)',
            }}>
              {plan.tagline}{isCurrent ? ' · сейчас активен' : ''}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 14, display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontSize: 32, fontWeight: 700, letterSpacing: -0.8,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {plan.priceMonth.toLocaleString('ru-RU')} ₽
          </span>
          <span style={{
            fontSize: 13,
            color: selected ? 'color-mix(in srgb, var(--bg) 65%, transparent)' : 'var(--text-2)',
          }}>
            / мес
          </span>
        </div>
        <div style={{
          fontSize: 12, marginTop: 2,
          color: selected ? 'color-mix(in srgb, var(--bg) 55%, transparent)' : 'var(--text-3)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {plan.priceTotal.toLocaleString('ru-RU')} ₽ за {plan.period}
        </div>
      </div>
    </button>
  );
}

function PlanConfirm({ plan, onBack, onPaid }) {
  const [paying, setPaying] = React.useState(false);
  const [paid, setPaid] = React.useState(false);

  const pay = () => {
    setPaying(true);
    setTimeout(() => {
      setPaying(false);
      setPaid(true);
      setTimeout(onPaid, 1100);
    }, 1200);
  };

  if (paid) {
    return (
      <div className="sheet" style={{ background: 'var(--bg)' }}>
        <StatusBar />
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', padding: '0 28px',
        }}>
          <div className="scale-in haptic" style={{
            width: 84, height: 84, borderRadius: 999, background: 'var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="check" size={44} color="#06120c" strokeWidth={2.6} />
          </div>
          <div className="t-display" style={{ marginTop: 24, textAlign: 'center', letterSpacing: -0.8 }}>
            Оплачено
          </div>
          <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 8, textAlign: 'center' }}>
            {plan.name} активен. Чек придёт на почту.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <SheetTopBar title="Оплата" onBack={onBack} />

      <div className="scroller" style={{ paddingTop: 0 }}>
        <div style={{ padding: '8px 20px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>К оплате</div>
          <div className="t-display" style={{ marginTop: 4, letterSpacing: -1, fontVariantNumeric: 'tabular-nums' }}>
            {plan.priceTotal.toLocaleString('ru-RU')} ₽
          </div>
          <div className="t-small" style={{ marginTop: 4 }}>
            {plan.name} · {plan.period} · {plan.priceMonth.toLocaleString('ru-RU')} ₽/мес
          </div>
        </div>

        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RowItem icon="card" label="Карта" value="Visa •••• 4821" sub="Привязанная по умолчанию" />
            <Divider />
            <RowItem icon="calendar" label="Списание" value="Сегодня" sub={`Следующее — через ${plan.period}`} />
            <Divider />
            <RowItem icon="info" label="Возврат" value="14 дней" sub="Полный, если ни разу не приходил" />
          </div>
        </div>

        <div style={{ height: 140 }} />
      </div>

      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '12px 16px 20px',
        background: 'linear-gradient(to top, var(--bg) 70%, transparent)',
      }}>
        <button
          onClick={pay}
          disabled={paying}
          className="btn btn-accent"
          style={{ width: '100%', height: 54, opacity: paying ? 0.7 : 1 }}
        >
          {paying ? 'Оплачиваем…' : `Оплатить ${plan.priceTotal.toLocaleString('ru-RU')} ₽`}
        </button>
      </div>
    </div>
  );
}

function SheetTopBar({ title, onClose, onBack }) {
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

