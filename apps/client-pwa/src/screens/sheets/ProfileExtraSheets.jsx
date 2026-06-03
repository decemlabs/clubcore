import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useClientMe, useUpdateClientProfile, useClientPaymentMethod, useUnlinkPaymentMethod, usePatchAutopay } from '@/data';

// ─── Generic sheet header ──────────────────────────────────────
export function SubSheetHeader({ title, onClose, action }) {
  return (
    <div style={{
      position: 'relative',
      padding: '50px 12px 8px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 8,
    }}>
      <button onClick={onClose} aria-label="Закрыть" style={{
        width: 36, height: 36, borderRadius: 999, border: 0,
        background: 'var(--surface)', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flex: '0 0 auto',
      }}>
        <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
      </button>
      <span className="t-h3" style={{
        fontSize: 15,
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, calc(-50% + 21px))',
        pointerEvents: 'none',
        whiteSpace: 'nowrap',
      }}>{title}</span>
      <div style={{
        minWidth: 36, display: 'flex', justifyContent: 'flex-end',
        alignItems: 'center', flex: '0 0 auto',
      }}>{action}</div>
    </div>
  );
}

// Goal enum → Russian display label (PDATA-02 / T-76-05)
const GOAL_LABELS = {
  lose_weight: 'Похудение',
  gain_mass: 'Набор массы',
  tone: 'Тонус',
  maintain: 'Поддержание формы',
};
const GOAL_OPTIONS = ['lose_weight', 'gain_mass', 'tone', 'maintain'];

