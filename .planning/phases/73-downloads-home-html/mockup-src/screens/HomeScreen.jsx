import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { QRPattern } from '@/components/QRPattern.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { GYM_INFO, NOTIFICATIONS, TRAINER_CANCEL, UPCOMING_BOOKING } from '@/data';
import { formatCountdown, useCountdown } from '@/hooks/useCountdown.js';
import { getSubInfo } from '@/utils/subInfo.js';

// Open/closed status chip — shown in home header, opens GymInfoSheet
export function GymStatusPill({ onClick }) {
  const g = (typeof GYM_INFO !== 'undefined') ? GYM_INFO : null;
  if (!g) return null;
  const open = g.status.open;
  const label = open ? `Открыто до ${g.status.until}` : `Закрыто · откроемся в ${g.hours[(g.todayIdx + 1) % 7].open}`;
  return (
    <button
      onClick={onClick}
      className="press"
      style={{
        height: 30, padding: '0 12px 0 10px',
        border: '0.5px solid var(--border)',
        background: 'var(--surface)', borderRadius: 999,
        display: 'inline-flex', alignItems: 'center', gap: 7,
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >
      <span style={{
        width: 7, height: 7, borderRadius: 999,
        background: open ? '#10b981' : 'var(--text-3)',
        boxShadow: open ? '0 0 0 3px rgba(16,185,129,0.18)' : 'none',
        animation: open ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
        flexShrink: 0,
      }} />
      <span style={{
        fontSize: 12, fontWeight: 600, letterSpacing: -0.1,
        color: 'var(--text-2)', whiteSpace: 'nowrap',
        overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {label}
      </span>
      <Icon name="chevronRight" size={12} color="var(--text-3)" strokeWidth={2.2} />
    </button>
  );
}

// Unified hero header card — gym title + actions + live status widgets
export function HomeHeroCard({ userName, unread, heroStyle = 'classic', onOpenGymInfo, onOpenNotifications }) {
  const g = (typeof GYM_INFO !== 'undefined') ? GYM_INFO : null;
  const open = g ? g.status.open : true;
  const openLabel = open ? `Открыт до ${g ? g.status.until : '23:00'}` : 'Закрыт';
  const initial = (userName || 'Г').trim().charAt(0).toUpperCase();

  const levels = [
    { h: [42, 60, 30, 38], t: 'Свободно',   c: 'var(--accent)' },
    { h: [58, 80, 52, 46], t: 'Умеренно',   c: '#e9a23b' },
    { h: [80, 96, 86, 72], t: 'Многолюдно', c: '#ef6f53' },
  ];
  const [lvl, setLvl] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => {
      setLvl(p => (p + (Math.random() < 0.5 ? 1 : 2)) % levels.length);
    }, 4000);
    return () => clearInterval(id);
  }, []);
  const L = levels[lvl];

  const labelStyle = {
    fontSize: 10, fontWeight: 700, letterSpacing: 0.4,
    textTransform: 'uppercase', color: 'var(--text-3)', lineHeight: 1,
  };
  const valueStyle = {
    display: 'flex', alignItems: 'center', gap: 7,
    fontSize: 14, fontWeight: 700, color: 'var(--text)', letterSpacing: -0.2, lineHeight: 1,
  };

  const greeting = (() => {
    const h = 9;
    if (h < 5) return 'Доброй ночи';
    if (h < 12) return 'Доброе утро';
    if (h < 18) return 'Добрый день';
    return 'Добрый вечер';
  })();

  // ── shared pieces ───────────────────────────────────────────────
  const bellBtn = (
    <button onClick={onOpenNotifications} className="press" aria-label="Уведомления" style={{
      position: 'relative', width: 38, height: 38, borderRadius: 12,
      border: '0.5px solid var(--border)', background: 'var(--surface)', boxShadow: 'var(--sh-1)',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
    }}>
      <Icon name="bell" size={19} color="var(--text)" />
      {unread > 0 && (
        <span style={{
          position: 'absolute', top: 8, right: 9, width: 7, height: 7, borderRadius: 999,
          background: '#f43f5e', border: '2px solid var(--surface)',
        }} />
      )}
    </button>
  );
  const avatarEl = (size = 38) => (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <Avatar initials={initial} bg="var(--accent)" color="#053a2b" size={size} />
      <span style={{
        position: 'absolute', right: -2, bottom: -2, width: size * 0.29, height: size * 0.29, borderRadius: 999,
        background: '#10b981', border: '2.5px solid var(--surface)',
      }} />
    </div>
  );
  const openDot = (
    <span style={{
      width: 9, height: 9, borderRadius: 999, flexShrink: 0,
      background: open ? '#10b981' : 'var(--text-3)',
      boxShadow: open ? '0 0 0 3px rgba(16,185,129,0.2)' : 'none',
      animation: open ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
    }} />
  );
  const bars = (h = 15) => (
    <span style={{ display: 'flex', alignItems: 'flex-end', gap: 2.5, height: h }}>
      {L.h.map((bh, i) => (
        <span key={i} style={{
          width: 3, borderRadius: 2, height: bh + '%',
          background: i < 2 ? L.c : 'var(--border-strong)',
          transition: 'height 0.55s cubic-bezier(0.32,0.72,0.2,1), background 0.45s',
        }} />
      ))}
    </span>
  );
  const gymTitle = (size = 18) => (
    <button onClick={onOpenGymInfo} className="press" style={{
      appearance: 'none', border: 0, background: 'transparent', padding: 0,
      textAlign: 'left', cursor: 'pointer', minWidth: 0, fontFamily: 'inherit', color: 'var(--text)',
    }}>
      <div style={{ fontSize: size, fontWeight: 750, letterSpacing: -0.4, lineHeight: 1.05 }}>Мой зал</div>
      <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-2)' }}>
        Тверская
      </div>
    </button>
  );

  const cardStyle = {
    position: 'relative', background: 'var(--surface)',
    border: '0.5px solid var(--border)', borderRadius: 20, boxShadow: 'var(--sh-2)',
  };
  const wrap = (inner, pad) => (
    <div style={{ padding: '4px 16px 16px' }}>
      <div className="fade-up" style={{ ...cardStyle, padding: pad }}>{inner}</div>
    </div>
  );

  // pieces for color/dark variants
  const glassChip = { height: 26, padding: '0 11px', borderRadius: 999, fontSize: 12, fontWeight: 600, background: 'rgba(255,255,255,0.15)', border: '0.5px solid rgba(255,255,255,0.24)', color: '#fff', display: 'inline-flex', alignItems: 'center', gap: 6 };
  const whiteDot = <span style={{ width: 7, height: 7, borderRadius: 999, background: '#fff', boxShadow: '0 0 0 3px rgba(255,255,255,0.25)' }} />;
  const whiteBars = (
    <span style={{ display: 'flex', alignItems: 'flex-end', gap: 2.5, height: 13 }}>
      {L.h.map((bh, i) => (<span key={i} style={{ width: 3, borderRadius: 2, height: bh + '%', background: i < 2 ? '#fff' : 'rgba(255,255,255,0.4)', transition: 'height 0.55s cubic-bezier(0.32,0.72,0.2,1)' }} />))}
    </span>
  );
  const glassBell = (badgeBorder) => (
    <button onClick={onOpenNotifications} className="press" aria-label="Уведомления" style={{
      position: 'relative', width: 38, height: 38, borderRadius: 12,
      border: '0.5px solid rgba(255,255,255,0.24)', background: 'rgba(255,255,255,0.13)',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', flexShrink: 0,
    }}>
      <Icon name="bell" size={19} color="#fff" />
      {unread > 0 && <span style={{ position: 'absolute', top: 8, right: 9, width: 7, height: 7, borderRadius: 999, background: '#f43f5e', border: '2px solid ' + badgeBorder }} />}
    </button>
  );
  const lightAvatar = (badgeBorder) => (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <Avatar initials={initial} bg="#ffffff" color="var(--accent-deep)" size={38} />
      <span style={{ position: 'absolute', right: -2, bottom: -2, width: 11, height: 11, borderRadius: 999, background: '#34d399', border: '2.5px solid ' + badgeBorder }} />
    </div>
  );
  const gymTitleWhite = (
    <button onClick={onOpenGymInfo} className="press" style={{ appearance: 'none', border: 0, background: 'transparent', padding: 0, textAlign: 'left', cursor: 'pointer', minWidth: 0, fontFamily: 'inherit', color: '#fff' }}>
      <div style={{ fontSize: 18, fontWeight: 750, letterSpacing: -0.4, lineHeight: 1.05 }}>Мой зал</div>
      <div style={{ marginTop: 2, fontSize: 12, color: 'rgba(255,255,255,0.82)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        <Icon name="mapPin" size={13} color="rgba(255,255,255,0.9)" strokeWidth={2} />Тверская
      </div>
    </button>
  );

  // ── Variant: Banner — accent-coloured header band ───────────────
  if (heroStyle === 'banner') {
    return (
      <div style={{ padding: '4px 16px 16px' }}>
        <div className="fade-up" style={{
          position: 'relative', overflow: 'hidden', borderRadius: 20, padding: '14px 16px', color: '#fff',
          background: 'linear-gradient(150deg, var(--accent) 0%, var(--accent-deep) 100%)', boxShadow: 'var(--sh-2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            {gymTitleWhite}
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{glassBell('var(--accent-deep)')}{lightAvatar('var(--accent-deep)')}</div>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <span style={{ ...glassChip, flex: 1, minWidth: 0, justifyContent: 'center' }}>{whiteDot}{openLabel}</span>
            <span style={{ ...glassChip, flex: 1, minWidth: 0, justifyContent: 'center' }}>{whiteBars}{L.t}</span>
          </div>
        </div>
      </div>
    );
  }

  // ── Variant: Dark — matte header echoing the membership card ────
  if (heroStyle === 'dark') {
    return (
      <div style={{ padding: '4px 16px 16px' }}>
        <div className="fade-up" style={{
          position: 'relative', overflow: 'hidden', borderRadius: 20, padding: '14px 16px', color: '#f3f1ea',
          background: 'linear-gradient(155deg, #23271f 0%, #14170f 100%)',
          border: '0.5px solid rgba(255,255,255,0.10)', boxShadow: 'var(--sh-2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            {gymTitleWhite}
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
              {glassBell('#181b14')}
              <div style={{ position: 'relative', flexShrink: 0 }}>
                <Avatar initials={initial} bg="var(--accent)" color="#053a2b" size={38} />
                <span style={{ position: 'absolute', right: -2, bottom: -2, width: 11, height: 11, borderRadius: 999, background: '#34d399', border: '2.5px solid #181b14' }} />
              </div>
            </div>
          </div>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '0.5px solid rgba(255,255,255,0.12)', display: 'flex', gap: 18, flexWrap: 'wrap' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 600 }}>{openDot}{openLabel}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 600 }}>{whiteBars}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span></span>
          </div>
        </div>
      </div>
    );
  }

  // ── Variant: Tiles — identity row + two stat tiles ──────────────
  if (heroStyle === 'tiles') {
    const tile = { background: 'var(--surface-2)', border: '0.5px solid var(--border)', borderRadius: 14, padding: '10px 12px', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 7 };
    return wrap(
      <>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          {gymTitle(18)}
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{bellBtn}{avatarEl(38)}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <div style={tile}>
            <span style={{ ...labelStyle, display: 'inline-flex', alignItems: 'center', gap: 5 }}><Icon name="clock" size={12} color="var(--text-3)" strokeWidth={2} />Зал</span>
            <span style={{ ...valueStyle, fontSize: 13.5 }}>{openDot}{openLabel}</span>
          </div>
          <div style={tile}>
            <span style={labelStyle}>Наполненность</span>
            <span style={{ ...valueStyle, fontSize: 13.5 }}>{bars(14)}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span></span>
          </div>
        </div>
      </>,
      '11px 14px',
    );
  }

  // ── Variant: Minimal — borderless & airy ────────────────────────
  if (heroStyle === 'minimal') {
    return (
      <div style={{ padding: '8px 20px 14px' }}>
        <div className="fade-up" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <button onClick={onOpenGymInfo} className="press" style={{ appearance: 'none', border: 0, background: 'transparent', padding: 0, textAlign: 'left', cursor: 'pointer', minWidth: 0, fontFamily: 'inherit', color: 'var(--text)' }}>
            <div style={{ fontSize: 23, fontWeight: 750, letterSpacing: -0.6, lineHeight: 1.05 }}>Мой зал</div>
            <div style={{ marginTop: 3, fontSize: 12.5, color: 'var(--text-2)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <Icon name="mapPin" size={13} color="var(--accent-deep)" strokeWidth={2} />Тверская
            </div>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{bellBtn}{avatarEl(40)}</div>
        </div>
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-2)', fontSize: 13, fontWeight: 600 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>{openDot}{openLabel}</span>
          <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-3)' }} />
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>{bars(13)}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span></span>
        </div>
      </div>
    );
  }

  // ── Variant: Compact — single dense row + thin status line ──────
  if (heroStyle === 'compact') {
    return wrap(
      <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          {avatarEl(40)}
          {gymTitle(16)}
          <div style={{ flex: 1 }} />
          {bellBtn}
        </div>
        <div style={{
          marginTop: 10, paddingTop: 10, borderTop: '0.5px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        }}>
          <span style={{ ...valueStyle, fontSize: 13 }}>{openDot}{openLabel}</span>
          <span style={{ width: 0.5, height: 14, background: 'var(--border)' }} />
          <span style={{ ...valueStyle, fontSize: 13 }}>{bars(14)}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span></span>
        </div>
      </>,
      '12px 14px',
    );
  }

  // ── Variant: Greeting — personalized header + status strip ──────
  if (heroStyle === 'greeting') {
    return wrap(
      <>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: 'var(--text-3)', fontWeight: 500, letterSpacing: -0.1 }}>{greeting},</div>
            <div style={{ fontSize: 22, fontWeight: 750, letterSpacing: -0.5, lineHeight: 1.1, marginTop: 1 }}>{userName}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{bellBtn}{avatarEl(38)}</div>
        </div>
        <button onClick={onOpenGymInfo} className="press" style={{
          width: '100%', marginTop: 12, appearance: 'none', cursor: 'pointer', fontFamily: 'inherit',
          background: 'var(--surface-2)', border: '0.5px solid var(--border)', borderRadius: 14,
          padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text)',
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13.5, letterSpacing: -0.2 }}>
            <Icon name="mapPin" size={14} color="var(--accent-deep)" strokeWidth={2} />
            Мой зал · Тверская
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: 'var(--text-2)' }}>
            {openDot}{open ? `до ${g ? g.status.until : '23:00'}` : 'Закрыт'}
          </span>
          <span style={{ width: 0.5, height: 14, background: 'var(--border)', margin: '0 2px' }} />
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600 }}>
            {bars(13)}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span>
          </span>
        </button>
      </>,
      '12px 14px',
    );
  }

  // ── Variant: Spotlight — occupancy as the focal element ─────────
  if (heroStyle === 'spotlight') {
    const pctFull = lvl === 0 ? 34 : lvl === 1 ? 64 : 88;
    return wrap(
      <>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          {gymTitle(18)}
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{bellBtn}{avatarEl(38)}</div>
        </div>
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '0.5px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <span style={labelStyle}>Наполненность сейчас</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: 'var(--text-2)' }}>
              {openDot}{openLabel}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10 }}>
            <span style={{ fontSize: 19, fontWeight: 750, letterSpacing: -0.4, color: L.c, transition: 'color 0.4s', whiteSpace: 'nowrap' }}>{L.t}</span>
            <div style={{ flex: 1, height: 8, borderRadius: 999, background: 'var(--surface-2)', border: '0.5px solid var(--border)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: pctFull + '%', borderRadius: 999, background: L.c, transition: 'width 0.6s cubic-bezier(0.32,0.72,0.2,1), background 0.45s' }} />
            </div>
          </div>
        </div>
      </>,
      '12px 14px',
    );
  }

  // ── Variant: Classic (default) ──────────────────────────────────
  return wrap(
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {gymTitle(18)}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>{bellBtn}{avatarEl(38)}</div>
      </div>
      <div style={{ marginTop: 9, paddingTop: 9, borderTop: '0.5px solid var(--border)', display: 'flex' }}>
        <div style={{ flex: 1, paddingRight: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={labelStyle}>Зал</span>
          <span style={{ ...valueStyle, height: 16, whiteSpace: 'nowrap' }}>{openDot}{openLabel}</span>
        </div>
        <div style={{ flex: 1, paddingLeft: 14, borderLeft: '0.5px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={labelStyle}>Наполненность</span>
          <span style={{ ...valueStyle, height: 16, whiteSpace: 'nowrap' }}>{bars(15)}<span style={{ color: L.c, transition: 'color 0.4s' }}>{L.t}</span></span>
        </div>
      </div>
    </>,
    '11px 14px 10px',
  );
}

export const HomeScreen = ({ tweaks, onOpenQR, onOpenPlans, onOpenManage, onOpenReferral, onOpenGymInfo, onOpenNotifications, onTab, setTweak }) => {
  const sub = getSubInfo(tweaks.subState);
  const variant = tweaks.homeVariant || 'classic';
  const userName = tweaks.userName || 'Саша';
  const isEmpty = tweaks.dataMode === 'empty';
  const trainerCancelled = tweaks.gymEvent === 'trainer-cancelled';
  const unread = isEmpty ? 0 : NOTIFICATIONS.filter(n => n.unread).length;
  const [showToast, setShowToast] = React.useState(false);

  const greeting = (() => {
    const h = 9; // demo time
    if (h < 5) return 'Доброй ночи';
    if (h < 12) return 'Доброе утро';
    if (h < 18) return 'Привет';
    return 'Добрый вечер';
  })();

  const subTone = sub.tone === 'ok' ? 'chip-accent' : sub.tone === 'warn' ? 'chip-warn' : 'chip-danger';
  const fillTone = sub.tone === 'ok' ? '' : sub.tone === 'warn' ? 'warn' : 'danger';
  const pct = Math.max(2, Math.min(100, (sub.daysLeft / sub.total) * 100));

  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => {
          setShowToast(true);
          setTimeout(() => setShowToast(false), 2400);
          return new Promise(r => setTimeout(r, 700));
        }}
      >
        {showToast && <div className="ptr-toast">Обновлено · сейчас</div>}
        {/* Hero header — unified card */}
        <HomeHeroCard
          userName={userName}
          unread={unread}
          heroStyle={tweaks.heroStyle || 'classic'}
          onOpenGymInfo={onOpenGymInfo}
          onOpenNotifications={onOpenNotifications}
        />

        {variant === 'classic' && <HomeClassic isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} userName={userName} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} subCardStyle={tweaks.subCardStyle || 'spot'} />}
        {variant === 'qr-hero' && <HomeQrHero isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} />}
        {variant === 'minimal' && <HomeMinimal isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} />}

        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );

  function HomePullToRefreshScroller({ children }) {
    return (
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => {
          setShowToast(true);
          setTimeout(() => setShowToast(false), 2400);
          return new Promise(r => setTimeout(r, 700));
        }}
      >
        {children}
      </PullToRefresh>
    );
  }
};

