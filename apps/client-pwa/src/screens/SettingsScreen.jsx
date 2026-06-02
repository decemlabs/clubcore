import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useClientMe } from '@/data';
import { useAuth } from '@/context/AuthContext.jsx';

// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// Two UI elements are fully built but gated OFF here. Flip a flag to reveal.
// See ProfileScreen.jsx PROFILE_FEATURE_FLAGS for the master flag object.
//
//  • linkedCard   — "Привязанная карта •••• 4821" row (needs card-on-file API)
//  • tenureBadge  — "PREMIUM · N ЛЕТ" identity badge (needs tier + tenure from API)
const SETTINGS_FEATURE_FLAGS = {
  linkedCard:  false,
  tenureBadge: false,
};

// ─── Notification prefs persistence (D-74-04) ─────────────────────────────
// Local-only: nothing sent to server. Survives reload via localStorage.
const NOTIF_STORAGE_KEY = 'clubcore:notif:v1';
const NOTIF_DEFAULTS = { promo: true, schedule: true, trainer: true, sound: false };

// ─── Settings screen ──────────────────────────────────────────────────────
export const SettingsScreen = ({
  tweaks,
  setTweak,
  onOpenPlans,
  onOpenPersonalData,
  onOpenCard,
  onOpenFAQ,
}) => {
  const navigate = useNavigate();
  const { data: me } = useClientMe();
  const { logout } = useAuth();

  // Notification toggles — init from localStorage with graceful fallback (T-74-03)
  const [notif, setNotif] = React.useState(() => {
    try {
      return { ...NOTIF_DEFAULTS, ...JSON.parse(localStorage.getItem(NOTIF_STORAGE_KEY) || '{}') };
    } catch {
      return NOTIF_DEFAULTS; /* noop */
    }
  });

  const setNotifKey = (key, val) => {
    const next = { ...notif, [key]: val };
    setNotif(next);
    try {
      localStorage.setItem(NOTIF_STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* noop */
    }
  };

  // Back: prefer history.back(); fall back to /profile (D-74-01)
  const handleBack = () => {
    if (window.history.length > 1) window.history.back();
    else navigate('/profile');
  };

  // Identity — graceful blanks, no hardcoded human names
  const initials = [me?.firstName, me?.lastName]
    .filter(Boolean)
    .map((s) => s[0])
    .join('')
    .toUpperCase() || '?';
  const fullName = [me?.firstName, me?.lastName].filter(Boolean).join(' ') || '';

  return (
    <div className="page">
      <StatusBar />

      {/* Header with back button — mirrors Settings.html .header/.hbtn/.htitle */}
      <div
        style={{
          position: 'relative',
          flexShrink: 0,
          height: 52,
          padding: '0 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <button
          onClick={handleBack}
          aria-label="Назад"
          className="press"
          style={{
            width: 36,
            height: 36,
            borderRadius: 999,
            border: '0.5px solid var(--border)',
            background: 'var(--surface)',
            boxShadow: 'var(--sh-1)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text)',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
          }}
        >
          <Icon name="chevronLeft" size={18} color="var(--text)" strokeWidth={2.2} />
        </button>

        <span
          className="t-h3"
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: 17,
            fontWeight: 700,
            letterSpacing: '-0.3px',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          Настройки
        </span>

        <div style={{ width: 36, flexShrink: 0 }} />
      </div>

      {/* Scrollable body */}
      <div className="scroller" style={{ padding: '6px 16px 28px' }}>

        {/* Identity strip */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '8px 4px 18px',
          }}
        >
          <Avatar initials={initials} size={62} />
          <div style={{ flex: 1, minWidth: 0 }}>
            {fullName ? (
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 750,
                  letterSpacing: '-0.5px',
                  lineHeight: 1.1,
                }}
              >
                {fullName}
              </div>
            ) : (
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 750,
                  letterSpacing: '-0.5px',
                  lineHeight: 1.1,
                  color: 'var(--text-3)',
                }}
              >
                —
              </div>
            )}
            {/* PREMIUM / tenure badge — gated (D-74-04/D-74-05) */}
            {SETTINGS_FEATURE_FLAGS.tenureBadge && (
              <span
                style={{
                  marginTop: 6,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  height: 22,
                  padding: '0 9px 0 8px',
                  borderRadius: 999,
                  background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
                  color: 'var(--accent-deep)',
                  fontSize: 10.5,
                  fontWeight: 700,
                  letterSpacing: 0.5,
                }}
              >
                PREMIUM
              </span>
            )}
          </div>
        </div>

        {/* ── Appearance ───────────────────────────────────────────── */}
        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
          Внешний вид
        </div>
        <div className="card" style={{ padding: 4 }}>
          <div
            style={{
              padding: '14px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div style={{ flex: 1 }} className="t-h3">
              Тема
            </div>
            <div className="seg" style={{ padding: 3 }}>
              <button
                className={`seg-item ${(tweaks?.theme || 'light') === 'light' ? 'active' : ''}`}
                onClick={() => setTweak('theme', 'light')}
                style={{ padding: '0 14px' }}
              >
                Светлая
              </button>
              <button
                className={`seg-item ${tweaks?.theme === 'dark' ? 'active' : ''}`}
                onClick={() => setTweak('theme', 'dark')}
                style={{ padding: '0 14px' }}
              >
                Тёмная
              </button>
            </div>
          </div>
        </div>

        {/* ── Notifications ─────────────────────────────────────────── */}
        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 4px 8px' }}>
          Уведомления
        </div>
        <div className="card" style={{ padding: 4 }}>
          <SettingRow
            label="Акции и скидки"
            value={notif.promo}
            onChange={(v) => setNotifKey('promo', v)}
          />
          <Divider2 />
          <SettingRow
            label="Изменения расписания"
            value={notif.schedule}
            onChange={(v) => setNotifKey('schedule', v)}
          />
          <Divider2 />
          <SettingRow
            label="Сообщения от тренера"
            value={notif.trainer}
            onChange={(v) => setNotifKey('trainer', v)}
          />
          <Divider2 />
          <SettingRow
            label="Звук уведомлений"
            value={notif.sound}
            onChange={(v) => setNotifKey('sound', v)}
          />
        </div>

        {/* ── Account ───────────────────────────────────────────────── */}
        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 4px 8px' }}>
          Аккаунт
        </div>
        <div className="card" style={{ padding: 4 }}>
          <NavRow label="Тариф и подписка" value="Изменить" onClick={onOpenPlans} />
          {/* Привязанная карта — BUILT, HIDDEN (needs card-on-file API) */}
          {SETTINGS_FEATURE_FLAGS.linkedCard && (
            <>
              <Divider2 />
              <NavRow label="Привязанная карта" value="•••• 4821" onClick={onOpenCard} />
            </>
          )}
          <Divider2 />
          <NavRow label="Личные данные" onClick={onOpenPersonalData} />
          <Divider2 />
          <NavRow label="Помощь и FAQ" onClick={onOpenFAQ} />
        </div>

        {/* ── Logout ────────────────────────────────────────────────── */}
        <button
          className="btn"
          onClick={() => {
            void logout();
          }}
          style={{
            marginTop: 22,
            width: '100%',
            height: 50,
            background: 'transparent',
            color: 'var(--danger)',
            border: '0.5px solid var(--border-strong)',
          }}
        >
          <Icon name="logout" size={18} color="var(--danger)" strokeWidth={2} />
          Выйти из аккаунта
        </button>

        {/* ── Version ───────────────────────────────────────────────── */}
        <div
          className="t-small"
          style={{ textAlign: 'center', color: 'var(--text-3)', marginTop: 16 }}
        >
          Версия 2.4.1 · Мой зал
        </div>
      </div>
    </div>
  );
};

// ─── Helper components (copied from ProfileScreen.jsx) ─────────────────────

function SettingRow({ label, value, onChange }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }} className="t-h3">
        {label}
      </div>
      <button
        onClick={() => onChange(!value)}
        style={{
          width: 44,
          height: 26,
          borderRadius: 999,
          border: 0,
          padding: 0,
          background: value ? 'var(--accent)' : 'var(--border-strong)',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background 0.15s',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: value ? 20 : 2,
            width: 22,
            height: 22,
            borderRadius: 999,
            background: '#fff',
            boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
            transition: 'left 0.18s ease',
          }}
        />
      </button>
    </div>
  );
}

function NavRow({ label, value, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '14px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        cursor: 'pointer',
      }}
    >
      <div style={{ flex: 1 }} className="t-h3">
        {label}
      </div>
      {value && (
        <div className="t-small" style={{ color: 'var(--text-2)' }}>
          {value}
        </div>
      )}
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </div>
  );
}

function Divider2() {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 14 }} />;
}
