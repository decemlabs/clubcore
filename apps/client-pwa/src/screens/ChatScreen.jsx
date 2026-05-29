import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { LongPressItem } from '@/components/ContextMenu.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { CONVERSATIONS, TRAINER_CANCEL } from '@/data';

export const ChatScreen = ({ tweaks, initialConv, onClearInitial, onThreadOpen }) => {
  const [convId, setConvId] = React.useState(null);
  React.useEffect(() => {
    onThreadOpen && onThreadOpen(!!convId);
    return () => { onThreadOpen && onThreadOpen(false); };
  }, [convId]);
  const [convs, setConvs] = React.useState(() => {
    if (tweaks && tweaks.gymEvent === 'trainer-cancelled') {
      return CONVERSATIONS.map(c =>
        c.id === 'c2' && TRAINER_CANCEL ? {
          ...c,
          unread: 1,
          last: 'Тренировка отменена',
          lastTime: 'сейчас',
          messages: [...c.messages, TRAINER_CANCEL.systemMessage],
        } : c
      );
    }
    return CONVERSATIONS;
  });
  const isEmpty = tweaks && tweaks.dataMode === 'empty';

  React.useEffect(() => {
    if (initialConv) {
      setConvId(initialConv);
      onClearInitial && onClearInitial();
    }
  }, [initialConv]);

  if (convId) {
    const conv = convs.find(c => c.id === convId);
    return <ChatThread
      conv={conv}
      onBack={() => setConvId(null)}
      onSend={(text, from = 'me', kind = null) => {
        const msg = { id: 'new-' + Date.now() + Math.random(), from, body: text, time: 'сейчас', read: false };
        if (kind) msg.kind = kind;
        if (kind === 'photo') {
          msg.photo = (text.startsWith('photo:') ? text.split(':')[1] : 'gym-selfie');
          msg.body = '';
        }
        setConvs(cs => cs.map(c => c.id === convId ? {
          ...c,
          messages: [...c.messages, msg],
          last: kind === 'photo' ? '📷 Фото' : text,
          lastTime: 'сейчас',
        } : c));
      }}
    />;
  }

  return (
    <div className="page">
      <StatusBar />
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => new Promise(r => setTimeout(r, 700))}
      >
        <div style={{ padding: '8px 20px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Сообщения</div>
          <div className="t-h1" style={{ marginTop: 4 }}>Чат</div>
        </div>

        {isEmpty ? (
          <div style={{ padding: '0 16px' }}>
            <div className="card" style={{ padding: 0 }}>
              <EmptyState
                illustration="chat"
                title="Здесь появятся сообщения"
                body="Напишем, когда подтвердим запись или будут новости. Можно начать диалог самим."
              />
            </div>
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="t-mini" style={{ padding: '0 4px' }}>Начать диалог</div>
              <button
                className="press card"
                style={{
                  width: '100%', padding: 14, display: 'flex', gap: 12, alignItems: 'center',
                  border: 0, cursor: 'pointer', textAlign: 'left',
                }}
              >
                <Avatar initials="Р" bg="var(--accent-soft)" color="var(--accent-deep)" size={40} />
                <div style={{ flex: 1 }}>
                  <div className="t-h3" style={{ fontSize: 15 }}>Ресепшен</div>
                  <div className="t-small">Расписание, абонемент, акции</div>
                </div>
                <Icon name="chevronRight" size={16} color="var(--text-3)" />
              </button>
            </div>
          </div>
        ) : (
          <div className="stack-2" style={{ padding: '0 16px' }}>
            {convs.map((c, i) => (
            <SwipeRow
              key={c.id}
              actionLabel={c.isMuted ? 'Включить' : 'Заглушить'}
              actionIcon={c.isMuted ? 'bell' : 'bellOff'}
              revealPx={100}
              onAction={() => {
                setConvs(cs => cs.map(x => x.id === c.id ? { ...x, isMuted: !x.isMuted } : x));
              }}
            >
            <LongPressItem
              className="press"
              style={{
                border: '0.5px solid var(--border)',
                cursor: 'pointer', textAlign: 'left',
                background: 'var(--surface)', borderRadius: 'var(--r-lg)',
                color: 'var(--text)', fontFamily: 'inherit',
                overflow: 'hidden',
              }}
              onClick={() => setConvId(c.id)}
              items={[
                { label: c.unread ? 'Прочитано' : 'Не прочитано', icon: 'check',
                  onClick: () => setConvs(cs => cs.map(x => x.id === c.id ? { ...x, unread: c.unread ? 0 : 1 } : x)) },
                { label: c.isMuted ? 'Включить уведомления' : 'Заглушить', icon: c.isMuted ? 'bell' : 'bellOff',
                  onClick: () => setConvs(cs => cs.map(x => x.id === c.id ? { ...x, isMuted: !x.isMuted } : x)) },
                { label: 'В архив', icon: 'box',
                  onClick: () => setConvs(cs => cs.filter(x => x.id !== c.id)) },
                { label: 'Удалить', icon: 'trash', danger: true,
                  onClick: () => setConvs(cs => cs.filter(x => x.id !== c.id)) },
              ]}
            >
              <div style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{ position: 'relative' }}>
                  <Avatar initials={c.initials} bg={c.bg} color={c.color} size={48} />
                  {c.isOfficial && (
                    <div style={{
                      position: 'absolute', right: -2, bottom: -2,
                      width: 18, height: 18, borderRadius: 999,
                      background: 'var(--accent)', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      border: '2px solid var(--surface)',
                    }}>
                      <Icon name="check" size={11} color="#06120c" strokeWidth={3} />
                    </div>
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="row-between">
                    <div className="row" style={{ gap: 6, minWidth: 0 }}>
                      <span className="t-h3" style={{ fontSize: 15 }}>{c.name}</span>
                    </div>
                    <span className="t-small" style={{ color: 'var(--text-3)', fontSize: 12 }}>{c.lastTime}</span>
                  </div>
                  <div className="t-mini" style={{ marginTop: 1, color: 'var(--text-3)', fontWeight: 500, letterSpacing: 0.2, textTransform: 'none' }}>
                    {c.sub}{c.isMuted ? ' · приглушён' : ''}
                  </div>
                  <div className="row-between" style={{ marginTop: 6, gap: 8 }}>
                    <div className="t-small" style={{
                      color: c.unread ? 'var(--text)' : 'var(--text-2)',
                      fontWeight: c.unread ? 500 : 400,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                    }}>{c.last}</div>
                    {c.unread > 0 && <span className="badge">{c.unread}</span>}
                  </div>
                </div>
              </div>
            </LongPressItem>
            </SwipeRow>
          ))}
        </div>
        )}

        {!isEmpty && (
        <div style={{ padding: '24px 20px 8px' }}>
          <div className="t-small" style={{ color: 'var(--text-3)' }}>
            Администрация работает с 8:00 до 22:00. Тренеры отвечают в свободное время.
          </div>
        </div>
        )}
        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );
};

function ChatThread({ conv, onBack, onSend }) {
  const [text, setText] = React.useState('');
  const [typing, setTyping] = React.useState(false);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [conv.messages.length, typing]);

  const submit = () => {
    if (!text.trim()) return;
    const t = text.trim();
    onSend(t);
    setText('');
    // bot reply for Администрация
    if (conv.id === 'c1' && conv.botReplies && conv.botReplies.length) {
      setTimeout(() => setTyping(true), 600);
      const reply = conv.botReplies[Math.floor(Math.random() * conv.botReplies.length)];
      setTimeout(() => {
        setTyping(false);
        onSend(reply, 'them');
      }, 2200);
    }
  };

  const sendPhoto = () => {
    onSend('photo:gym-selfie', 'me', 'photo');
  };

  const openAttach = () => {
    // Bridge to App-level attachment sheet — pick callback bound below
    window.__attachPick = (kind) => {
      if (kind === 'photo' || kind === 'camera') sendPhoto();
      else if (kind === 'file') onSend('plan.pdf', 'me', 'photo'); // demo: file as photo bubble
      else if (kind === 'voice') onSend('🎤 Голосовое · 0:08', 'me');
    };
    window.__openChatAttach?.();
  };

  return (
    <div className="page">
      <StatusBar />
      {/* Top bar */}
      <div style={{
        paddingTop: 50, paddingBottom: 10,
        background: 'color-mix(in oklab, var(--bg) 88%, transparent)',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '0.5px solid var(--border)',
      }}>
        <div style={{ padding: '4px 12px', display: 'flex', alignItems: 'center', gap: 4 }}>
          <button onClick={onBack} aria-label="Назад к списку чатов" style={{
            width: 36, height: 36, borderRadius: 999, border: 0, background: 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}>
            <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
          </button>
          <div style={{ position: 'relative' }}>
            <Avatar initials={conv.initials} bg={conv.bg} color={conv.color} size={36} />
            <span style={{
              position: 'absolute', right: -1, bottom: -1, width: 10, height: 10,
              borderRadius: 999, background: 'var(--accent)',
              border: '2px solid var(--bg)',
            }} />
          </div>
          <div style={{ flex: 1, marginLeft: 4, minWidth: 0 }}>
            <div className="t-h3" style={{ fontSize: 15 }}>{conv.name}</div>
            <div className="t-mini" style={{ marginTop: 1, color: typing ? 'var(--accent-deep)' : 'var(--text-3)', textTransform: 'none', letterSpacing: 0.2, fontWeight: 500 }}>
              {typing ? 'печатает…' : `${conv.sub}${conv.isOfficial ? ' · ✓ верифицирован' : ' · в сети'}`}
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="scroller" style={{ padding: '14px 14px 14px' }}>
        <div className="stack-2">
          {conv.messages.map((m, i) => {
            if (m.kind === 'system') {
              return (
                <div key={m.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '8px 0' }}>
                  <div className="bubble bubble-system">
                    <div className="row" style={{ gap: 6, justifyContent: 'center' }}>
                      <Icon name="info" size={14} color="currentColor" strokeWidth={2} />
                      {m.body}
                    </div>
                  </div>
                  <div className="bubble-meta" style={{ marginTop: 4 }}>{m.time}</div>
                </div>
              );
            }
            if (m.kind === 'cancel') {
              return (
                <div key={m.id} style={{ margin: '8px 0', display: 'flex', justifyContent: 'center' }}>
                  <div className="bubble" style={{
                    background: 'var(--danger-soft, #fee2e2)', color: 'var(--danger)',
                    border: '0.5px solid color-mix(in oklab, var(--danger) 30%, transparent)',
                    maxWidth: 280, textAlign: 'center', fontSize: 13.5, lineHeight: 1.45,
                    fontWeight: 500,
                  }}>
                    <div className="row" style={{ gap: 6, justifyContent: 'center', marginBottom: 4 }}>
                      <Icon name="alert" size={14} color="currentColor" strokeWidth={2} />
                      <span style={{ fontWeight: 700, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' }}>Тренировка отменена</span>
                    </div>
                    {m.body}
                  </div>
                </div>
              );
            }
            const mine = m.from === 'me';
            const showTime = i === conv.messages.length - 1 || conv.messages[i+1]?.from !== m.from || conv.messages[i+1]?.time !== m.time;
            const isPhoto = m.kind === 'photo';
            return (
              <div key={m.id} style={{ display: 'flex', flexDirection: 'column', alignItems: mine ? 'flex-end' : 'flex-start' }}>
                {isPhoto ? (
                  <div className={`bubble ${mine ? 'bubble-me' : 'bubble-them'}`} style={{ padding: 4, overflow: 'hidden' }}>
                    <PhotoBubblePreview kind={m.photo} />
                    {m.body && !m.body.startsWith('photo:') && (
                      <div style={{ padding: '6px 10px 4px', fontSize: 14 }}>{m.body}</div>
                    )}
                  </div>
                ) : (
                  <div className={`bubble ${mine ? 'bubble-me' : 'bubble-them'}`}>{m.body}</div>
                )}
                {showTime && (
                  <div className="bubble-meta" style={{ marginTop: 3, display: 'flex', gap: 4, alignItems: 'center' }}>
                    <span>{m.time}</span>
                    {mine && (
                      m.read ? (
                        <svg width="16" height="11" viewBox="0 0 16 11" fill="none" style={{ marginBottom: -1 }}
                             role="img" aria-label="Прочитано">
                          <path d="M1 6l3 3 6-7" stroke="var(--accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                          <path d="M6 6l3 3 6-7" stroke="var(--accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                        </svg>
                      ) : (
                        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" style={{ marginBottom: -1 }}
                             role="img" aria-label="Доставлено">
                          <path d="M1 6l3 3 6-7" stroke="var(--text-3)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                        </svg>
                      )
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Typing indicator */}
          {typing && (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6 }}>
              <div className="bubble bubble-them" style={{ padding: '10px 14px' }}>
                <div className="typing-dots">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Quick replies for service tone */}
        {conv.id === 'c1' && !typing && (
          <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {['Расскажи про скидку', 'Когда сауна работает?', 'Спасибо!'].map(q => (
              <button key={q} onClick={() => onSend(q)} className="press" style={{
                border: '0.5px solid var(--border-strong)', background: 'var(--surface)',
                color: 'var(--text)', padding: '8px 14px', borderRadius: 999,
                fontSize: 13, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
              }}>{q}</button>
            ))}
          </div>
        )}

        <div style={{ height: 16 }} />
      </div>

      {/* Composer */}
      <div style={{
        padding: '8px 8px 14px', borderTop: '0.5px solid var(--border)',
        background: 'var(--bg)', display: 'flex', alignItems: 'flex-end', gap: 6,
      }}>
        <button onClick={openAttach} className="press" aria-label="Прикрепить" style={{
          width: 40, height: 40, borderRadius: 999, border: 0, background: 'transparent',
          color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', flexShrink: 0,
        }}>
          <Icon name="paperclip" size={20} color="currentColor" strokeWidth={1.8} />
        </button>
        <div style={{
          flex: 1, background: 'var(--surface)', borderRadius: 22,
          border: '0.5px solid var(--border-strong)', padding: '4px 8px 4px 16px',
          display: 'flex', alignItems: 'center', minHeight: 40,
        }}>
          <input
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="Сообщение"
            style={{
              flex: 1, border: 0, outline: 0, background: 'transparent',
              fontSize: 15, color: 'var(--text)', fontFamily: 'inherit',
              padding: '8px 0',
            }}
          />
        </div>
        <button onClick={text.trim() ? submit : () => onSend('🎤 Голосовое · 0:05', 'me')}
                aria-label={text.trim() ? 'Отправить' : 'Записать голосовое'}
                style={{
          width: 40, height: 40, borderRadius: 999, border: 0,
          background: text.trim() ? 'var(--accent)' : 'var(--surface-2)',
          color: text.trim() ? '#06120c' : 'var(--text-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', flexShrink: 0,
          transition: 'background 0.15s',
        }}>
          {text.trim() ? (
            <Icon name="send" size={18} color="currentColor" strokeWidth={2} />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <rect x="9" y="3" width="6" height="13" rx="3" stroke="currentColor" strokeWidth="1.8" />
              <path d="M5 11a7 7 0 0014 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          )}
        </button>
      </div>

      <style>{`
        .typing-dots { display: inline-flex; gap: 4px; align-items: center; }
        .typing-dots span {
          width: 7px; height: 7px; border-radius: 999px;
          background: var(--text-3);
          animation: typing-bounce 1.2s ease-in-out infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes typing-bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
          30% { transform: translateY(-3px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// Tiny inline preview for "photo" bubbles — abstract gradient
function PhotoBubblePreview({ kind }) {
  const presets = {
    'plan': { bg: 'linear-gradient(135deg, #fde68a 0%, #f59e0b 60%, #ea580c 100%)', label: 'PLAN.pdf', sub: 'программа на завтра' },
    'gym-selfie': { bg: 'linear-gradient(135deg, #cbd5e1 0%, #475569 70%, #1e293b 100%)', label: 'IMG_4821.jpg', sub: 'отправлено сейчас' },
  };
  const p = presets[kind] || presets['gym-selfie'];
  return (
    <div style={{
      width: 220, height: 140, borderRadius: 14, position: 'relative',
      background: p.bg, overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(120% 80% at 70% 25%, rgba(255,255,255,0.35), transparent 60%)',
      }} />
      <div style={{
        position: 'absolute', left: 10, bottom: 8, color: '#fff',
        fontSize: 11, fontWeight: 600, letterSpacing: 0.3,
        textShadow: '0 1px 2px rgba(0,0,0,0.5)',
      }}>
        <div>{p.label}</div>
        <div style={{ opacity: 0.85, fontWeight: 500 }}>{p.sub}</div>
      </div>
    </div>
  );
}