// ─── Personal data ────────────────────────────────────────────
export const PersonalDataSheet = ({ onClose, userName, setTweak }) => {
  const { data: meData } = useClientMe();
  const updateProfile = useUpdateClientProfile();

  // Editable local state — initialized from API data via useEffect (PDATA-01)
  const [name, setName] = React.useState('');
  const [email, setEmail] = React.useState('');
  const [goal, setGoal] = React.useState('');
  const [heightCm, setHeightCm] = React.useState('');
  const [weightKg, setWeightKg] = React.useState('');

  // Local-only fields (no backend column — D-76-11)
  const [dob, setDob] = React.useState('14.03.1996');
  const [gender, setGender] = React.useState('f');

  const [saved, setSaved] = React.useState(false);

  // Local in-sheet toast state (mirror CheckoutSheet pattern — no global Sonner in PWA)
  const [toastMsg, setToastMsg] = React.useState(null);
  const toastTimer = React.useRef(null);

  // Hydrate from API once per client load (PDATA-01 / D-76-10). Guarding on a
  // ref keyed by client id means a later background refetch / cache invalidation
  // (which mints a new meData object identity) does NOT clobber unsaved edits.
  const hydratedForId = React.useRef(null);
  React.useEffect(() => {
    if (!meData) return;
    const key = meData.id ?? '__me__';
    if (hydratedForId.current === key) return;
    hydratedForId.current = key;
    setName(meData.firstName ?? '');
    setEmail(meData.email ?? '');
    setGoal(meData.goal ?? '');
    setHeightCm(meData.heightCm != null ? String(meData.heightCm) : '');
    setWeightKg(meData.weightKg != null ? String(meData.weightKg) : '');
  }, [meData]);

  // Phone: read-only from API; ref tracks initial value for SMS-verify guard (unchanged)
  const phone = meData?.phone ?? '';
  const initialPhone = React.useRef(phone);
  React.useEffect(() => {
    if (phone) initialPhone.current = phone;
  }, [phone]);

  const isSaving = updateProfile.isPending;

  const showToast = (msg) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToastMsg(msg);
    toastTimer.current = setTimeout(() => setToastMsg(null), 2600);
  };

  const onSave = async () => {
    // Phone changes delegate to the SMS-verify flow. NOTE (WR-76-04): phone is
    // currently read-only in this sheet, so this branch is unreachable today —
    // retained for when phone editing is wired here.
    if (phone !== initialPhone.current) {
      window.__openSmsVerify?.('phone', phone);
      return;
    }
    // heightCm/weightKg are integer columns server-side — coerce to a positive
    // integer and drop anything non-numeric/≤0 so we never PATCH NaN or a float.
    const toPosInt = (s) => {
      const n = Math.round(Number(s));
      return Number.isFinite(n) && n > 0 ? n : undefined;
    };
    try {
      await updateProfile.mutateAsync({
        firstName: name,
        email: email || undefined,
        goal: goal || undefined,
        heightCm: heightCm ? toPosInt(heightCm) : undefined,
        weightKg: weightKg ? toPosInt(weightKg) : undefined,
      });
      if (setTweak) setTweak('userName', name);
      setSaved(true);
      setTimeout(() => setSaved(false), 1400);
    } catch {
      showToast('Не удалось сохранить данные. Попробуйте ещё раз.');
    }
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Личные данные" onClose={onClose} action={
        <button onClick={onSave} disabled={isSaving} style={{
          border: 0, background: 'transparent',
          color: saved ? 'var(--accent-deep)' : isSaving ? 'var(--text-3)' : 'var(--text)',
          fontSize: 13, fontWeight: 600, padding: '6px 10px',
          cursor: isSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
        }}>
          {saved ? 'Сохранено' : isSaving ? 'Сохранение…' : 'Сохранить'}
        </button>
      } />

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Avatar */}
        <div style={{
          padding: '8px 16px 20px', display: 'flex', flexDirection: 'column',
          alignItems: 'center',
        }}>
          <div style={{ position: 'relative' }}>
            <Avatar
              initials={(name || meData?.firstName || '?').slice(0, 1).toUpperCase()}
              bg="var(--avatar-bg)"
              color="var(--avatar-fg)"
              size={88}
            />
            <button style={{
              position: 'absolute', right: -4, bottom: -4,
              width: 32, height: 32, borderRadius: 999, border: '2px solid var(--bg)',
              background: 'var(--accent)', color: '#06120c', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 0,
            }}>
              <Icon name="plus" size={16} color="currentColor" strokeWidth={2.4} />
            </button>
          </div>
          <div className="t-small" style={{ marginTop: 12, color: 'var(--text-3)' }}>
            Тапни +, чтобы загрузить фото
          </div>
        </div>

        {/* Основное — API-backed fields */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Основное</div>
          <div className="card" style={{ padding: 0 }}>
            <FormRow label="Имя" value={name} onChange={setName} />
            <Divider3 />
            <FormRow label="Телефон" value={phone} onChange={() => {}} type="tel" />
            <Divider3 />
            <FormRow label="Email" value={email} onChange={setEmail} type="email" />
          </div>
        </div>

        {/* О себе — local-only fields (D-76-11); labelled "Только на устройстве" */}
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px 8px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>О себе</div>
            <div className="t-mini" style={{ color: 'var(--text-3)', marginLeft: 'auto', fontSize: 11 }}>
              Только на устройстве
            </div>
          </div>
          <div className="card" style={{ padding: 0 }}>
            <FormRow label="Дата рождения" value={dob} onChange={setDob} />
            <Divider3 />
            <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div className="t-h3" style={{ fontSize: 14, flex: 1 }}>Пол</div>
              <div className="seg" style={{ padding: 2 }}>
                <button className={`seg-item ${gender === 'f' ? 'active' : ''}`}
                        onClick={() => setGender('f')}>Жен</button>
                <button className={`seg-item ${gender === 'm' ? 'active' : ''}`}
                        onClick={() => setGender('m')}>Муж</button>
              </div>
            </div>
          </div>
        </div>

        {/* Здоровье — API-backed; height/weight editable, goal = segmented enum control */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Здоровье</div>
          <div className="card" style={{ padding: 0 }}>
            <FormRow label="Рост" value={heightCm} onChange={setHeightCm} type="number" placeholder="см" />
            <Divider3 />
            <FormRow label="Вес" value={weightKg} onChange={setWeightKg} type="number" placeholder="кг" />
            <Divider3 />
            {/* Goal — server-enforced 4-value enum (T-76-05); segmented control prevents invalid values */}
            <div style={{ padding: '12px 14px' }}>
              <div className="t-small" style={{ color: 'var(--text-2)', marginBottom: 8 }}>Цель</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {GOAL_OPTIONS.map((key) => (
                  <button
                    key={key}
                    onClick={() => setGoal(key === goal ? '' : key)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 999,
                      border: `1px solid ${goal === key ? 'var(--accent)' : 'var(--border)'}`,
                      background: goal === key ? 'var(--accent-soft)' : 'transparent',
                      color: goal === key ? 'var(--accent-deep)' : 'var(--text-2)',
                      fontSize: 13,
                      fontWeight: goal === key ? 600 : 400,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      transition: 'all 0.15s',
                    }}
                  >
                    {GOAL_LABELS[key]}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{ padding: '20px 16px 30px' }}>
          <button onClick={() => window.__openDeleteAccount?.()} style={{
            width: '100%', height: 50, borderRadius: 999, border: '0.5px solid var(--border-strong)',
            background: 'transparent', color: 'var(--danger)',
            fontSize: 15, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer',
          }}>
            Удалить аккаунт
          </button>
        </div>

        {/* In-sheet error toast — local state pattern (no global Sonner in PWA) */}
        <div
          aria-live="polite"
          aria-atomic="true"
          style={{
            position: 'absolute',
            left: 16,
            right: 16,
            bottom: 32,
            zIndex: 200,
            background: 'var(--danger-soft)',
            color: 'var(--danger)',
            border: '1px solid var(--danger)',
            borderRadius: 14,
            padding: '11px 13px',
            display: 'flex',
            alignItems: 'center',
            gap: 11,
            boxShadow: '0 16px 40px rgba(28, 25, 23, 0.18)',
            transform: toastMsg ? 'translateY(0)' : 'translateY(180%)',
            opacity: toastMsg ? 1 : 0,
            transition: 'transform 0.42s cubic-bezier(0.32, 0.72, 0.2, 1), opacity 0.3s',
            pointerEvents: 'none',
          }}
        >
          <span style={{
            width: 30, height: 30, borderRadius: 9, flexShrink: 0,
            background: 'var(--danger)', color: '#fff',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" style={{ width: 17, height: 17 }}>
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </span>
          <span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 650, letterSpacing: '-0.1px', lineHeight: 1.25 }}>
            {toastMsg}
          </span>
        </div>
      </div>
    </div>
  );
};

export function FormRow({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div className="t-small" style={{ width: 110, color: 'var(--text-2)' }}>{label}</div>
      <input
        type={type} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        style={{
          flex: 1, border: 0, outline: 0, background: 'transparent',
          fontFamily: 'inherit', fontSize: 15, fontWeight: 500,
          color: 'var(--text)', textAlign: 'right',
        }}
      />
    </div>
  );
}

export function Divider3() {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 14 }} />;
}

