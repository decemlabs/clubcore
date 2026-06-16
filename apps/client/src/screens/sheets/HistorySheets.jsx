import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { FilterChips } from '@/components/FilterChips.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { SearchBar } from '@/components/SearchBar.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { TRAINING_HISTORY, VISIT_HISTORY } from '@/data';
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx';

// ─── Visit history ──────────────────────────────────────────
export const VisitHistorySheet = ({ onClose }) => {
  const visits = VISIT_HISTORY;
  const [query, setQuery] = React.useState('');
  const [filter, setFilter] = React.useState('all');

  // Apply filter then search
  const filtered = visits.filter(v => {
    const q = query.toLowerCase().trim();
    const matchQ = !q || v.kind.toLowerCase().includes(q) || v.date.toLowerCase().includes(q);
    let matchF = true;
    if (filter === 'trainer') matchF = !!v.trainer;
    if (filter === 'solo')    matchF = !v.trainer;
    return matchQ && matchF;
  });

  const total = filtered.length;
  const totalMin = filtered.reduce((s, v) => {
    const m = v.duration.match(/(\d+)ч\s*(\d+)м/);
    return s + (m ? parseInt(m[1]) * 60 + parseInt(m[2]) : 0);
  }, 0);
  const totalH = Math.floor(totalMin / 60);
  const trainerVisits = filtered.filter(v => v.trainer).length;

  // Group by week-ish (only when no filter)
  const isFiltered = query || filter !== 'all';
  const groups = isFiltered
    ? [{ label: `Найдено · ${filtered.length}`, items: filtered }]
    : [
        { label: 'Эта неделя',    items: filtered.slice(0, 2) },
        { label: 'Прошлая неделя', items: filtered.slice(2, 4) },
        { label: 'Ранее',          items: filtered.slice(4) },
      ].filter(g => g.items.length > 0);

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="История посещений" onClose={onClose} />

      <PullToRefresh
        scrollPaddingTop={0}
        onRefresh={() => new Promise(r => setTimeout(r, 700))}
      >
        {/* Search + filters */}
        <div style={{ padding: '8px 16px 6px' }}>
          <SearchBar value={query} onChange={setQuery}
                     placeholder="Поиск по дате или типу" />
        </div>
        <div style={{ padding: '4px 16px 6px' }}>
          <FilterChips value={filter} onChange={setFilter} options={[
            { id: 'all',     label: 'Все',           count: visits.length },
            { id: 'trainer', label: 'С тренером',    icon: 'user', count: visits.filter(v => v.trainer).length },
            { id: 'solo',    label: 'Самостоятельно', icon: 'qr',  count: visits.filter(v => !v.trainer).length },
          ]} />
        </div>

        {/* Summary — only when not filtering */}
        {!isFiltered && (
          <div style={{ padding: '8px 16px 16px' }}>
            <div className="card" style={{ padding: 16 }}>
              <div className="t-mini" style={{ color: 'var(--text-3)' }}>За последний месяц</div>
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 12, marginTop: 10,
              }}>
                <SummaryCol big={total} sub="визитов" />
                <SummaryCol big={`${totalH}ч`} sub="в зале" />
                <SummaryCol big={trainerVisits} sub="с тренером" tone="accent" />
              </div>
              <div style={{ marginTop: 14 }}>
                <div className="t-mini" style={{ color: 'var(--text-3)', marginBottom: 8 }}>
                  Активность по дням
                </div>
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
                  gap: 6, alignItems: 'end', height: 48,
                }}>
                  {[0.3, 0.0, 0.6, 0.0, 0.9, 0.4, 0.0].map((h, i) => (
                    <div key={i} style={{
                      height: `${h * 100}%`,
                      background: h > 0 ? 'var(--accent)' : 'var(--surface-2)',
                      borderRadius: 6,
                      minHeight: 6,
                    }} />
                  ))}
                </div>
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
                  gap: 6, marginTop: 6,
                }}>
                  {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(d => (
                    <div key={d} className="t-mini" style={{
                      textAlign: 'center', color: 'var(--text-3)',
                      fontSize: 9.5, textTransform: 'none', letterSpacing: 0,
                    }}>{d}</div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {filtered.length === 0 && (
          <div style={{ padding: '40px 24px', textAlign: 'center' }}>
            <div style={{
              width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
              background: 'var(--surface-2)', color: 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="history" size={28} color="currentColor" />
            </div>
            <div className="t-h3" style={{ fontSize: 16 }}>Ничего не нашлось</div>
            <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
              Попробуй другие слова или сними фильтр.
            </div>
            <button onClick={() => { setQuery(''); setFilter('all'); }}
                    className="press"
                    style={{
                      marginTop: 16, padding: '8px 18px', fontSize: 13, fontWeight: 600,
                      border: '0.5px solid var(--border-strong)', background: 'transparent',
                      color: 'var(--text)', borderRadius: 999, cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}>Сбросить</button>
          </div>
        )}

        {/* Groups */}
        {groups.map(g => (
          <div key={g.label} style={{ padding: '0 16px 14px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
              {g.label}
            </div>
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {g.items.map((v, i) => (
                <React.Fragment key={v.id}>
                  {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 56 }} />}
                  <VisitRow v={v} />
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}
        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );
};

function VisitRow({ v }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'center' }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: v.trainer ? 'var(--accent-soft)' : 'var(--surface-2)',
        color: v.trainer ? 'var(--accent-deep)' : 'var(--text-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={v.trainer ? 'user' : 'qr'} size={16} color="currentColor" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{v.date}</div>
        <div className="t-small" style={{ marginTop: 1, fontSize: 12 }}>
          {v.time} · {v.kind}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="t-h3 t-num" style={{ fontSize: 14, fontWeight: 600 }}>{v.duration}</div>
        <div className="t-mini" style={{
          fontSize: 9.5, color: 'var(--text-3)',
          textTransform: 'none', letterSpacing: 0,
        }}>в зале</div>
      </div>
    </div>
  );
}

function SummaryCol({ big, sub, tone }) {
  return (
    <div>
      <div className="t-h1 t-num" style={{
        fontSize: 22, letterSpacing: -0.4,
        color: tone === 'accent' ? 'var(--accent-deep)' : 'var(--text)',
      }}>{big}</div>
      <div className="t-mini" style={{
        color: 'var(--text-3)', marginTop: 2,
        textTransform: 'none', letterSpacing: 0,
      }}>{sub}</div>
    </div>
  );
}

// ─── Training history (with trainers) ──────────────────────
export const TrainingHistorySheet = ({ onClose }) => {
  const list = TRAINING_HISTORY;
  const [query, setQuery] = React.useState('');
  const [filter, setFilter] = React.useState('all');

  const filtered = list.filter(t => {
    const q = query.toLowerCase().trim();
    const matchQ = !q ||
      t.trainer.toLowerCase().includes(q) ||
      t.focus.toLowerCase().includes(q) ||
      (t.notes || '').toLowerCase().includes(q);
    let matchF = true;
    if (filter === 'with-notes') matchF = !!t.notes;
    if (filter === 'recent')     matchF = /(сегодня|вчера|нед)/i.test(t.date);
    return matchQ && matchF;
  });

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Тренировки с тренером" onClose={onClose} />

      <PullToRefresh
        scrollPaddingTop={0}
        onRefresh={() => new Promise(r => setTimeout(r, 700))}
      >
        {/* Search + filters */}
        <div style={{ padding: '8px 16px 6px' }}>
          <SearchBar value={query} onChange={setQuery}
                     placeholder="Тренер, фокус или заметка" />
        </div>
        <div style={{ padding: '4px 16px 6px' }}>
          <FilterChips value={filter} onChange={setFilter} options={[
            { id: 'all',         label: 'Все',                count: list.length },
            { id: 'recent',      label: 'Недавние',            icon: 'clock', count: list.filter(t => /(сегодня|вчера|нед)/i.test(t.date)).length },
            { id: 'with-notes',  label: 'С заметкой',          icon: 'info',  count: list.filter(t => t.notes).length },
          ]} />
        </div>

        {/* Stats — only when not filtering */}
        {(!query && filter === 'all') && (
          <div style={{ padding: '8px 16px 14px' }}>
            <div className="card" style={{ padding: 16 }}>
              <div className="row" style={{ gap: 18, alignItems: 'flex-end' }}>
                <div>
                  <div className="t-mini" style={{ color: 'var(--text-3)' }}>Всего</div>
                  <div className="t-display t-num" style={{
                    fontSize: 32, letterSpacing: -0.6, marginTop: 2,
                  }}>{list.length}</div>
                </div>
                <div style={{ flex: 1 }}>
                  <div className="t-mini" style={{ color: 'var(--text-3)' }}>Любимый тренер</div>
                  <div className="row" style={{ marginTop: 6, gap: 8 }}>
                    <Avatar initials="АС" bg="#fef3c7" color="#f59e0b" size={28} />
                    <span className="t-h3" style={{ fontSize: 14 }}>Аня Соколова</span>
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 14, padding: 12,
                            background: 'var(--surface-2)', borderRadius: 12 }}>
                <div className="t-small" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
                  💪 Серия из <b style={{ color: 'var(--text)' }}>3 недель</b> подряд.
                  Так держать!
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {filtered.length === 0 && (
          <div style={{ padding: '40px 24px', textAlign: 'center' }}>
            <div style={{
              width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
              background: 'var(--surface-2)', color: 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="user" size={28} color="currentColor" />
            </div>
            <div className="t-h3" style={{ fontSize: 16 }}>Тренировок не найдено</div>
            <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
              Попробуй другие слова или сними фильтр.
            </div>
            <button onClick={() => { setQuery(''); setFilter('all'); }}
                    className="press"
                    style={{
                      marginTop: 16, padding: '8px 18px', fontSize: 13, fontWeight: 600,
                      border: '0.5px solid var(--border-strong)', background: 'transparent',
                      color: 'var(--text)', borderRadius: 999, cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}>Сбросить</button>
          </div>
        )}

        {/* List */}
        {filtered.length > 0 && (
          <div style={{ padding: '0 16px 14px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
              {query || filter !== 'all' ? `Найдено · ${filtered.length}` : 'История'}
            </div>
            <div className="stack-3">
              {filtered.map(t => <TrainingCard key={t.id} t={t} />)}
            </div>
          </div>
        )}
        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );
};

function TrainingCard({ t }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
        <Avatar initials={t.initials} bg={t.bg} color={t.color} size={40} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 8 }}>
            <div className="t-h3" style={{ fontSize: 15 }}>{t.trainer}</div>
            <div className="t-mini" style={{
              color: 'var(--text-3)', fontSize: 10,
              textTransform: 'none', letterSpacing: 0, fontWeight: 500, flexShrink: 0,
            }}>{t.date}</div>
          </div>
          <div className="t-small" style={{ marginTop: 2, color: 'var(--text-2)' }}>
            {t.focus}
          </div>
          {t.notes && (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: 'var(--surface-2)', borderRadius: 10,
              borderLeft: '2px solid var(--accent)',
            }}>
              <div className="t-mini" style={{
                color: 'var(--accent-deep)', fontSize: 9,
              }}>ЗАМЕТКА ОТ ТРЕНЕРА</div>
              <div className="t-small" style={{
                marginTop: 2, color: 'var(--text-2)', lineHeight: 1.45,
              }}>
                {t.notes}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

