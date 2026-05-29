import { StatusBar } from './StatusBar.jsx';

// ─── Skeleton primitives ─────────────────────────────────────────
export function SkLine({ w = '100%', h = 12, style }) {
  return <div className="sk sk-line" style={{ width: w, height: h, ...style }} />;
}
export function SkBlock({ w = '100%', h = 80, r = 18, style }) {
  return <div className="sk" style={{ width: w, height: h, borderRadius: r, ...style }} />;
}
export function SkCircle({ size = 44, style }) {
  return <div className="sk sk-circle" style={{ width: size, height: size, ...style }} />;
}

export function HomeSkeleton() {
  return (
    <div className="page">
      <div className="scroller" style={{ paddingTop: 54 }}>
        <div style={{ padding: '8px 20px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <SkLine w={90} h={11} />
            <SkLine w={150} h={22} />
          </div>
          <SkCircle size={44} />
        </div>
        <div style={{ padding: '0 16px 12px' }}><SkBlock h={120} r={20} /></div>
        <div style={{ padding: '0 16px 12px' }}><SkBlock h={68} r={20} /></div>
        <div style={{ padding: '0 16px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <SkBlock h={84} r={18} />
          <SkBlock h={84} r={18} />
        </div>
        <div style={{ padding: '8px 20px 6px' }}><SkLine w={90} h={10} /></div>
        <div style={{ padding: '0 16px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <SkBlock h={64} r={16} />
          <SkBlock h={64} r={16} />
        </div>
      </div>
    </div>
  );
}

export function ListSkeleton({ rows = 5, withHero = false }) {
  return (
    <div className="page">
      <div className="scroller" style={{ paddingTop: 54 }}>
        {withHero && (
          <div style={{ padding: '8px 20px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <SkLine w={120} h={12} />
            <SkLine w={200} h={26} />
          </div>
        )}
        <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 16px', background: 'var(--surface)',
              borderRadius: 18, border: '0.5px solid var(--border)',
            }}>
              <SkCircle size={42} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <SkLine w="60%" h={12} />
                <SkLine w="40%" h={10} />
              </div>
              <SkLine w={40} h={10} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="page">
      <div className="scroller" style={{ paddingTop: 54 }}>
        <div style={{ padding: '8px 20px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <SkCircle size={64} />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <SkLine w="50%" h={16} />
            <SkLine w="35%" h={11} />
          </div>
        </div>
        <div style={{ padding: '0 16px 12px' }}><SkBlock h={140} r={20} /></div>
        <div style={{ padding: '4px 16px 12px' }}><SkBlock h={44} r={999} /></div>
        <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <SkBlock key={i} h={56} r={16} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Sheet skeleton ──────────────────────────────────────────────
// Generic skeleton matching the sheet chrome (status bar + close + title)
// + a flexible body shape. Used to bridge sheet-open with brief loading.
export function SheetSkeleton({ variant = 'list', title = true }) {
  return (
    <div
      className="sheet sheet-sk-fade"
      style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}
    >
      <StatusBar />
      <div style={{
        padding: '8px 12px 0', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between', height: 56,
      }}>
        <div className="sk sk-circle" style={{ width: 36, height: 36 }} />
        {title && <SkLine w={110} h={14} />}
        <div style={{ width: 36 }} />
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        {variant === 'list' && <SheetSkBodyList />}
        {variant === 'detail' && <SheetSkBodyDetail />}
        {variant === 'plans' && <SheetSkBodyPlans />}
        {variant === 'qr' && <SheetSkBodyQR />}
        {variant === 'checkout' && <SheetSkBodyCheckout />}
        {variant === 'thread' && <SheetSkBodyThread />}
      </div>
    </div>
  );
}

export function SheetSkBodyList() {
  return (
    <div style={{ padding: '8px 20px 16px' }}>
      <SkLine w={140} h={26} style={{ marginBottom: 18 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '14px 16px', background: 'var(--surface)',
            borderRadius: 18, border: '0.5px solid var(--border)',
          }}>
            <SkCircle size={42} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <SkLine w="55%" h={12} />
              <SkLine w="35%" h={10} />
            </div>
            <SkLine w={40} h={10} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SheetSkBodyDetail() {
  return (
    <div style={{ padding: '12px 16px 16px' }}>
      <SkBlock h={180} r={20} style={{ marginBottom: 14 }} />
      <SkLine w={200} h={22} style={{ marginBottom: 10 }} />
      <SkLine w={140} h={12} style={{ marginBottom: 22 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SkLine w="100%" h={11} />
        <SkLine w="92%" h={11} />
        <SkLine w="80%" h={11} />
      </div>
      <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <SkBlock h={64} r={16} />
        <SkBlock h={64} r={16} />
      </div>
    </div>
  );
}

export function SheetSkBodyPlans() {
  return (
    <div style={{ padding: '12px 16px 16px' }}>
      <SkLine w={160} h={11} style={{ marginBottom: 16 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <SkBlock key={i} h={120} r={22} />
        ))}
      </div>
      <div style={{ marginTop: 22 }}>
        <SkBlock h={52} r={999} />
      </div>
    </div>
  );
}

export function SheetSkBodyQR() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '0 24px',
      height: '100%',
    }}>
      <SkLine w={100} h={11} style={{ marginBottom: 24 }} />
      <div style={{
        padding: 24, background: 'var(--surface)', borderRadius: 28,
        boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
      }}>
        <div className="sk" style={{ width: 240, height: 240, borderRadius: 14 }} />
      </div>
      <SkLine w={140} h={22} style={{ marginTop: 28 }} />
      <SkLine w={100} h={10} style={{ marginTop: 8 }} />
    </div>
  );
}

export function SheetSkBodyCheckout() {
  return (
    <div style={{ padding: '12px 16px 16px' }}>
      <SkBlock h={80} r={18} style={{ marginBottom: 16 }} />
      <SkLine w={100} h={10} style={{ marginBottom: 10 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SkBlock h={56} r={16} />
        <SkBlock h={56} r={16} />
        <SkBlock h={56} r={16} />
      </div>
      <div style={{ marginTop: 22 }}>
        <SkLine w={80} h={11} style={{ marginBottom: 10 }} />
        <SkBlock h={68} r={16} />
      </div>
      <div style={{ marginTop: 22 }}>
        <SkBlock h={52} r={999} />
      </div>
    </div>
  );
}

export function SheetSkBodyThread() {
  return (
    <div style={{ padding: '12px 16px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <SkBlock h={48} r={16} style={{ alignSelf: 'flex-start', width: '60%' }} />
      <SkBlock h={36} r={16} style={{ alignSelf: 'flex-end', width: '40%' }} />
      <SkBlock h={64} r={16} style={{ alignSelf: 'flex-start', width: '75%' }} />
      <SkBlock h={48} r={16} style={{ alignSelf: 'flex-end', width: '52%' }} />
      <SkBlock h={40} r={16} style={{ alignSelf: 'flex-start', width: '46%' }} />
    </div>
  );
}