// ─── Card management ──────────────────────────────────────────
export const CardSheet = ({ onClose }) => {
  const [unbindConfirm, setUnbindConfirm] = React.useState(false);
  const [unbindError, setUnbindError] = React.useState(null);
  const [autopayConsentOpen, setAutopayConsentOpen] = React.useState(false);
  const [autopayError, setAutopayError] = React.useState(null);

  const { data: cardData } = useClientPaymentMethod();
  const patchAutopay = usePatchAutopay();
  const unlinkCard = useUnlinkPaymentMethod();

  const openPaymentMethods = () => {
    onClose();
    setTimeout(() => window.__openPaymentMethods?.(), 280);
  };

  // Wire: enable autopay with ФЗ-376 consent (T-81-06)
  const handleEnableAutopayWithConsent = async () => {
    setAutopayError(null);
    try {
      await patchAutopay.mutateAsync({ enabled: true, consentAcknowledged: true });
      setAutopayConsentOpen(false);
    } catch (err) {
      const code = err && typeof err === 'object' && 'code' in err ? err.code : null;
      setAutopayConsentOpen(false);
      if (code === 'consent_required') {
        // Re-surface consent modal — backend rejected without acknowledged flag
        setAutopayConsentOpen(true);
      } else {
        setAutopayError('Не удалось включить автопродление. Попробуйте ещё раз.');
      }
    }
  };

  // Wire: disable autopay — no consent needed (T-81-06).
  // WR-03: disabling MUST NEVER route into the enable-consent modal. The
  // backend's 409 consent_required only fires when ENABLING without
  // consent_acknowledged=true, so any error on disable is an unexpected
  // failure — surface a generic toast, never an enable-consent confirm whose
  // "Подключить" button would ENABLE autopay (the opposite of user intent).
  const handleDisableAutopay = async () => {
    setAutopayError(null);
    try {
      await patchAutopay.mutateAsync({ enabled: false, consentAcknowledged: false });
    } catch {
      setAutopayError('Не удалось изменить автопродление. Попробуйте ещё раз.');
    }
  };

  // Wire: unlink card — DELETE /client/payment-method (PAYM-03, T-81-10)
  const handleUnlinkConfirmed = async () => {
    setUnbindError(null);
    try {
      await unlinkCard.mutateAsync();
      setUnbindConfirm(false);
      onClose();
    } catch (err) {
      setUnbindConfirm(false);
      const code = err && typeof err === 'object' && 'code' in err ? err.code : null;
      setUnbindError(code ? `Ошибка: ${String(code)}` : 'Не удалось отвязать карту. Попробуйте ещё раз.');
    }
  };

  // Expiry display helpers
  const expiryStr = cardData
    ? `${String(cardData.expiryMonth).padStart(2, '0')} / ${String(cardData.expiryYear).slice(-2)}`
    : '—— / ——';

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Привязанная карта" onClose={onClose} />

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Card visual — real data from GET /client/payment-method (T-81-07) */}
        <div style={{ padding: '8px 16px 18px' }}>
          <div style={{
            position: 'relative', aspectRatio: '1.6 / 1',
            borderRadius: 20,
            background: 'linear-gradient(135deg, #1c1917 0%, #2c2826 100%)',
            color: '#fafaf9', padding: 22, overflow: 'hidden',
            boxShadow: '0 12px 30px rgba(28,25,23,0.25)',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{
              position: 'absolute', right: -40, top: -60,
              width: 200, height: 200, borderRadius: '50%',
              background: 'rgba(45, 212, 164, 0.18)', filter: 'blur(6px)',
              pointerEvents: 'none',
            }} />
            <div className="t-mini" style={{ color: 'rgba(250,250,249,0.7)', position: 'relative' }}>
              Карта для оплаты
            </div>
            <div style={{ flex: 1 }} />
            {/* last4 from API — no PAN/CVV, no cardholder name (T-81-07) */}
            <div className="t-h2" style={{
              color: '#fafaf9', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              letterSpacing: 2, fontSize: 20, marginBottom: 12, position: 'relative',
            }}>
              {cardData ? `•••• •••• •••• ${cardData.last4}` : '•••• •••• •••• ————'}
            </div>
            <div className="row-between" style={{ position: 'relative' }}>
              <div>
                <div className="t-mini" style={{ color: 'rgba(250,250,249,0.6)', fontSize: 9 }}>КАРТА</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>CLUBCORE</div>
              </div>
              <div>
                <div className="t-mini" style={{ color: 'rgba(250,250,249,0.6)', fontSize: 9 }}>ДО</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2,
                              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
                  {expiryStr}
                </div>
              </div>
              <div style={{
                width: 36, height: 22, borderRadius: 4,
                background: 'linear-gradient(135deg, #f59e0b, #dc2626)',
              }} />
            </div>
          </div>
        </div>

        {/* Autopay toggles — only «Авто-продление абонемента» remains (anti-feature removed per locked decision) */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Автоплатежи</div>
          <div className="card" style={{ padding: 0 }}>
            {/* Авто-продление абонемента — wired to PATCH /autopay with ФЗ-376 consent (T-81-06, T-81-08) */}
            <AutopayToggleRow
              label="Авто-продление абонемента"
              sub="Спишется за 3 дня до конца"
              enabled={cardData?.autopayEnabled ?? false}
              isPending={patchAutopay.isPending}
              onEnable={() => setAutopayConsentOpen(true)}
              onDisable={handleDisableAutopay}
            />
          </div>
          {autopayError && (
            <div className="t-small" style={{ color: 'var(--danger)', marginTop: 6, paddingLeft: 4 }}>
              {autopayError}
            </div>
          )}
        </div>

        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Действия</div>
          <div className="card" style={{ padding: 0 }}>
            <MiniActionRow icon="plus" label="Добавить новую карту" onClick={openPaymentMethods} />
            <Divider3 />
            <MiniActionRow icon="card" label="Изменить срок действия" onClick={openPaymentMethods} />
            <Divider3 />
            <MiniActionRow
              icon="alert"
              label="Отвязать карту"
              danger
              onClick={() => setUnbindConfirm(true)}
            />
          </div>
          {unbindError && (
            <div className="t-small" style={{ color: 'var(--danger)', marginTop: 6, paddingLeft: 4 }}>
              {unbindError}
            </div>
          )}
        </div>

        {/* Unbind confirmation modal */}
        {unbindConfirm && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 30,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            animation: 'ctx-fade 0.2s ease-out',
          }} onClick={() => setUnbindConfirm(false)}>
            <div onClick={(e) => e.stopPropagation()} style={{
              width: 'calc(100% - 24px)', margin: '0 12px 12px',
              background: 'var(--surface)', borderRadius: 20, padding: 20,
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
              animation: 'sheet-up 0.28s cubic-bezier(0.32, 0.72, 0.2, 1)',
            }}>
              <div className="t-h2" style={{ fontSize: 18 }}>Отвязать карту?</div>
              <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
                Автоплатежи отключатся. Записи и продление абонемента нужно будет оплачивать вручную.
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button onClick={() => setUnbindConfirm(false)} className="press" style={{
                  flex: 1, height: 46, borderRadius: 999, border: '0.5px solid var(--border-strong)',
                  background: 'transparent', color: 'var(--text)',
                  fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}>Отмена</button>
                <button
                  onClick={handleUnlinkConfirmed}
                  disabled={unlinkCard.isPending}
                  className="press"
                  style={{
                    flex: 1, height: 46, borderRadius: 999, border: 0,
                    background: 'var(--danger)', color: '#fff',
                    fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                    opacity: unlinkCard.isPending ? 0.7 : 1,
                  }}
                >
                  {unlinkCard.isPending ? 'Отвязываем…' : 'Отвязать'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ФЗ-376 autopay consent disclosure modal (T-81-06) */}
        {autopayConsentOpen && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 30,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            animation: 'ctx-fade 0.2s ease-out',
          }} onClick={() => setAutopayConsentOpen(false)}>
            <div onClick={(e) => e.stopPropagation()} style={{
              width: 'calc(100% - 24px)', margin: '0 12px 12px',
              background: 'var(--surface)', borderRadius: 20, padding: 20,
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
              animation: 'sheet-up 0.28s cubic-bezier(0.32, 0.72, 0.2, 1)',
            }}>
              <div className="t-h2" style={{ fontSize: 18 }}>Подключить автопродление?</div>
              {/* ФЗ-376 required disclosure: amount + periodicity + cancellation method */}
              <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)', lineHeight: 1.6 }}>
                Сумма списания — стоимость текущего тарифа. Списывается за 3 дня до окончания
                абонемента. Отключить можно в любой момент в настройках карты.
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button onClick={() => setAutopayConsentOpen(false)} className="press" style={{
                  flex: 1, height: 46, borderRadius: 999, border: '0.5px solid var(--border-strong)',
                  background: 'transparent', color: 'var(--text)',
                  fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}>
                  Отмена
                </button>
                <button
                  onClick={handleEnableAutopayWithConsent}
                  disabled={patchAutopay.isPending}
                  className="press"
                  style={{
                    flex: 2, height: 46, borderRadius: 999, border: 'none',
                    background: 'var(--accent)', color: '#06120c',
                    fontFamily: 'inherit', fontSize: 15, fontWeight: 700, cursor: 'pointer',
                    opacity: patchAutopay.isPending ? 0.7 : 1,
                  }}
                >
                  {patchAutopay.isPending ? 'Подключаем…' : 'Подключить'}
                </button>
              </div>
            </div>
          </div>
        )}

        <div style={{ padding: '14px 22px 30px' }}>
          <div className="t-small" style={{
            textAlign: 'center', color: 'var(--text-3)', lineHeight: 1.5,
          }}>
            Данные карты хранятся на стороне платёжного провайдера.
            Мы видим только последние 4 цифры.
          </div>
        </div>
      </div>
    </div>
  );
};

