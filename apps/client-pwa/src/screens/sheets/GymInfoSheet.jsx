import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { Divider, RowItem } from '@/components/RowItem.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { GYM_INFO } from '@/data';

// Decorative glyphs used as photography placeholders in the gym hero
function GymPhotoGlyph({ kind }) {
  // All glyphs use currentColor; size is 180x180 viewBox
  switch (kind) {
    case 'dumbbell':
      return (
        <g fill="currentColor">
          <rect x="16"  y="78" width="14" height="24" rx="3" />
          <rect x="34"  y="68" width="10" height="44" rx="3" />
          <rect x="44"  y="86" width="92" height="8"  rx="4" />
          <rect x="136" y="68" width="10" height="44" rx="3" />
          <rect x="150" y="78" width="14" height="24" rx="3" />
        </g>
      );
    case 'run':
      return (
        <g fill="currentColor">
          <circle cx="118" cy="40" r="14" />
          <path d="M58 86 L92 72 L114 80 L130 102 L154 100 L154 112 L122 116 L100 90 L84 100 L98 124 L116 144 L106 152 L82 130 L66 110 L44 130 L34 122 L60 96 Z" />
        </g>
      );
    case 'sauna':
      return (
        <g fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round">
          <path d="M50 130 Q60 110 50 90 Q40 70 50 50" />
          <path d="M90 140 Q100 116 90 92 Q80 68 90 44" />
          <path d="M130 130 Q140 110 130 90 Q120 70 130 50" />
        </g>
      );
    case 'locker':
      return (
        <g fill="none" stroke="currentColor" strokeWidth="5">
          <rect x="36"  y="30" width="48" height="120" rx="6" />
          <rect x="96"  y="30" width="48" height="120" rx="6" />
          <circle cx="60"  cy="98" r="3" fill="currentColor" stroke="none" />
          <circle cx="120" cy="98" r="3" fill="currentColor" stroke="none" />
          <line x1="48"  y1="50" x2="72"  y2="50" />
          <line x1="108" y1="50" x2="132" y2="50" />
        </g>
      );
    case 'yoga':
      return (
        <g fill="currentColor">
          <circle cx="90" cy="36" r="12" />
          <path d="M90 54 L90 96 L60 132 L70 138 L90 110 L110 138 L120 132 L90 96 Z" />
          <rect x="32" y="138" width="116" height="6" rx="3" />
        </g>
      );
    default:
      return null;
  }
}

