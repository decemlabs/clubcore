import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';

// Accepts: { kind: 'training' | 'sub' | 'shop', title, subtitle, amount, lineItems? }

export const CheckoutSheet = ({ ctx, onClose, onDone, forceOutcome }) => {
  const [stage, setStage] = React.useState('review'); // 'review' | 'paying' | 'done' | 'error'
  const [errorKind, setErrorKind] = React.useState(null); // 'payment' | 'slot-busy' | 'offline'
  const [card, setCard] = React.useState('saved');    // 'saved' | 'apple' | 'new'
  const [savePromo, setSavePromo] = React.useState(false);
  const [promoCode, setPromoCode] = React.useState('');
  const [promoApplied, setPromoApplied] = React.useState(false);

  if (!ctx) return null;

  const discount = promoApplied ? Math.round(ctx.amount * 0.1) : 0;
  const total = ctx.amount - discount;

  const startPay = () => {
    setStage('paying');
    setTimeout(() => {
      const outcome = forceOutcome || 'ok';
      if (outcome === 'ok') setStage('done');
      else { setErrorKind(outcome); setStage('error'); }
    }, 1300);
  };

  if (stage === 'done') {
    return <CheckoutDone ctx={ctx} total={total} onClose={() => { onClose(); onDone && onDone(); }} />;
  }

  if (stage === 'error') {
    return <CheckoutError kind={errorKind}
                          onRetry={() => { setStage('review'); setErrorKind(null); }}
                          onClose={onClose} />;
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 240,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

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
        <span className="t-h3" style={{ fontSize: 15 }}>Оплата</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Big sum */}
        <div style={{ padding: '8px 20px 18px', textAlign: 'center' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>К оплате</div>
          <div className="t-display t-num" style={{ marginTop: 6, fontSize: 44, letterSpacing: -1 }}>
            {total.toLocaleString('ru-RU')} ₽
          </div>
          {discount > 0 && (
            <div className="t-small" style={{ marginTop: 4, color: 'var(--accent-deep)', fontWeight: 600 }}>
              Скидка −{discount.toLocaleString('ru-RU')} ₽ применена
            </div>
          )}
        </div>

        {/* Order summary */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Заказ</div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: 'var(--surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={ctx.kind === 'sub' ? 'card' : ctx.kind === 'training' ? 'user' : 'tag'}
                      size={20} color="var(--text)" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t-h3" style={{ fontSize: 15 }}>{ctx.title}</div>
                <div className="t-small" style={{ marginTop: 2 }}>{ctx.subtitle}</div>
              </div>
              <div className="t-h3 t-num" style={{ fontSize: 15 }}>
                {ctx.amount.toLocaleString('ru-RU')} ₽
              </div>
            </div>
            {discount > 0 && (
              <>
                <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 14 }} />
                <div style={{ padding: '12px 14px', display: 'flex', justifyContent: 'space-between' }}>
                  <span className="t-small" style={{ color: 'var(--accent-deep)' }}>Промокод FIT10</span>
                  <span className="t-h3 t-num" style={{ fontSize: 14, color: 'var(--accent-deep)' }}>
                    −{discount.toLocaleString('ru-RU')} ₽
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Promo code */}
        {!promoApplied && (
          <div style={{ padding: '0 16px 12px' }}>
            <div style={{
              display: 'flex', gap: 8, alignItems: 'stretch',
            }}>
              <div style={{
                flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8,
                background: 'var(--surface)', borderRadius: 'var(--r-lg)',
                border: '0.5px solid var(--border)',
                padding: '0 14px', height: 46,
              }}>
                <Icon name="tag" size={18} color="var(--text-3)" />
                <input
                  value={promoCode}
                  onChange={e => setPromoCode(e.target.value.toUpperCase())}
                  placeholder="Промокод"
                  style={{
                    flex: 1, minWidth: 0, width: '100%',
                    border: 0, outline: 0, background: 'transparent',
                    color: 'var(--text)', fontFamily: 'inherit', fontSize: 14,
                    fontWeight: 500, letterSpacing: 0.5,
                  }}
                />
              </div>
              <button
                onClick={() => promoCode && setPromoApplied(true)}
                disabled={!promoCode}
                style={{
                  height: 46, padding: '0 18px', borderRadius: 'var(--r-pill)',
                  border: 0, background: promoCode ? 'var(--text)' : 'var(--surface-2)',
                  color: promoCode ? 'var(--bg)' : 'var(--text-3)',
                  fontWeight: 600, fontSize: 14, cursor: promoCode ? 'pointer' : 'default',
                  fontFamily: 'inherit', whiteSpace: 'nowrap', flexShrink: 0,
                }}
              >Применить</button>
            </div>
          </div>
        )}

        {/* Card picker */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
            Способ оплаты
          </div>
          <div className="card" style={{ padding: 4 }}>
            <PayOption
              icon="card"
              title="Visa •••• 4821"
              sub="Срок до 09 / 28"
              checked={card === 'saved'}
              onClick={() => setCard('saved')}
            />
            <Divider2c />
            <PayOption
              icon="card"
              title="Apple Pay"
              sub="Touch ID"
              checked={card === 'apple'}
              onClick={() => setCard('apple')}
            />
            <Divider2c />
            <PayOption
              icon="add"
              title="Новая карта"
              sub="Visa, Mastercard, Мир"
              checked={card === 'new'}
              onClick={() => setCard('new')}
            />
          </div>
        </div>

        {/* Save card switch */}
        {card === 'saved' && (
          <div style={{ padding: '0 16px 18px' }}>
            <button
              onClick={() => setSavePromo(s => !s)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                background: 'transparent', border: 0, cursor: 'pointer',
                color: 'var(--text-2)', fontFamily: 'inherit',
                padding: '8px 4px', textAlign: 'left',
              }}
            >
              <div style={{
                width: 22, height: 22, borderRadius: 6,
                border: `1.5px solid ${savePromo ? 'var(--accent)' : 'var(--text-3)'}`,
                background: savePromo ? 'var(--accent)' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                {savePromo && (
                  <svg width="14" height="14" viewBox="0 0 24 24">
                    <path d="M5 12l5 5L20 7" stroke="#06120c" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              <span className="t-small" style={{ color: 'var(--text-2)' }}>
                Подписаться на акции и скидки клуба
              </span>
            </button>
          </div>
        )}

        <div style={{ height: 110 }} />
      </div>

      {/* Sticky pay button */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: 16,
        background: 'color-mix(in oklab, var(--bg) 85%, transparent)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        borderTop: '0.5px solid var(--border)',
      }}>
        <button
          onClick={startPay}
          disabled={stage === 'paying'}
          className="btn btn-accent"
          style={{ width: '100%', height: 54, opacity: stage === 'paying' ? 0.7 : 1 }}
        >
          {stage === 'paying' ? (
            <>
              <span className="ptr-spin" style={{
                borderColor: 'rgba(6,18,12,0.25)', borderTopColor: '#06120c',
              }} />
              Оплачиваем…
            </>
          ) : (
            <>Оплатить · {total.toLocaleString('ru-RU')} ₽</>
          )}
        </button>
        <div className="t-small" style={{
          textAlign: 'center', marginTop: 8, color: 'var(--text-3)',
        }}>
          Нажимая, ты соглашаешься с условиями оплаты
        </div>
      </div>
    </div>
  );
};

function PayOption({ icon, title, sub, checked, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: '100%', display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 12px', background: 'transparent', border: 0,
      cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
      color: 'var(--text)',
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={icon === 'add' ? 'plus' : icon} size={18} color="var(--text-2)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{title}</div>
        <div className="t-small" style={{ marginTop: 1 }}>{sub}</div>
      </div>
      <div style={{
        width: 22, height: 22, borderRadius: 999,
        border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--text-3)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        {checked && <span style={{
          width: 10, height: 10, borderRadius: 999, background: 'var(--accent)',
        }} />}
      </div>
    </button>
  );
}

function Divider2c() {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 12 }} />;
}

function CheckoutDone({ ctx, total, onClose }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 240,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'fade-up 0.4s ease-out',
    }}>
      <StatusBar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', padding: '40px 28px' }}>
        <div style={{
          width: 84, height: 84, borderRadius: 999, background: 'var(--accent)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'scale-in 0.4s cubic-bezier(0.32, 1.4, 0.4, 1)',
          marginBottom: 24,
        }}>
          <svg width="44" height="44" viewBox="0 0 24 24">
            <path d="M5 12l5 5L20 7" stroke="#06120c" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="t-display" style={{ textAlign: 'center', letterSpacing: -1, fontSize: 32 }}>
          Готово!
        </div>
        <div className="t-body" style={{
          textAlign: 'center', marginTop: 10, color: 'var(--text-2)',
          maxWidth: 280, lineHeight: 1.5,
        }}>
          {ctx.kind === 'sub' ? 'Абонемент активирован. QR в зале уже работает.' :
           ctx.kind === 'training' ? 'Записали и сохранили в твоём расписании. Напомним за час.' :
           'Оплата прошла. Чек придёт на почту.'}
        </div>
        <div style={{
          marginTop: 22, padding: '12px 18px',
          background: 'var(--surface)', borderRadius: 'var(--r-lg)',
          border: '0.5px solid var(--border)',
          display: 'flex', gap: 14, alignItems: 'center',
        }}>
          <Icon name="card" size={18} color="var(--text-3)" />
          <div>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>Списано</div>
            <div className="t-h3 t-num" style={{ fontSize: 16 }}>
              {total.toLocaleString('ru-RU')} ₽ · •••• 4821
            </div>
          </div>
        </div>
      </div>
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button onClick={() => { onClose(); window.__openReceipt?.(ctx, total); }} className="btn" style={{
          width: '100%', height: 50, background: 'var(--surface)', color: 'var(--text)',
          border: '0.5px solid var(--border-strong)',
        }}>
          Посмотреть чек
        </button>
        <button onClick={onClose} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Хорошо
        </button>
      </div>
    </div>
  );
}