// Controlled autopay toggle row — wired to real usePatchAutopay + ФЗ-376 consent (PAYM-05)
function AutopayToggleRow({ label, sub, enabled, isPending, onEnable, onDisable }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{label}</div>
        {sub && <div className="t-small" style={{ marginTop: 2 }}>{sub}</div>}
      </div>
      <button
        aria-label={label}
        aria-checked={enabled}
        role="switch"
        disabled={isPending}
        onClick={() => { if (enabled) { void onDisable(); } else { onEnable(); } }}
        style={{
          width: 44, height: 26, borderRadius: 999, border: 0, padding: 0,
          background: enabled ? 'var(--accent)' : 'var(--border-strong)',
          cursor: isPending ? 'not-allowed' : 'pointer',
          position: 'relative', transition: 'background 0.15s',
          flexShrink: 0, opacity: isPending ? 0.6 : 1,
        }}
      >
        <span style={{
          position: 'absolute', top: 2, left: enabled ? 20 : 2,
          width: 22, height: 22, borderRadius: 999, background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.25)', transition: 'left 0.18s ease',
        }} />
      </button>
    </div>
  );
}

function ToggleRow({ label, sub, defaultOn }) {
  const [on, setOn] = React.useState(!!defaultOn);
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{label}</div>
        {sub && <div className="t-small" style={{ marginTop: 2 }}>{sub}</div>}
      </div>
      <button onClick={() => setOn(!on)} style={{
        width: 44, height: 26, borderRadius: 999, border: 0, padding: 0,
        background: on ? 'var(--accent)' : 'var(--border-strong)',
        cursor: 'pointer', position: 'relative', transition: 'background 0.15s',
        flexShrink: 0,
      }}>
        <span style={{
          position: 'absolute', top: 2, left: on ? 20 : 2,
          width: 22, height: 22, borderRadius: 999, background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.25)', transition: 'left 0.18s ease',
        }} />
      </button>
    </div>
  );
}