export const GymInfoSheet = ({ onClose }) => {
  const g = GYM_INFO;
  const [photoIdx, setPhotoIdx] = React.useState(0);
  const [hoursOpen, setHoursOpen] = React.useState(false);
  const [rulesOpen, setRulesOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [calling, setCalling] = React.useState(false);
  const [route, setRoute] = React.useState(false);

  const todayHrs = `${g.hours[g.todayIdx].open}–${g.hours[g.todayIdx].close}`;

  const copyAddr = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(`${g.city}, ${g.address}`).catch(() => {});
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  const callGym = () => { setCalling(true); setTimeout(() => setCalling(false), 1800); };
  const openRoute = () => { setRoute(true); setTimeout(() => setRoute(false), 2200); };

  return (
    <div className="sheet" style={{ background: 'var(--bg)' }}>
      <StatusBar />

      {/* Photo carousel */}
      <div style={{ position: 'relative', height: 260, overflow: 'hidden', flexShrink: 0 }}>
        {g.photos.map((p, i) => (
          <div key={i} style={{
            position: 'absolute', inset: 0,
            opacity: i === photoIdx ? 1 : 0,
            transition: 'opacity 0.4s ease',
            background: `linear-gradient(135deg, color-mix(in oklab, ${p.bg} 88%, #fff) 0%, ${p.bg} 60%, color-mix(in oklab, ${p.bg} 75%, #000) 100%)`,
            display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-start', padding: 20,
          }}>
            <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.08, pointerEvents: 'none' }}>
              <defs>
                <pattern id={`gpat-${i}`} x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                  <circle cx="20" cy="20" r="1" fill="#fff" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill={`url(#gpat-${i})`} />
            </svg>
            {/* Decorative photo glyph — placeholder for actual photography */}
            <svg
              width="180" height="180" viewBox="0 0 180 180"
              style={{
                position: 'absolute', right: -20, top: '50%',
                transform: 'translateY(-50%)',
                opacity: 0.22, color: '#fff', pointerEvents: 'none',
              }}
            >
              <GymPhotoGlyph kind={p.icon} />
            </svg>
            <span style={{
              position: 'relative', zIndex: 1,
              color: 'rgba(255,255,255,0.92)', fontSize: 11, fontWeight: 600,
              letterSpacing: 0.4, textTransform: 'uppercase',
              padding: '5px 10px', borderRadius: 999,
              background: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(6px)',
            }}>{p.tag}</span>
          </div>
        ))}

        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 100,
          background: 'linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0) 100%)',
          pointerEvents: 'none', zIndex: 2,
        }} />
        <button onClick={onClose} style={{
          position: 'absolute', top: 54, left: 16, zIndex: 5,
          width: 40, height: 40, borderRadius: 999,
          border: 0, background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(10px)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff',
        }}>
          <Icon name="close" size={20} color="#fff" strokeWidth={2.2} />
        </button>

        <div style={{
          position: 'absolute', top: 54, right: 16, zIndex: 5,
          height: 32, padding: '0 12px',
          borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 8,
          background: g.status.open ? 'rgba(16,185,129,0.92)' : 'rgba(120,113,108,0.92)',
          color: '#fff', fontSize: 12, fontWeight: 700, letterSpacing: 0.3, backdropFilter: 'blur(6px)',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: 999, background: '#fff',
            animation: g.status.open ? 'pulse-soft 2s ease-in-out infinite' : 'none',
          }} />
          {g.status.open ? `Открыто до ${g.status.until}` : 'Закрыто'}
        </div>

        <div style={{
          position: 'absolute', bottom: 12, left: 0, right: 0, zIndex: 3,
          display: 'flex', justifyContent: 'center', gap: 6,
        }}>
          {g.photos.map((_, i) => (
            <button key={i} onClick={() => setPhotoIdx(i)} style={{
              border: 0, padding: 0, cursor: 'pointer',
              width: i === photoIdx ? 18 : 6, height: 6, borderRadius: 999,
              background: i === photoIdx ? '#fff' : 'rgba(255,255,255,0.5)',
              transition: 'all 0.22s ease',
            }} />
          ))}
        </div>
      </div>

      <div className="scroller" style={{ paddingTop: 0, marginTop: -16 }}>
        <div style={{
          background: 'var(--bg)', borderTopLeftRadius: 24, borderTopRightRadius: 24,
          padding: '20px 20px 8px', position: 'relative',
        }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>{g.tagline}</div>
          <div className="t-display" style={{ marginTop: 4, letterSpacing: -0.8, fontSize: 28 }}>{g.name}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <Icon name="mapPin" size={14} color="var(--text-3)" />
            <div className="t-small" style={{ color: 'var(--text-2)' }}>
              {g.address} · {g.metro}
            </div>
          </div>
        </div>

        <div style={{
          padding: '12px 16px 8px', display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr', gap: 8,
        }}>
          <GIQuickAction icon="navigation" label="Маршрут" onClick={openRoute} />
          <GIQuickAction icon="phone" label="Позвонить" onClick={callGym} />
          <GIQuickAction icon="copy" label={copied ? 'Скопировано' : 'Адрес'} onClick={copyAddr} highlight={copied} />
        </div>

        {(copied || calling || route) && (
          <div style={{ padding: '0 16px 8px' }}>
            <div className="fade-up" style={{
              background: 'var(--text)', color: 'var(--bg)',
              padding: '10px 14px', borderRadius: 12,
              display: 'flex', alignItems: 'center', gap: 10,
              fontSize: 13, fontWeight: 500,
            }}>
              <Icon name={copied ? 'check' : calling ? 'phone' : 'navigation'} size={16} color="var(--bg)" strokeWidth={2.2} />
              {copied && 'Адрес скопирован — открой Карты'}
              {calling && `Звоним: ${g.phone}`}
              {route && `${g.walkMin} мин пешком от тебя`}
            </div>
          </div>
        )}

        <div style={{ padding: '8px 16px' }}>
          <button onClick={() => setHoursOpen(o => !o)} className="card press" style={{
            width: '100%', padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12,
            background: 'var(--surface)', border: '0.5px solid var(--border)',
            cursor: 'pointer', textAlign: 'left',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, background: 'var(--surface-2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="clock" size={18} color="var(--text)" />
            </div>
            <div style={{ flex: 1 }}>
              <div className="t-h3" style={{ fontSize: 15 }}>Часы работы</div>
              <div className="t-small" style={{ marginTop: 1 }}>Сегодня · {todayHrs}</div>
            </div>
            <div style={{ transform: hoursOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.18s' }}>
              <Icon name="chevronDown" size={16} color="var(--text-3)" />
            </div>
          </button>

          {hoursOpen && (
            <div className="fade-up" style={{
              marginTop: 4, background: 'var(--surface)', border: '0.5px solid var(--border)',
              borderRadius: 'var(--r-lg)', overflow: 'hidden',
            }}>
              {g.hours.map((h, i) => {
                const today = i === g.todayIdx;
                return (
                  <div key={i} style={{
                    padding: '12px 16px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    borderBottom: i < g.hours.length - 1 ? '0.5px solid var(--border)' : 0,
                    background: today ? 'var(--surface-2)' : 'transparent',
                  }}>
                    <div style={{
                      fontSize: 14, fontWeight: today ? 700 : 500,
                      color: today ? 'var(--text)' : 'var(--text-2)',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}>
                      {h.d}
                      {today && <span style={{
                        fontSize: 9, padding: '2px 6px', borderRadius: 999,
                        background: 'var(--accent)', color: '#06120c', fontWeight: 700, letterSpacing: 0.3,
                      }}>СЕГОДНЯ</span>}
                    </div>
                    <div className="t-num" style={{
                      fontSize: 14, color: today ? 'var(--text)' : 'var(--text-2)',
                      fontWeight: today ? 600 : 500,
                    }}>{h.open}–{h.close}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 20px 8px' }}>Что есть в зале</div>
        <div style={{ padding: '0 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {g.amenities.map((a, i) => (
            <div key={i} className="card" style={{
              padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 10, background: 'var(--surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Icon name={a.icon} size={16} color="var(--text)" />
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{a.label}</div>
            </div>
          ))}
        </div>

        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 20px 8px' }}>Сегодня в зале</div>
        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <RowItem icon="user" label="Администратор" value={g.staffToday.admin} sub="Подходи на ресепшн с любым вопросом" />
            <Divider />
            <RowItem icon="flame" label="Тренеры на смене" value={`${g.staffToday.trainers}`} sub="Можешь записаться или взять тренировку" />
            <Divider />
            <RowItem icon="calendar" label="Групповых занятий" value={`${g.staffToday.classes}`} sub="С 7:00 до 21:00" />
          </div>
        </div>

        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 20px 8px' }}>Связаться</div>
        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 4 }}>
            <GIContactRow icon="phone" label="Телефон" value={g.phone} onClick={callGym} />
            <Divider />
            <GIContactRow icon="chat" label="Email" value={g.email} />
            {g.social.map((s) => (
              <React.Fragment key={s.kind}>
                <Divider />
                <GIContactRow icon={s.kind === 'tg' ? 'telegram' : 'instagram'} label={s.label} value={s.handle} />
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 20px 8px' }}>Правила зала</div>
        <div style={{ padding: '0 16px 24px' }}>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <button onClick={() => setRulesOpen(o => !o)} style={{
              width: '100%', padding: '14px 16px', border: 0, cursor: 'pointer',
              background: 'transparent', textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 10, background: 'var(--surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Icon name="info" size={16} color="var(--text)" />
              </div>
              <div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>
                {rulesOpen ? 'Свернуть' : `Все ${g.rules.length} правил зала`}
              </div>
              <div style={{ transform: rulesOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.18s' }}>
                <Icon name="chevronDown" size={16} color="var(--text-3)" />
              </div>
            </button>

            {rulesOpen && (
              <div className="fade-up" style={{ padding: '0 16px 14px' }}>
                <div style={{
                  borderTop: '0.5px solid var(--border)',
                  paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 12,
                }}>
                  {g.rules.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <div style={{
                        flexShrink: 0, width: 22, height: 22, borderRadius: 999,
                        background: 'var(--surface-2)', color: 'var(--text-2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, fontVariantNumeric: 'tabular-nums', marginTop: 1,
                      }}>{i + 1}</div>
                      <div style={{ fontSize: 13.5, color: 'var(--text-2)', lineHeight: 1.5, flex: 1 }}>{r}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function GIQuickAction({ icon, label, onClick, highlight }) {
  return (
    <button onClick={onClick} className="press" style={{
      cursor: 'pointer', padding: '14px 8px',
      background: highlight ? 'var(--accent)' : 'var(--surface)',
      color: highlight ? '#06120c' : 'var(--text)',
      borderRadius: 'var(--r-lg)',
      border: highlight ? '0.5px solid transparent' : '0.5px solid var(--border)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
      transition: 'background 0.16s, color 0.16s',
    }}>
      <Icon name={icon} size={20} color={highlight ? '#06120c' : 'var(--text)'} strokeWidth={1.9} />
      <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: -0.1 }}>{label}</div>
    </button>
  );
}

function GIContactRow({ icon, label, value, onClick }) {
  return (
    <button onClick={onClick} className={onClick ? 'press' : ''} style={{
      width: '100%', border: 0, background: 'transparent', cursor: onClick ? 'pointer' : 'default',
      padding: '12px 14px', textAlign: 'left',
      display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 10, background: 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon name={icon} size={16} color="var(--text)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-mini" style={{ color: 'var(--text-3)' }}>{label}</div>
        <div style={{
          fontSize: 14, fontWeight: 500, color: 'var(--text)',
          marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{value}</div>
      </div>
      {onClick && <Icon name="chevronRight" size={14} color="var(--text-3)" />}
    </button>
  );
}