// Inline error states — payment-rejected / slot-busy / offline
function CheckoutError({ kind, onRetry, onClose }) {
  const variants = {
    payment: {
      icon: 'card', tone: 'error',
      title: 'Не получилось списать',
      body: 'Банк отклонил платёж. Проверь баланс или попробуй другую карту.',
      primary: 'Попробовать снова',
      secondary: 'Поменять карту',
    },
    'slot-busy': {
      icon: 'clock', tone: 'warn',
      title: 'Слот уже занят',
      body: 'Кто-то записался на это время, пока ты оплачивал. Деньги не списали.',
      primary: 'Выбрать другое время',
      secondary: 'Назад',
    },
    offline: {
      icon: 'wifi', tone: 'info',
      title: 'Нет связи',
      body: 'Похоже, интернет пропал. Попробуй ещё раз, когда появится сеть.',
      primary: 'Повторить',
      secondary: 'Закрыть',
    },
  }[kind] || {
    icon: 'alert', tone: 'error',
    title: 'Что-то пошло не так',
    body: 'Попробуй ещё раз.',
    primary: 'Повторить',
    secondary: 'Закрыть',
  };
  const palette = {
    error: { bg: 'var(--danger-soft)', fg: 'var(--danger)' },
    warn:  { bg: 'var(--warn-soft)',   fg: '#a36a16' },
    info:  { bg: 'var(--surface-2)',   fg: 'var(--text-2)' },
  }[variants.tone];
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 240,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <div style={{
        padding: '50px 12px 4px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start',
      }}>
        <button onClick={onClose} style={{
          width: 36, height: 36, borderRadius: 999, border: 0,
          background: 'var(--surface)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="close" size={20} color="var(--text)" strokeWidth={2.2} />
        </button>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', padding: '20px 28px' }}>
        <div className="haptic" style={{
          width: 92, height: 92, borderRadius: 22, background: palette.bg, color: palette.fg,
          display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 22,
        }}>
          <Icon name={variants.icon} size={44} color="currentColor" strokeWidth={2} />
        </div>
        <div className="t-display" style={{ textAlign: 'center', letterSpacing: -0.8, fontSize: 28 }}>
          {variants.title}
        </div>
        <div className="t-body" style={{
          textAlign: 'center', marginTop: 10, color: 'var(--text-2)', maxWidth: 300, lineHeight: 1.5,
        }}>{variants.body}</div>
      </div>
      <div style={{ padding: '16px 16px 28px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button onClick={onRetry} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          {variants.primary}
        </button>
        <button onClick={onClose} className="btn" style={{
          width: '100%', height: 48, background: 'transparent', color: 'var(--text-2)',
          border: '0.5px solid var(--border-strong)',
        }}>
          {variants.secondary}
        </button>
      </div>
    </div>
  );
}