// Compact branded spot illustration for the "first booking" prompt
function BookSpot() {
  return (
    <div style={{ position: 'relative', width: 56, height: 52, flexShrink: 0 }}>
      {/* halo */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)',
        width: 50, height: 50, borderRadius: '50%',
        background: 'radial-gradient(circle, color-mix(in oklab, var(--accent) 22%, transparent) 0%, transparent 66%)',
      }} />
      {/* dashed ring */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)',
        width: 50, height: 50, borderRadius: '50%',
        border: '1px dashed color-mix(in oklab, var(--text) 55%, transparent)', opacity: 0.55,
      }} />
      {/* white scene card with a dumbbell glyph */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%,-50%) rotate(-5deg)', transformOrigin: 'center',
        width: 38, height: 32, borderRadius: 10, background: 'var(--surface)',
        border: '0.5px solid var(--border)',
        boxShadow: '0 6px 14px rgba(28,25,23,0.14), 0 1px 3px rgba(28,25,23,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2,
        animation: 'book-scene-in 0.46s cubic-bezier(0.32,1.6,0.32,1) both',
      }}>
        <svg width={22} height={22} viewBox="0 0 24 24" fill="none"
             stroke="var(--accent-deep)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 9v6M8 7v10M16 7v10M19 9v6M8 12h8" />
        </svg>
      </div>
      {/* floating accent chips */}
      <span style={{
        position: 'absolute', right: 3, top: 3, width: 7, height: 7, borderRadius: 2,
        background: 'var(--accent-deep)', zIndex: 1,
        animation: 'book-float 3.4s ease-in-out infinite',
      }} />
      <span style={{
        position: 'absolute', left: 2, bottom: 7, width: 5, height: 5, borderRadius: '50%',
        background: 'var(--accent)', zIndex: 1,
        animation: 'book-float 3.4s ease-in-out infinite', animationDelay: '0.8s',
      }} />
      <style>{`
        @keyframes book-scene-in {
          0% { transform: translate(-50%,-50%) rotate(-5deg) scale(0.5); opacity: 0; }
          60% { transform: translate(-50%,-50%) rotate(-5deg) scale(1.06); }
          100% { transform: translate(-50%,-50%) rotate(-5deg) scale(1); opacity: 1; }
        }
        @keyframes book-float {
          0%, 100% { transform: translateY(0) rotate(0); }
          50% { transform: translateY(-5px) rotate(10deg); }
        }
      `}</style>
    </div>
  );
}