function MiniActionRow({ icon, label, danger, onClick }) {
  return (
    <button
      onClick={onClick}
      className="press"
      style={{
        appearance: 'none', border: 0, background: 'transparent', width: '100%',
        padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12,
        cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
        color: 'inherit',
      }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: danger ? 'var(--danger-soft)' : 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={icon} size={16} color={danger ? 'var(--danger)' : 'var(--text-2)'} strokeWidth={2} />
      </div>
      <div className="t-h3" style={{
        flex: 1, fontSize: 14, color: danger ? 'var(--danger)' : 'var(--text)',
      }}>{label}</div>
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </button>
  );
}

// ─── FAQ / Help ───────────────────────────────────────────────
const FAQ_ITEMS = [
  { q: 'Что входит в абонемент?', a: 'Зал, кардио-зона, групповые занятия по расписанию, сауна (для полугодового и годового тарифов). Тренер оплачивается отдельно.' },
  { q: 'Можно ли заморозить абонемент?', a: 'Да. Месячный — без заморозки, полугодовой — до 14 дней, годовой — до 30 дней. Активировать заморозку можно в чате с админом или на ресепшене.' },
  { q: 'Как отменить запись к тренеру?', a: 'За 4+ часа до начала — бесплатно через экран «Управление записью». За 1–4 часа — вернётся 50%. Позже — оплата сохраняется тренеру.' },
  { q: 'QR-код не работает на турникете', a: 'Проверь, что абонемент активен (на главном экране) и яркость экрана достаточная. Если не помогает — подойди к админу с приложением.' },
  { q: 'Как пригласить друга?', a: 'Профиль → «Приведи друга». Поделись кодом — друг получит скидку 1 000 ₽ на первый абонемент, а ты — 1 000 ₽ на следующее продление.' },
  { q: 'Можно ли вернуть деньги за абонемент?', a: 'Да, по российскому законодательству. Пиши в чат — рассчитаем сумму за вычетом фактически использованных дней.' },
  { q: 'Где парковка?', a: 'Подземный паркинг с торца здания, въезд со двора. Для членов клуба — первые 2 часа бесплатно, потом 200 ₽/ч.' },
  { q: 'Дресс-код', a: 'Спортивная одежда и сменная обувь обязательны. Обувь с чёрной подошвой не пускаем — оставляет полосы на полу. Полотенце на тренажёр — must.' },
];

export const FAQSheet = ({ onClose, onOpenChat }) => {
  const [open, setOpen] = React.useState(-1);
  const [query, setQuery] = React.useState('');

  const filtered = FAQ_ITEMS.filter(item =>
    !query ||
    item.q.toLowerCase().includes(query.toLowerCase()) ||
    item.a.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Помощь" onClose={onClose} />

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Search */}
        <div style={{ padding: '4px 16px 14px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'var(--surface)', borderRadius: 'var(--r-pill)',
            border: '0.5px solid var(--border)',
            padding: '0 14px', height: 44,
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
              <circle cx="11" cy="11" r="7" stroke="var(--text-3)" strokeWidth="1.8" fill="none" />
              <path d="M16 16l4 4" stroke="var(--text-3)" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Поиск по вопросам"
              style={{
                flex: 1, border: 0, outline: 0, background: 'transparent',
                color: 'var(--text)', fontFamily: 'inherit', fontSize: 15,
              }}
            />
          </div>
        </div>

        {/* Quick contacts */}
        <div style={{ padding: '0 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <ContactTile icon="chat" big="Написать" sub="в админ-чат" onClick={onOpenChat} />
          <ContactTile icon="phone" big="Позвонить" sub="ресепшен" onClick={() => { window.location.href = 'tel:+74951234567'; }} />
        </div>

        {/* FAQ list */}
        <div style={{ padding: '0 16px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
            Частые вопросы
          </div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {filtered.length === 0 ? (
              <div style={{ padding: 28, textAlign: 'center' }}>
                <div className="t-h3" style={{ fontSize: 15 }}>Ничего не нашлось</div>
                <div className="t-small" style={{ marginTop: 6 }}>Попробуй другие слова или напиши в чат.</div>
              </div>
            ) : filtered.map((item, i) => (
              <React.Fragment key={item.q}>
                {i > 0 && <Divider3 />}
                <FaqRow
                  q={item.q} a={item.a}
                  open={open === i}
                  onToggle={() => setOpen(open === i ? -1 : i)}
                />
              </React.Fragment>
            ))}
          </div>
        </div>

        <div style={{ padding: '4px 22px 30px' }}>
          <div className="t-small" style={{
            textAlign: 'center', color: 'var(--text-3)', lineHeight: 1.5,
          }}>
            Не нашли ответ?<br />
            Пиши в чат — ответим в течение 10 минут с 8:00 до 22:00.
          </div>
        </div>
      </div>
    </div>
  );
};

function ContactTile({ icon, big, sub, onClick }) {
  return (
    <button onClick={onClick} className="press" style={{
      borderRadius: 'var(--r-lg)', padding: 14,
      display: 'flex', flexDirection: 'column', gap: 8,
      cursor: 'pointer', textAlign: 'left', color: 'var(--text)',
      background: 'var(--surface)', border: '0.5px solid var(--border)',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: 'var(--accent-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name={icon} size={18} color="var(--accent-deep)" />
      </div>
      <div>
        <div className="t-h3" style={{ fontSize: 15 }}>{big}</div>
        <div className="t-small">{sub}</div>
      </div>
    </button>
  );
}

function FaqRow({ q, a, open, onToggle }) {
  return (
    <div>
      <button onClick={onToggle} style={{
        width: '100%', padding: '14px 14px', background: 'transparent', border: 0,
        display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
        fontFamily: 'inherit', textAlign: 'left', color: 'var(--text)',
      }}>
        <div className="t-h3" style={{ flex: 1, fontSize: 14 }}>{q}</div>
        <div style={{
          transform: `rotate(${open ? 90 : 0}deg)`, transition: 'transform 0.2s',
          flexShrink: 0,
        }}>
          <Icon name="chevronRight" size={16} color="var(--text-3)" />
        </div>
      </button>
      {open && (
        <div className="fade-up" style={{
          padding: '0 14px 14px 14px',
        }}>
          <div className="t-body" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
            {a}
          </div>
        </div>
      )}
    </div>
  );
}
