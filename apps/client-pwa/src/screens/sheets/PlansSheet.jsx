import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useClientPlans, useClientPtPackages } from '@/data';

// ─── In-file adapters: API plan shapes → card render shapes ──────────────
// API: ClientCatalogPlanResponse { id, name, priceKopecks, durationDays }
export function toMembershipCard(p) {
  const priceRub = p.priceKopecks / 100;
  const durationMonths = Math.round(p.durationDays / 30);
  const pricePerMonth = durationMonths > 0 ? Math.round(priceRub / durationMonths) : priceRub;
  return {
    id: String(p.id),
    name: p.name,
    tagline: `${p.durationDays} дней`,
    priceMonth: pricePerMonth,
    priceTotal: priceRub,
    period: durationMonths === 1 ? '1 мес' : durationMonths < 12 ? `${durationMonths} мес` : '12 мес',
    popular: durationMonths === 6,
    badge: durationMonths === 12 ? 'Выгоднее всего' : durationMonths === 6 ? 'Популярный' : null,
    kind: 'sub',
  };
}

// API: ClientCatalogPtPackageResponse { id, name, sessionCount, priceKopecks }
export function toPtCard(p) {
  const priceRub = p.priceKopecks / 100;
  const pricePerSession = p.sessionCount > 0 ? Math.round(priceRub / p.sessionCount) : priceRub;
  return {
    id: String(p.id),
    name: p.name,
    tagline: `${p.sessionCount} занятий`,
    priceMonth: pricePerSession,
    priceTotal: priceRub,
    period: `${p.sessionCount} тренировок`,
    popular: p.sessionCount === 10,
    badge: null,
    kind: 'pt',
  };
}

export const PlansSheet = ({ onClose, onPick, currentPlanId }) => {
  const { data: membershipPlans, isLoading: plansLoading, isError: plansError } = useClientPlans();
  const { data: ptPackages, isLoading: ptLoading, isError: ptError } = useClientPtPackages();

  const isLoading = plansLoading || ptLoading;
  const isError = plansError || ptError;

  // Adapt API data to card render shapes
  const allPlans = React.useMemo(() => {
    const plans = (membershipPlans ?? []).map(toMembershipCard);
    const ptCards = (ptPackages ?? []).map(toPtCard);
    return [...plans, ...ptCards];
  }, [membershipPlans, ptPackages]);

  const [picked, setPicked] = React.useState(null);
  const [confirming, setConfirming] = React.useState(false);

  // Set default selection once data loads
  React.useEffect(() => {
    if (allPlans.length > 0 && picked === null) {
      const defaultPlan = currentPlanId
        ? (allPlans.find(p => p.id === currentPlanId) ?? allPlans.find(p => p.popular) ?? allPlans[0])
        : (allPlans.find(p => p.popular) ?? allPlans[0]);
      setPicked(defaultPlan?.id ?? null);
    }
  }, [allPlans, picked, currentPlanId]);

  const plan = allPlans.find(p => p.id === picked);

  if (isLoading) {
    return (
      <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="ptr-spin" style={{ width: 28, height: 28, borderWidth: 2 }} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 }}>
        <Icon name="alert" size={32} color="var(--danger)" strokeWidth={2} />
        <div className="t-h3" style={{ textAlign: 'center' }}>Не удалось загрузить тарифы</div>
        <button onClick={onClose} className="btn" style={{ height: 44, padding: '0 24px' }}>
          Закрыть
        </button>
      </div>
    );
  }

  if (confirming && plan) {
    return <PlanConfirm
      plan={plan}
      onBack={() => setConfirming(false)}
      onClose={onClose}
      onPaid={() => { onPick && onPick(plan); onClose(); }}
    />;
  }

  // Separate membership plans from PT packages for display
  const membershipCards = allPlans.filter(p => p.kind === 'sub');
  const ptCards = allPlans.filter(p => p.kind === 'pt');

  return (
    <div className="sheet" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <SheetTopBar title="Тарифы" onClose={onClose} />

      <div className="scroller" style={{ paddingTop: 4 }}>
        {membershipCards.length > 0 && (
          <>
            <div style={{ padding: '4px 20px 16px' }}>
              <div className="t-mini" style={{ color: 'var(--text-3)' }}>Подписка</div>
              <div className="t-h1" style={{ marginTop: 4 }}>Выбери свой ритм</div>
              <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)', maxWidth: 320 }}>
                Чем длиннее период — тем выгоднее в месяц. Заморозить или сменить можно в любой момент.
              </div>
            </div>

            <div className="stack-2" style={{ padding: '0 16px' }}>
              {membershipCards.map(p => (
                <PlanCard
                  key={p.id}
                  plan={p}
                  selected={picked === p.id}
                  isCurrent={p.id === currentPlanId}
                  onSelect={() => setPicked(p.id)}
                />
              ))}
            </div>
          </>
        )}

        {ptCards.length > 0 && (
          <>
            <div style={{ padding: membershipCards.length > 0 ? '24px 20px 12px' : '4px 20px 12px' }}>
              <div className="t-mini" style={{ color: 'var(--text-3)' }}>Персональные тренировки</div>
              <div className="t-h2" style={{ marginTop: 4 }}>Пакеты с тренером</div>
            </div>

            <div className="stack-2" style={{ padding: '0 16px' }}>
              {ptCards.map(p => (
                <PlanCard
                  key={p.id}
                  plan={p}
                  selected={picked === p.id}
                  isCurrent={p.id === currentPlanId}
                  onSelect={() => setPicked(p.id)}
                />
              ))}
            </div>
          </>
        )}

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
          disabled={!plan}
        >
          {plan?.id === currentPlanId
            ? `Текущий тариф`
            : plan
              ? (plan.kind === 'pt'
                  ? `Купить · ${plan.priceTotal.toLocaleString('ru-RU')} ₽`
                  : `Оформить · ${plan.priceTotal.toLocaleString('ru-RU')} ₽`)
              : 'Выберите тариф'}
        </button>
        <div className="t-small" style={{
          textAlign: 'center', color: 'var(--text-3)', marginTop: 8, fontSize: 12,
        }}>
          {plan && plan.kind === 'sub' && <>{plan.priceMonth.toLocaleString('ru-RU')} ₽ / мес · карта •••• 4821</>}
          {plan && plan.kind === 'pt' && <>{plan.priceMonth.toLocaleString('ru-RU')} ₽ / занятие · карта •••• 4821</>}
        </div>
      </div>
    </div>
  );
};

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
            {plan.kind === 'pt' ? '/ занятие' : '/ мес'}
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

// PlanConfirm shows checkout details and delegates actual payment to CheckoutSheet
// via onPaid which opens CheckoutSheet with the selected planId+kind.
function PlanConfirm({ plan, onBack, onClose, onPaid }) {
  // Redirect to checkout — pass planId + kind to the checkout flow
  const handleCheckout = () => {
    // onPaid triggers App.jsx → ui.setCheckoutCtx({ kind, planId, ... })
    onPaid();
  };

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
            {plan.name} · {plan.period} · {plan.priceMonth.toLocaleString('ru-RU')} ₽/{plan.kind === 'pt' ? 'занятие' : 'мес'}
          </div>
        </div>

        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RowItem icon="card" label="Карта" value="Visa •••• 4821" sub="Привязанная по умолчанию" />
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
          onClick={handleCheckout}
          className="btn btn-accent"
          style={{ width: '100%', height: 54 }}
        >
          Перейти к оплате · {plan.priceTotal.toLocaleString('ru-RU')} ₽
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