// Variant A: Classic — subscription card + QR button + actions + feed
export function HomeClassic({ isEmpty, sub, subTone, fillTone, pct, userName, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled, subCardStyle }) {
  return (
    <>
      {/* Trainer cancelled — strong alert */}
      {trainerCancelled && <TrainerCancelCard onTab={onTab} />}

      {/* Subscription card — already communicates the expired state + renew CTA */}
      <div style={{ padding: '0 16px 12px' }}>
        {subCardStyle === 'ring'
          ? <SubCardPremium sub={sub} pct={pct} onOpenPlans={onOpenPlans} />
          : <SubCardSpot sub={sub} pct={pct} userName={userName} onOpenPlans={onOpenPlans} />}
      </div>

      {/* Upcoming booking — tappable to manage */}
      {!isEmpty ? (
        <UpcomingCard onClick={onOpenManage} onCancel={onOpenManage} />
      ) : (
        <div style={{ padding: '0 16px 12px' }}>
          <button
            onClick={() => onTab('book')}
            className="press card"
            style={{
              appearance: 'none', cursor: 'pointer', textAlign: 'left', width: '100%',
              display: 'flex', alignItems: 'stretch', gap: 0, padding: 0, overflow: 'hidden',
              color: 'var(--text)',
            }}
          >
            <div style={{ width: 4, background: 'var(--accent)', flexShrink: 0 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 13, flex: 1, minWidth: 0 }}>
              <BookSpot />
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                <span className="t-h3" style={{ fontSize: 15.5, letterSpacing: -0.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Запишись на тренировку
                </span>
                <span className="t-small" style={{ color: 'var(--text-2)' }}>
                  Первая — со скидкой <b style={{ color: 'var(--accent-deep)', fontWeight: 700 }}>−30%</b>
                </span>
              </div>
              <span style={{ flexShrink: 0, display: 'inline-flex' }}>
                <Icon name="chevronRight" size={18} color="var(--text-3)" strokeWidth={2.2} />
              </span>
            </div>
          </button>
        </div>
      )}

      {/* QR pass — big primary action */}
      <div style={{ padding: '4px 16px 12px' }}>
        <button onClick={onOpenQR} className="press" style={{
          width: '100%', border: 0, background: 'var(--text)', color: 'var(--bg)',
          borderRadius: 'var(--r-xl)', padding: '20px 22px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          cursor: 'pointer', textAlign: 'left',
        }}>
          <div>
            <div className="t-mini" style={{ color: 'var(--text-3)', opacity: 0.8 }}>Пропуск в зал</div>
            <div className="t-h2" style={{ color: 'var(--bg)', marginTop: 4 }}>Открыть QR-код</div>
            <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 4 }}>Покажи на турникете</div>
          </div>
          <div style={{
            width: 64, height: 64, borderRadius: 16,
            background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="qr" size={36} color="#0a0a0a" strokeWidth={1.6} />
          </div>
        </button>
      </div>

      {/* Quick actions */}
      <div style={{ padding: '0 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <BookTile onClick={() => onTab('book')} />
        <ChatTile onClick={() => onTab('chat')} badge={2} />
      </div>

      {/* Feed */}
      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// Reusable live status dot for sub card variants
export function SubDot({ tone }) {
  const color = tone === 'ok' ? 'var(--accent)' : tone === 'warn' ? 'var(--warn)' : 'var(--danger)';
  const ring = tone === 'ok'
    ? '0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent)'
    : tone === 'warn'
    ? '0 0 0 3px color-mix(in oklab, var(--warn) 22%, transparent)'
    : '0 0 0 3px color-mix(in oklab, var(--danger) 22%, transparent)';
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: 999,
      background: color, boxShadow: ring,
      animation: tone === 'ok' ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
      flexShrink: 0,
    }} />
  );
}

// Premium subscription card — activity-ring focal, accent tint, perk chips
export function SubCardPremium({ sub, pct, onOpenPlans }) {
  const tone = sub.tone;
  const ringColor = tone === 'ok' ? 'var(--accent)' : tone === 'warn' ? 'var(--warn)' : 'var(--danger)';
  const deep = tone === 'ok' ? 'var(--accent-deep)' : tone === 'warn' ? '#a36a16' : 'var(--danger)';
  const tint = tone === 'ok'
    ? 'color-mix(in oklab, var(--accent-soft) 42%, var(--surface))'
    : tone === 'warn'
      ? 'color-mix(in oklab, var(--warn-soft) 55%, var(--surface))'
      : 'color-mix(in oklab, var(--danger-soft, #fef2f2) 70%, var(--surface))';
  const R = 34, C = 2 * Math.PI * R;
  const off = C * (1 - Math.max(0, Math.min(1, pct / 100)));
  const statusText = tone === 'ok' ? 'активен' : tone === 'warn' ? 'истекает' : 'истёк';
  const unit = sub.daysLeft === 1 ? 'день' : (sub.daysLeft > 1 && sub.daysLeft < 5) ? 'дня' : 'дней';
  return (
    <div className="card fade-up" style={{
      position: 'relative', overflow: 'hidden', padding: 18,
      background: tint,
      border: '0.5px solid color-mix(in oklab, ' + ringColor + ' 24%, var(--border))',
    }}>
      {/* decorative glow */}
      <div style={{
        position: 'absolute', right: -40, top: -52, width: 170, height: 170, borderRadius: '50%',
        background: 'radial-gradient(circle at 32% 34%, color-mix(in oklab, ' + ringColor + ' 26%, transparent), transparent 66%)',
        pointerEvents: 'none',
      }} />
      <div className="row-between" style={{ position: 'relative', marginBottom: 14 }}>
        <div className="t-mini" style={{ color: deep, letterSpacing: 0.6, fontWeight: 700 }}>Абонемент</div>
        <span style={{
          height: 22, padding: '0 10px', borderRadius: 999, fontSize: 11, fontWeight: 700,
          display: 'inline-flex', alignItems: 'center', gap: 5,
          background: 'color-mix(in oklab, ' + ringColor + ' 16%, var(--surface))', color: deep,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: 999, background: ringColor,
            boxShadow: '0 0 0 3px color-mix(in oklab, ' + ringColor + ' 24%, transparent)',
            animation: tone === 'ok' ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
          }} />
          {statusText}
        </span>
      </div>

      <div className="row" style={{ position: 'relative', gap: 16, alignItems: 'center' }}>
        <div style={{ position: 'relative', width: 84, height: 84, flexShrink: 0 }}>
          <svg width="84" height="84" viewBox="0 0 84 84" style={{ transform: 'rotate(-90deg)', display: 'block' }}>
            <circle cx="42" cy="42" r={R} fill="none" stroke="color-mix(in oklab, var(--text) 9%, transparent)" strokeWidth="7" />
            <circle cx="42" cy="42" r={R} fill="none" stroke={ringColor} strokeWidth="7" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={off}
              style={{ transition: 'stroke-dashoffset 0.85s cubic-bezier(0.32,0.72,0.2,1)' }} />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <span className="t-num" style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, letterSpacing: -1 }}>{sub.daysLeft}</span>
            <span className="t-mini" style={{ color: 'var(--text-3)', fontSize: 9.5, marginTop: 2 }}>{unit}</span>
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="t-h2" style={{ fontSize: 20, letterSpacing: -0.4 }}>{sub.label}</div>
          <div className="t-small" style={{ marginTop: 2 }}>
            {tone === 'danger' ? `истёк ${sub.until}` : `действует до ${sub.until}`}
          </div>
          <div className="row" style={{ gap: 7, marginTop: 11, flexWrap: 'wrap' }}>
            <span style={{
              height: 24, padding: '0 10px', borderRadius: 999, fontSize: 11.5, fontWeight: 600,
              background: 'var(--surface)', border: '0.5px solid var(--border)', color: 'var(--text-2)',
              display: 'inline-flex', alignItems: 'center', gap: 5,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: 999, background: ringColor }} />
              {tone === 'danger' ? 'QR не работает' : 'QR активен'}
            </span>
            <span style={{
              height: 24, padding: '0 10px', borderRadius: 999, fontSize: 11.5, fontWeight: 600,
              background: 'var(--surface)', border: '0.5px solid var(--border)', color: 'var(--text-2)',
              display: 'inline-flex', alignItems: 'center',
            }}>
              14 дней заморозки
            </span>
          </div>
        </div>
      </div>

      {tone !== 'ok' && (
        <button onClick={onOpenPlans} className="btn btn-accent" style={{ width: '100%', marginTop: 16, position: 'relative' }}>
          Продлить{tone === 'warn' ? ' со скидкой 15%' : ''}
        </button>
      )}
    </div>
  );
}

// Minimalist brand spot illustration — a dumbbell built from simple primitives.
// Outline-only, single accent hue; used as the brand symbol / emblem glyph.
function DumbbellMark({ color, style, sw = 3.4 }) {
  return (
    <svg viewBox="0 0 140 100" fill="none" stroke={color} strokeWidth={sw}
      strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true">
      {/* bar */}
      <rect x="46" y="44" width="48" height="12" rx="6" />
      {/* left plates */}
      <rect x="30" y="34" width="11" height="32" rx="5.5" />
      <rect x="16" y="40" width="9" height="20" rx="4.5" />
      {/* right plates */}
      <rect x="99" y="34" width="11" height="32" rx="5.5" />
      <rect x="115" y="40" width="9" height="20" rx="4.5" />
    </svg>
  );
}

// Variant: physical premium club card — brand emblem + monogram, gold chip,
// material texture, embossed cardholder details and a geometric brand pattern.
export function SubCardSpot({ sub, pct, userName = 'Саша', onOpenPlans }) {
  const tone = sub.tone;
  const accentC = tone === 'ok' ? 'var(--accent)' : tone === 'warn' ? 'var(--warn)' : 'var(--danger)';
  const statusText = tone === 'ok' ? 'активен' : tone === 'warn' ? 'истекает' : 'истёк';
  const unit = sub.daysLeft === 1 ? 'день' : (sub.daysLeft > 1 && sub.daysLeft < 5) ? 'дня' : 'дней';

  return (
    <div className="card fade-up" style={{
      position: 'relative', overflow: 'hidden', padding: '20px 22px 18px',
      minHeight: 206, display: 'flex', flexDirection: 'column',
      borderRadius: 'var(--r-xl)', color: '#f3f1ea', isolation: 'isolate',
      background: 'linear-gradient(155deg, #262a22 0%, #181b16 54%, #0f120e 100%)',
      border: '0.5px solid rgba(255,255,255,0.10)',
      boxShadow: '0 20px 44px -18px rgba(0,0,0,0.62), inset 0 1px 0 rgba(255,255,255,0.07)',
    }}>
      {/* geometric brand pattern — concentric rings, abstract & on-brand */}
      <svg viewBox="0 0 200 200" aria-hidden="true" style={{
        position: 'absolute', right: -56, top: -46, width: 250, height: 250, pointerEvents: 'none',
      }}>
        {[92, 74, 56, 38].map((r, i) => (
          <circle key={r} cx="100" cy="100" r={r} fill="none"
            stroke="rgba(255,255,255,0.05)" strokeWidth={i === 0 ? 1.2 : 0.8} />
        ))}
      </svg>
      {/* fine engraved guilloché texture */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.5,
        backgroundImage: 'repeating-linear-gradient(122deg, rgba(255,255,255,0.03) 0 1px, transparent 1px 9px)',
      }} />
      {/* soft top sheen */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.05), transparent 32%)',
      }} />
      {/* large embossed emblem — brand symbol pressed into the material */}
      <div style={{ position: 'absolute', right: -22, bottom: -34, width: 168, height: 168, pointerEvents: 'none' }}>
        <BrandSeal color="rgba(0,0,0,0.4)" style={{ position: 'absolute', inset: 0, transform: 'translate(1px,1.4px)' }} />
        <BrandSeal color="rgba(255,255,255,0.07)" style={{ position: 'absolute', inset: 0, transform: 'translate(-1px,-1px)' }} />
      </div>

      {/* Header — emblem + wordmark / status */}
      <div className="row-between" style={{ position: 'relative' }}>
        <div className="col">
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 700, letterSpacing: 1.5, color: '#f3f1ea' }}>МОЙ ЗАЛ</div>
          <div style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: 2, color: 'color-mix(in oklab, ' + accentC + ' 42%, #b8c0b8)', marginTop: 2 }}>PREMIUM CLUB</div>
        </div>
        <span style={{
          height: 24, padding: '0 11px', borderRadius: 999, fontSize: 10.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: 'rgba(255,255,255,0.06)', border: '0.5px solid rgba(255,255,255,0.14)',
          color: 'rgba(255,255,255,0.9)',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: 999, background: accentC,
            boxShadow: '0 0 0 3px color-mix(in oklab, ' + accentC + ' 22%, transparent)',
          }} />
          {statusText}
        </span>
      </div>

      {/* Primary metric — read instantly */}
      <div style={{ position: 'relative', marginTop: 'auto', paddingTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <span className="t-num" style={{
            fontFamily: 'var(--font-display)', fontSize: 78, fontWeight: 700,
            lineHeight: 0.76, letterSpacing: -3.5, color: '#f4f2ec', textShadow: '0 1px 0 rgba(0,0,0,0.35)',
          }}>{sub.daysLeft}</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'rgba(255,255,255,0.74)', paddingBottom: 9, lineHeight: 1.15, letterSpacing: -0.1 }}>
            {unit}<br />осталось
          </span>
        </div>
      </div>

      {/* Progress — plan + valid-thru frame the bar */}
      <div style={{ position: 'relative', marginTop: 14 }}>
        <div className="row-between" style={{ marginBottom: 7 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'rgba(255,255,255,0.82)', letterSpacing: 0.1 }}>{sub.label}</span>
          <span style={{ fontSize: 11.5, fontWeight: 500, color: 'rgba(255,255,255,0.5)', letterSpacing: 0.2, fontVariantNumeric: 'tabular-nums' }}>
            {tone === 'danger' ? `истёк ${sub.until}` : `до ${sub.until}`}
          </span>
        </div>
        <div style={{ height: 5, borderRadius: 999, background: 'rgba(255,255,255,0.12)', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: pct + '%', borderRadius: 999, background: accentC, transition: 'width 0.85s cubic-bezier(0.32,0.72,0.2,1)' }} />
        </div>
      </div>

      {tone !== 'ok' && (
        <button onClick={onOpenPlans} className="btn btn-accent" style={{ width: '100%', marginTop: 16, position: 'relative' }}>
          Продлить{tone === 'warn' ? ' со скидкой 15%' : ''}
        </button>
      )}
    </div>
  );
}

// Brand emblem — dumbbell glyph inside a ringed seal (monogram-like mark)
function BrandSeal({ color, style }) {
  return (
    <svg viewBox="0 0 100 100" fill="none" stroke={color} style={style} aria-hidden="true">
      <circle cx="50" cy="50" r="46" strokeWidth="2.4" />
      <circle cx="50" cy="50" r="38" strokeWidth="1" opacity="0.6" />
      <g transform="translate(50 50) scale(0.42) translate(-70 -50)">
        <DumbbellMark color={color} sw={6} />
      </g>
    </svg>
  );
}

// Variant B: QR-hero — QR is huge at top
export function HomeQrHero({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled }) {
  return (
    <>
      {trainerCancelled && <TrainerCancelCard onTab={onTab} />}
      {sub.tone === 'danger' && (
        <div style={{ padding: '0 16px 12px' }}>
          <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />
        </div>
      )}
      {/* QR hero */}
      <div style={{ padding: '0 16px 14px' }}>
        <button onClick={onOpenQR} className="press" style={{
          width: '100%', border: 0, background: 'var(--surface)',
          borderRadius: 'var(--r-xl)', padding: '24px 20px 20px',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          cursor: 'pointer', boxShadow: 'var(--sh-2)', borderTop: '1px solid var(--border)',
        }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', alignSelf: 'flex-start' }}>
            Пропуск · #4821
          </div>
          <div style={{ marginTop: 10, padding: 14, background: '#fff', borderRadius: 16 }}>
            <QRPattern size={180} color="#0a0a0a" />
          </div>
          <div style={{ marginTop: 14, color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>
            Тапни, чтобы увеличить
          </div>
        </button>
      </div>

      {/* Subscription compact */}
      <div style={{ padding: '0 16px 12px' }}>
        <div className="card" style={{ padding: 14 }}>
          <div className="row-between">
            <div>
              <div className="row" style={{ gap: 8 }}>
                <span className="t-h3" style={{ fontWeight: 600 }}>{sub.daysLeft} {sub.daysLeft === 1 ? 'день' : sub.daysLeft < 5 ? 'дня' : 'дней'}</span>
                <span className={`chip ${subTone}`} style={{ height: 22, padding: '0 9px', fontSize: 11.5 }}>{sub.label}</span>
              </div>
              <div className="t-small" style={{ marginTop: 2 }}>до {sub.until}</div>
            </div>
            {sub.tone !== 'ok' && (
              <button onClick={onOpenPlans} className="btn btn-accent btn-sm">Продлить</button>
            )}
          </div>
          <div className="progress-track" style={{ marginTop: 12 }}>
            <div className={`progress-fill ${fillTone}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      {!isEmpty && <UpcomingCard onClick={onOpenManage} onCancel={onOpenManage} compact />}

      <div style={{ padding: '4px 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <BookTile onClick={() => onTab('book')} />
        <ChatTile onClick={() => onTab('chat')} badge={isEmpty ? 0 : 2} />
      </div>

      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// Variant C: Minimal — single big "next thing" hero
export function HomeMinimal({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled }) {
  const ms = useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000);
  const cd = formatCountdown(ms);
  const banner = (
    <>
      {trainerCancelled && <TrainerCancelCard onTab={onTab} />}
      {sub.tone === 'danger' && (
        <div style={{ padding: '0 16px 12px' }}>
          <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />
        </div>
      )}
    </>
  );
  if (isEmpty) {
    return (
      <>
        {banner}
        <div style={{ padding: '0 20px 8px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Добро пожаловать</div>
          <div className="t-display" style={{ marginTop: 4, marginBottom: 6, letterSpacing: -1 }}>
            Начни<br/>с первого визита
          </div>
          <div className="t-body" style={{ color: 'var(--text-2)' }}>
            Открой QR на турникете или запишись к тренеру.
          </div>
        </div>

        <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 10 }}>
          <button onClick={onOpenQR} className="btn btn-accent" style={{ flex: 1, height: 56 }}>
            <Icon name="qr" size={20} color="#06120c" strokeWidth={2} />
            Пройти в зал
          </button>
        </div>

        <div style={{ padding: '4px 16px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button onClick={() => onTab('book')} className="btn btn-ghost" style={{ height: 44 }}>
            Записаться
          </button>
          <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
            Написать
          </button>
        </div>

        <FeedSection unread={0} isEmpty onOpenNotifications={onOpenNotifications} />
      </>
    );
  }
  return (
    <>
      {banner}
      <div style={{ padding: '0 20px 8px' }}>
        <div className="t-mini" style={{ color: 'var(--text-3)', fontVariantNumeric: 'tabular-nums' }}>
          Сегодня в {UPCOMING_BOOKING.time} · через {cd.primary}
        </div>
        <div className="t-display" style={{ marginTop: 4, marginBottom: 6, letterSpacing: -1 }}>
          Тренировка<br/>с {UPCOMING_BOOKING.trainerInstr}
        </div>
        <div className="t-body" style={{ color: 'var(--text-2)' }}>
          Зал на Тверской · {UPCOMING_BOOKING.focus}
        </div>
      </div>

      <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 10 }}>
        <button onClick={onOpenQR} className="btn btn-accent" style={{ flex: 1, height: 56 }}>
          <Icon name="qr" size={20} color="#06120c" strokeWidth={2} />
          Пройти в зал
        </button>
      </div>

      <div style={{ padding: '4px 16px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <button onClick={onOpenManage} className="btn btn-ghost" style={{ height: 44 }}>
          Перенести
        </button>
        <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
          Написать
        </button>
      </div>

      {/* Sub strip */}
      <div style={{ padding: '0 16px 14px' }}>
        <button onClick={() => onTab('profile')} style={{
          width: '100%', border: 0, background: 'transparent', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px',
          borderRadius: 'var(--r-lg)', background: 'var(--surface)',
          textAlign: 'left',
        }}>
          <div className="dot" style={{
            background: sub.tone === 'ok' ? 'var(--accent)' : sub.tone === 'warn' ? 'var(--warn)' : 'var(--danger)',
            width: 10, height: 10,
          }} />
          <div style={{ flex: 1 }}>
            <div className="t-h3">{sub.label}</div>
            <div className="t-small">{sub.daysLeft === 0 ? `истёк ${sub.until}` : `${sub.daysLeft} ${sub.daysLeft === 1 ? 'день' : 'дней'} до ${sub.until}`}</div>
          </div>
          {sub.tone !== 'ok' ? (
            <span onClick={(e) => { e.stopPropagation(); onOpenPlans(); }}
                  className="chip chip-accent"
                  style={{ background: 'var(--text)', color: 'var(--bg)' }}>Продлить</span>
          ) : (
            <Icon name="chevronRight" size={18} color="var(--text-3)" />
          )}
        </button>
      </div>

      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// ─── Upcoming booking card (used on classic + qr-hero) ─────────
export function UpcomingCard({ onClick, compact, onCancel }) {
  const b = UPCOMING_BOOKING;
  // 4h 12m from "now" — ticks down each second
  const ms = useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000);
  const cd = formatCountdown(ms);
  const cdLabel = cd.h > 0 ? `${cd.h}ч ${cd.m}м` : `${cd.m}м`;
  const cardInner = (
    <button
      onClick={onClick}
      className="press card"
      style={{
        appearance: 'none', cursor: 'pointer', textAlign: 'left', width: '100%',
        display: 'flex', alignItems: 'stretch', gap: 0, padding: 0, overflow: 'hidden',
        color: 'var(--text)', borderRadius: 0,
      }}
    >
      {/* accent rail — marks the next active session */}
      <div style={{ width: 4, background: 'var(--accent)', flexShrink: 0 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: compact ? 13 : '14px 15px', flex: 1, minWidth: 0 }}>
        {/* time focal */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div className="t-num" style={{ fontSize: 22, fontWeight: 750, lineHeight: 1, letterSpacing: -0.6 }}>{b.time}</div>
          <div className="t-mini" style={{ color: 'var(--text-3)', marginTop: 4 }}>{b.duration} мин</div>
        </div>

        {/* divider */}
        <div style={{ width: 1, alignSelf: 'stretch', background: 'var(--border)' }} />

        {/* details */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="t-h3" style={{ fontSize: 15.5, letterSpacing: -0.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.focus}</span>
          <div className="row-between" style={{ gap: 8, minWidth: 0 }}>
            <span className="row" style={{ gap: 7, minWidth: 0 }}>
              <span className="t-small" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.trainer}</span>
            </span>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', flexShrink: 0,
              fontSize: 12.5, fontWeight: 600, color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums',
            }}>
              <Icon name="clock" size={13} color="var(--text-3)" strokeWidth={2} />
              {cdLabel}
            </span>
          </div>
        </div>

        {/* chevron affordance */}
        <span style={{ flexShrink: 0, display: 'inline-flex' }}>
          <Icon name="chevronRight" size={18} color="var(--text-3)" strokeWidth={2.2} />
        </span>
      </div>
    </button>
  );
  return (
    <div style={{ padding: '0 16px 12px' }}>
      <SwipeRow onAction={() => onCancel?.()} actionLabel="Отменить" actionIcon="close">
        {cardInner}
      </SwipeRow>
    </div>
  );
}

export function QuickTile({ icon, title, sub, onClick, badge }) {
  return (
    <button onClick={onClick} className="press" style={{
      background: 'var(--surface)', borderRadius: 'var(--r-lg)',
      padding: '16px', textAlign: 'left', cursor: 'pointer',
      border: '0.5px solid var(--border)', position: 'relative',
      color: 'var(--text)', fontFamily: 'inherit',
    }}>
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, background: 'var(--surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={20} color="var(--text)" />
        </div>
        {badge ? <span className="badge">{badge}</span> : null}
      </div>
      <div className="t-h3">{title}</div>
      <div className="t-small">{sub}</div>
    </button>
  );
}

// Distinct quick-action tiles (ported from the new home design)
export function BookTile({ onClick }) {
  const avs = [
    { t: 'А', bg: 'var(--accent)', c: '#06231a' },
    { t: 'М', bg: 'color-mix(in oklab, var(--accent) 58%, #6ee7c4)', c: '#06231a' },
    { t: 'К', bg: 'var(--accent-deep)', c: '#eafaf3' },
  ];
  return (
    <button onClick={onClick} className="press" style={{
      background: 'var(--surface)', border: '0.5px solid var(--border)', borderRadius: 'var(--r-lg)',
      padding: 15, textAlign: 'left', cursor: 'pointer', color: 'var(--text)', fontFamily: 'inherit',
      minHeight: 132, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ display: 'flex' }}>
        {avs.map((a, i) => (
          <span key={i} style={{
            width: 34, height: 34, borderRadius: 999, border: '2.5px solid var(--surface)',
            marginLeft: i ? -11 : 0, background: a.bg, color: a.c,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 700,
          }}>{a.t}</span>
        ))}
        <span style={{
          width: 34, height: 34, borderRadius: 999, border: '2.5px solid var(--surface)', marginLeft: -11,
          background: 'var(--surface-2)', color: 'var(--text-2)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700,
        }}>+9</span>
      </div>
      <div>
        <div className="t-h3" style={{ fontSize: 16 }}>Записаться</div>
        <div className="t-small">12 тренеров в зале</div>
      </div>
    </button>
  );
}

export function ChatTile({ onClick, badge = 0 }) {
  return (
    <button onClick={onClick} className="press" style={{
      background: 'var(--text)', border: 0, borderRadius: 'var(--r-lg)',
      padding: 15, textAlign: 'left', cursor: 'pointer', color: 'var(--bg)', fontFamily: 'inherit',
      minHeight: 132, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'relative', width: 'fit-content' }}>
        <span style={{
          width: 50, height: 38, borderRadius: '15px 15px 15px 5px',
          background: 'rgba(255,255,255,0.13)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          {[0, 1, 2].map(i => (
            <span key={i} className="chat-dot" style={{
              width: 6, height: 6, borderRadius: 999, background: 'var(--accent)',
              opacity: 1 - i * 0.28, animationDelay: (i * 0.2) + 's',
            }} />
          ))}
        </span>
        {badge > 0 && (
          <span style={{
            position: 'absolute', top: -7, right: -7, minWidth: 21, height: 21, padding: '0 5px',
            borderRadius: 999, background: 'var(--accent)', color: '#06231a',
            border: '2.5px solid var(--text)', fontSize: 11, fontWeight: 800,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}>{badge}</span>
        )}
      </div>
      <div>
        <div className="t-h3" style={{ fontSize: 16, color: 'var(--bg)' }}>Чат</div>
        <div className="t-small" style={{ color: 'color-mix(in oklab, var(--bg) 62%, transparent)' }}>Ответят за ~5 мин</div>
      </div>
      <style>{`@keyframes chat-dot{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}} .chat-dot{animation:chat-dot 1.4s ease-in-out infinite}`}</style>
    </button>
  );
}

// ─── Expired subscription banner ─────────────────────────────────
export function ExpiredAlert({ sub, onOpenPlans }) {
  return (
    <div className="card fade-up" style={{
      padding: 16, background: 'var(--danger-soft, #fef2f2)',
      border: '0.5px solid color-mix(in oklab, var(--danger) 35%, transparent)',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, flexShrink: 0,
          background: 'var(--danger)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'pulse-soft 2s ease-in-out infinite',
        }}>
          <Icon name="alert" size={22} color="currentColor" strokeWidth={2.2} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--danger)' }}>
            Абонемент закончился {sub.until}
          </div>
          <div className="t-small" style={{ marginTop: 4, color: 'var(--text-2)', lineHeight: 1.45 }}>
            QR не сработает на турникете. Продли сегодня — сохраним твою серию посещений и скидку на тренера.
          </div>
        </div>
      </div>
      <button onClick={onOpenPlans} className="btn" style={{
        width: '100%', height: 46, background: 'var(--danger)', color: '#fff',
        border: 0, fontWeight: 600,
      }}>
        Выбрать тариф
        <Icon name="arrowRight" size={16} color="currentColor" strokeWidth={2} />
      </button>
      <style>{`
        @keyframes pulse-soft {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
      `}</style>
    </div>
  );
}

// ─── Trainer cancellation card ───────────────────────────────────
export function TrainerCancelCard({ onTab }) {
  const c = TRAINER_CANCEL;
  const [hidden, setHidden] = React.useState(false);
  if (hidden) return null;
  return (
    <div style={{ padding: '0 16px 12px' }}>
    <div className="card fade-up" style={{
      padding: 0, overflow: 'hidden',
      border: '0.5px solid color-mix(in oklab, var(--danger) 35%, transparent)',
    }}>
      <div style={{
        background: 'var(--danger)', color: '#fff', padding: '10px 8px 10px 16px',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Icon name="alert" size={14} color="currentColor" strokeWidth={2.4} />
        <span className="t-mini" style={{ color: '#fff', letterSpacing: 0.6, fontWeight: 700, flex: 1 }}>
          Тренировка отменена
        </span>
        <button
          onClick={() => setHidden(true)}
          aria-label="Скрыть"
          className="press"
          style={{
            flexShrink: 0, width: 26, height: 26, borderRadius: 999, border: 0,
            background: 'rgba(255,255,255,0.18)', color: '#fff', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Icon name="close" size={13} color="currentColor" strokeWidth={2.4} />
        </button>
      </div>
      <div style={{ padding: 16 }}>
        <div className="row" style={{ gap: 12, alignItems: 'center' }}>
          <Avatar initials={c.initials} bg={c.bg} color={c.color} size={42} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="t-h3" style={{ fontSize: 15 }}>{c.trainer}</div>
            <div className="t-small" style={{ marginTop: 2 }}>{c.date} · {c.reason}</div>
          </div>
        </div>
        <div className="t-small" style={{ marginTop: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {c.reasonFull} Вернули <b style={{ color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{c.refund.toLocaleString('ru')} ₽</b> на карту.
        </div>
        <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <button onClick={() => onTab('book')} className="btn btn-accent" style={{ height: 44 }}>
            Перенести
          </button>
          <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
            Написать
          </button>
        </div>
      </div>
    </div>
    </div>
  );
}

export function FeedSection({ unread, isEmpty, onOpenNotifications }) {
  if (isEmpty) {
    return (
      <div style={{ padding: '8px 4px 0' }}>
        <div style={{ padding: '4px 20px 4px' }}>
          <div className="t-h2">Уведомления</div>
          <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 2 }}>
            история анонсов и пушей зала
          </div>
        </div>
        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 0 }}>
            <EmptyState
              illustration="sparkle"
              title="Тут будут новости"
              body="Пиши на ресепшен — расскажем про расписание, события и акции."
              compact
            />
          </div>
        </div>
      </div>
    );
  }
  const visible = NOTIFICATIONS.slice(0, 5);
  const hasMore = NOTIFICATIONS.length > visible.length;

  // Harmonious per-type accents (shared chroma/lightness, varied hue)
  const TONES = {
    promo:       { c: 'oklch(0.60 0.13 162)', label: 'Акция' },
    achievement: { c: 'oklch(0.64 0.12 72)',  label: 'Достижение' },
    schedule:    { c: 'oklch(0.62 0.14 42)',  label: 'Расписание' },
    message:     { c: 'oklch(0.58 0.12 250)', label: 'Сообщение' },
    news:        { c: 'oklch(0.56 0.13 300)', label: 'Клуб' },
    info:        { c: 'var(--text-3)',        label: 'Система' },
  };
  const soft = (c, p) => 'color-mix(in oklab, ' + c + ' ' + p + '%, var(--surface))';
  const catBadge = (kind) => {
    const tn = TONES[kind];
    const neutral = kind === 'info';
    return (
      <span style={{
        height: 19, padding: '0 8px', borderRadius: 999, fontSize: 9.5, fontWeight: 700,
        letterSpacing: 0.5, textTransform: 'uppercase', flexShrink: 0,
        background: neutral ? 'var(--surface-2)' : soft(tn.c, 15),
        color: neutral ? 'var(--text-3)' : tn.c,
        display: 'inline-flex', alignItems: 'center',
      }}>{tn.label}</span>
    );
  };
  const unreadDot = <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--accent)', flexShrink: 0 }} />;
  const timeText = (t) => <span className="t-mini" style={{ textTransform: 'none', letterSpacing: 0.2, color: 'var(--text-3)', fontWeight: 500, whiteSpace: 'nowrap', flexShrink: 0 }}>{t}</span>;

  const ICONS = { promo: 'tag', achievement: 'starFill', schedule: 'calendar', message: 'chat', news: 'image', info: 'info' };
  const renderNotif = (n) => {
    const c = (TONES[n.kind] || TONES.info).c;
    return (
      <div key={n.id} className="card press" style={{ padding: '13px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, flexShrink: 0, background: soft(c, 16), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={ICONS[n.kind] || 'info'} size={19} color={c} strokeWidth={1.9} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row-between" style={{ gap: 8, alignItems: 'flex-start' }}>
            <span className="t-h3" style={{
              fontSize: 15, minWidth: 0, lineHeight: 1.3,
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>{n.title}</span>
            <span className="row" style={{ gap: 7, flexShrink: 0, marginTop: 2 }}>
              {timeText(n.time)}
              {n.unread && unreadDot}
            </span>
          </div>
          <div className="t-small" style={{ marginTop: 3, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{n.body}</div>
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: '8px 4px 0' }}>
      <button
        onClick={onOpenNotifications}
        className="press"
        style={{
          appearance: 'none', border: 0, background: 'transparent',
          width: '100%', cursor: onOpenNotifications ? 'pointer' : 'default',
          padding: '4px 20px 10px', display: 'flex',
          alignItems: 'center', justifyContent: 'space-between',
          fontFamily: 'inherit', color: 'var(--text)', textAlign: 'left',
        }}>
        <div className="row" style={{ gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="row" style={{ gap: 8, alignItems: 'center' }}>
              <span className="t-h2">Лента клуба</span>
              {unread > 0 && (
                <span style={{
                  minWidth: 20, height: 20, padding: '0 6px',
                  borderRadius: 999, background: 'var(--accent)', color: '#06120c',
                  fontSize: 11, fontWeight: 700,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontVariantNumeric: 'tabular-nums',
                }}>{unread}</span>
              )}
            </div>
            <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 2, fontWeight: 400 }}>
              акции, события и сообщения зала
            </div>
          </div>
        </div>
        {onOpenNotifications && (
          <span className="t-small" style={{
            color: 'var(--text-2)', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 2,
          }}>
            Все
            <Icon name="chevronRight" size={14} color="var(--text-3)" strokeWidth={2.2} />
          </span>
        )}
      </button>
      <div className="stack-2" style={{ padding: '0 16px', gap: 10 }}>
        {visible.map(renderNotif)}
        {hasMore && onOpenNotifications && (
          <button onClick={onOpenNotifications} className="press" style={{
            appearance: 'none', border: '0.5px dashed var(--border-strong)',
            background: 'transparent', borderRadius: 'var(--r-lg)',
            padding: '12px 16px', cursor: 'pointer',
            color: 'var(--text-2)', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 13, fontWeight: 600,
          }}>
            Ещё {NOTIFICATIONS.length - visible.length}
            <Icon name="chevronRight" size={14} color="var(--text-3)" strokeWidth={2.2} />
          </button>
        )}
      </div>
    </div>
  );
}

