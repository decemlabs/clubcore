import React, { Suspense, lazy, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';

import '@/styles.css';

import { HomeIndicator } from '@/components/HomeIndicator.jsx';
import { TabBar } from '@/components/TabBar.jsx';
import { SheetGate } from '@/components/SheetGate.jsx';
import { PushToast } from '@/components/PushToast.jsx';
import { HomeSkeleton, ListSkeleton, ProfileSkeleton } from '@/components/skeletons.jsx';

import { useTweaksCtx } from '@/context/TweaksContext.jsx';
import { useUI } from '@/context/UIContext.jsx';
import { useAuth } from '@/context/AuthContext.jsx';
import { RequireAuth } from '@/context/RequireAuth.jsx';

import { CONVERSATIONS, TRAINERS } from '@/data';

import { TweaksRoot } from '@/components/Tweaks/TweaksRoot.jsx';

// ── Payment return route (ЮKassa return_url target) ───────────────────────
const PaymentReturnScreen = lazy(() =>
  import('@/routes/PaymentReturnScreen.jsx').then(m => ({ default: m.PaymentReturnScreen }))
);

// ── Login screen ───────────────────────────────────────────────────────────
const LoginScreen = lazy(() =>
  import('@/screens/LoginScreen.jsx').then(m => ({ default: m.LoginScreen }))
);

// ── Onboarding screen (D-04 — newbie first-login questionnaire) ────────────
const OnboardingScreen = lazy(() =>
  import('@/screens/OnboardingScreen.jsx').then(m => ({ default: m.OnboardingScreen }))
);

// ── Lazy tab screens — each is its own chunk ───────────────────────────────
const HomeScreen     = lazy(() => import('@/screens/HomeScreen.jsx').then(m => ({ default: m.HomeScreen })));
const BookScreen     = lazy(() => import('@/screens/BookScreen.jsx').then(m => ({ default: m.BookScreen })));
const ChatScreen     = lazy(() => import('@/screens/ChatScreen.jsx').then(m => ({ default: m.ChatScreen })));
const ProfileScreen  = lazy(() => import('@/screens/ProfileScreen.jsx').then(m => ({ default: m.ProfileScreen })));

// ── Lazy sheets ────────────────────────────────────────────────────────────
const QRSheet              = lazy(() => import('@/screens/sheets/QRSheet.jsx').then(m => ({ default: m.QRSheet })));
const PlansSheet           = lazy(() => import('@/screens/sheets/PlansSheet.jsx').then(m => ({ default: m.PlansSheet })));
const BookingManageSheet   = lazy(() => import('@/screens/sheets/BookingManageSheet.jsx').then(m => ({ default: m.BookingManageSheet })));
const ReferralSheet        = lazy(() => import('@/screens/sheets/ReferralSheet.jsx').then(m => ({ default: m.ReferralSheet })));
const GymInfoSheet         = lazy(() => import('@/screens/sheets/GymInfoSheet.jsx').then(m => ({ default: m.GymInfoSheet })));
const NotificationsSheet   = lazy(() => import('@/screens/sheets/NotificationsSheet.jsx').then(m => ({ default: m.NotificationsSheet })));
const TrainerDetailSheet   = lazy(() => import('@/screens/sheets/TrainerDetailSheet.jsx').then(m => ({ default: m.TrainerDetailSheet })));
const CheckoutSheet        = lazy(() => import('@/screens/sheets/CheckoutSheet.jsx').then(m => ({ default: m.CheckoutSheet })));
const PersonalDataSheet    = lazy(() => import('@/screens/sheets/ProfileExtraSheets.jsx').then(m => ({ default: m.PersonalDataSheet })));
const CardSheet            = lazy(() => import('@/screens/sheets/ProfileExtraSheets.jsx').then(m => ({ default: m.CardSheet })));
const FAQSheet             = lazy(() => import('@/screens/sheets/ProfileExtraSheets.jsx').then(m => ({ default: m.FAQSheet })));
const VisitHistorySheet    = lazy(() => import('@/screens/sheets/HistorySheets.jsx').then(m => ({ default: m.VisitHistorySheet })));
const TrainingHistorySheet = lazy(() => import('@/screens/sheets/HistorySheets.jsx').then(m => ({ default: m.TrainingHistorySheet })));

// Flows live in one chunk — they reference each other heavily.
const Flows = {
  Booking:     lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.BookingConfirmedSheet }))),
  Receipt:     lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.ReceiptSheet }))),
  Cancel:      lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.CancelBookingSheet }))),
  SubManage:   lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.SubManageSheet }))),
  Payments:    lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.PaymentMethodsSheet }))),
  Delete:      lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.DeleteAccountSheet }))),
  Sms:         lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.SmsVerifySheet }))),
  Review:      lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.ReviewSheet }))),
  TrainerCx:   lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.TrainerCancelledSheet }))),
  Attach:      lazy(() => import('@/screens/sheets/flows.jsx').then(m => ({ default: m.ChatAttachSheet }))),
};

// ── Tab → route mapping ────────────────────────────────────────────────────
const TAB_BY_PATH = { '/home': 'home', '/book': 'book', '/chat': 'chat', '/profile': 'profile' };
const PATH_BY_TAB = { home: '/home', book: '/book', chat: '/chat', profile: '/profile' };

function useTabFromRoute() {
  const { pathname } = useLocation();
  return TAB_BY_PATH[pathname] || 'home';
}

function useTabLoading() {
  // Brief skeleton state on tab change — feels like a real app fetching.
  const tab = useTabFromRoute();
  const [loading, setLoading] = React.useState(false);
  const skipFirst = React.useRef(true);
  useEffect(() => {
    if (skipFirst.current) { skipFirst.current = false; return; }
    setLoading(true);
    const id = setTimeout(() => setLoading(false), 320);
    return () => clearTimeout(id);
  }, [tab]);
  return loading;
}

// ── Screen wrappers — bind route → screen with context-derived props ───────
function HomeRoute() {
  const { t, setTweak } = useTweaksCtx();
  const ui = useUI();
  const navigate = useNavigate();
  return (
    <HomeScreen
      tweaks={t}
      setTweak={setTweak}
      onOpenQR={() => ui.setQrOpen(true)}
      onOpenPlans={() => ui.setPlansOpen(true)}
      onOpenManage={() => ui.setManageOpen(true)}
      onOpenReferral={() => ui.setReferralOpen(true)}
      onOpenGymInfo={() => ui.setGymInfoOpen(true)}
      onOpenNotifications={() => ui.setNotifsOpen(true)}
      onTab={(id) => navigate(PATH_BY_TAB[id] || '/home')}
    />
  );
}

function BookRoute() {
  const ui = useUI();
  const navigate = useNavigate();
  return (
    <BookScreen
      onTab={(id) => navigate(PATH_BY_TAB[id] || '/home')}
      onOpenManage={() => ui.setManageOpen(true)}
      onOpenTrainer={(tr) => ui.setTrainerDetail(tr)}
      onCheckout={(ctx) => ui.setCheckoutCtx(ctx)}
      onConfirmFlow={ui.setBookConfirmOpen}
      onOpenPlans={() => ui.setPlansOpen(true)}
    />
  );
}

function ChatRoute() {
  const { t } = useTweaksCtx();
  const ui = useUI();
  return (
    <ChatScreen
      tweaks={t}
      initialConv={ui.pendingChat}
      onClearInitial={() => ui.setPendingChat(null)}
      onThreadOpen={ui.setChatThreadOpen}
    />
  );
}

function ProfileRoute() {
  const { t, setTweak } = useTweaksCtx();
  const ui = useUI();
  return (
    <ProfileScreen
      tweaks={t}
      setTweak={setTweak}
      onOpenPlans={() => ui.setPlansOpen(true)}
      onOpenReferral={() => ui.setReferralOpen(true)}
      onOpenGymInfo={() => ui.setGymInfoOpen(true)}
      onOpenPersonalData={() => ui.setPersonalOpen(true)}
      onOpenCard={() => ui.setCardOpen(true)}
      onOpenFAQ={() => ui.setFaqOpen(true)}
      onOpenVisitHistory={() => ui.setVisitHistOpen(true)}
      onOpenTrainingHistory={() => ui.setTrainHistOpen(true)}
    />
  );
}

// Lazy-routed fallback per tab — matches original skeleton variants.
function TabFallback({ tab }) {
  if (tab === 'home') return <HomeSkeleton />;
  if (tab === 'profile') return <ProfileSkeleton />;
  return <ListSkeleton rows={5} withHero />;
}

// ── Top-level shell ────────────────────────────────────────────────────────
export default function App() {
  const { t, setTweak } = useTweaksCtx();
  const ui = useUI();
  const { status } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const tab = useTabFromRoute();
  const tabLoading = useTabLoading();

  // React to pushKind tweak — show toast when value changes from 'idle'.
  useEffect(() => {
    if (t.pushKind && t.pushKind !== 'idle') ui.setPushKind(t.pushKind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t.pushKind]);

  const handleTab = (id) => {
    if (id === 'chat') ui.setPendingChat(null);
    navigate(PATH_BY_TAB[id] || '/home');
  };

  const unreadChat = CONVERSATIONS.reduce((s, c) => s + (c.unread || 0), 0);

  // Push tap routing
  const handlePushTap = () => {
    const k = ui.pushKind;
    if (k === 'message') {
      handleTab('chat');
      setTimeout(() => ui.setPendingChat('c2'), 360);
    } else if (k === 'promo') {
      ui.setPlansOpen(true);
    } else if (k === 'schedule') {
      handleTab('book');
    } else if (k === 'cancel') {
      setTweak('gymEvent', 'trainer-cancelled');
      handleTab('home');
    }
  };

  // Hide tab bar on sheets, login screen, onboarding, or while loading auth
  const isLoginRoute = pathname === '/login';
  const isOnboardingRoute = pathname === '/onboarding';
  const hideTabBar = ui.anySheetOpen || ui.chatThreadOpen || ui.bookConfirmOpen
    || isLoginRoute || isOnboardingRoute || status === 'unknown' || status === 'anon';

  return (
    <div className="stage" data-screen-label="Прототип">
      <div
        data-screen-label={`01 ${tab}`}
        style={{
          width: 390, height: 844, position: 'relative',
          borderRadius: 54, background: '#0a0a0a', padding: 12,
          boxShadow: '0 50px 100px rgba(28,25,23,0.25), 0 0 0 1px rgba(28,25,23,0.15)',
        }}
      >
        <div style={{ position: 'absolute', inset: 12, borderRadius: 44, overflow: 'hidden', background: 'var(--bg)' }}>
          {/* Dynamic island */}
          <div style={{
            position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
            width: 120, height: 32, borderRadius: 999, background: '#000', zIndex: 300,
            pointerEvents: 'none',
          }} />

          <div className="screen">
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              {/* Routed tab screen (with a brief tab-loading skeleton on transitions) */}
              {tabLoading ? <TabFallback tab={tab} /> : (
                <Suspense fallback={<TabFallback tab={tab} />}>
                  <Routes>
                    {/* Public routes — no auth guard */}
                    <Route path="/login" element={<LoginScreen />} />
                    <Route path="/"     element={<Navigate to="/home" replace />} />

                    {/* Protected tab routes */}
                    <Route path="/home"    element={<RequireAuth><HomeRoute /></RequireAuth>} />
                    <Route path="/book"    element={<RequireAuth><BookRoute /></RequireAuth>} />
                    <Route path="/chat"    element={<RequireAuth><ChatRoute /></RequireAuth>} />
                    <Route path="/profile" element={<RequireAuth><ProfileRoute /></RequireAuth>} />
                    <Route path="/payment/return" element={<RequireAuth><PaymentReturnScreen /></RequireAuth>} />
                    {/* Onboarding questionnaire — D-04: newbie first-login + manual re-entry */}
                    <Route path="/onboarding" element={<RequireAuth><OnboardingScreen /></RequireAuth>} />

                    {/* Catch-all: anon → /login via RequireAuth; authed → /home */}
                    <Route path="*" element={
                      <RequireAuth>
                        <Navigate to="/home" replace />
                      </RequireAuth>
                    } />
                  </Routes>
                </Suspense>
              )}

              {/* ─── Lazy-loaded sheet overlays ─── */}
              <Suspense fallback={null}>
                <SheetGate open={ui.qrOpen} variant="qr">
                  <QRSheet onClose={() => ui.setQrOpen(false)} userName={t.userName} />
                </SheetGate>
                <SheetGate open={ui.plansOpen} variant="plans">
                  <PlansSheet
                    onClose={() => ui.setPlansOpen(false)}
                    currentPlanId={t.subState === 'active' ? 'annual' : 'monthly'}
                    onPick={(plan) => {
                      ui.setPlansOpen(false)
                      ui.setCheckoutCtx({
                        kind: plan.kind,
                        planId: plan.id,
                        title: plan.name,
                        subtitle: plan.period,
                        amount: plan.priceKopecks,
                      })
                    }}
                  />
                </SheetGate>
                <SheetGate open={ui.manageOpen} variant="detail">
                  <BookingManageSheet
                    onClose={() => ui.setManageOpen(false)}
                    onCancelled={() => { ui.setManageOpen(false); handleTab('home'); }}
                    onRescheduled={() => { ui.setManageOpen(false); handleTab('home'); }}
                    onChat={() => { ui.setManageOpen(false); handleTab('chat'); setTimeout(() => ui.setPendingChat('c2'), 360); }}
                    onRules={() => { ui.setManageOpen(false); ui.setFaqOpen(true); }}
                  />
                </SheetGate>
                <SheetGate open={ui.referralOpen} variant="detail">
                  <ReferralSheet onClose={() => ui.setReferralOpen(false)} userName={t.userName} />
                </SheetGate>
                <SheetGate open={ui.gymInfoOpen} variant="detail">
                  <GymInfoSheet onClose={() => ui.setGymInfoOpen(false)} />
                </SheetGate>
                <SheetGate open={ui.notifsOpen} variant="list">
                  <NotificationsSheet
                    onClose={() => ui.setNotifsOpen(false)}
                    onOpenChat={() => { ui.setNotifsOpen(false); handleTab('chat'); }}
                  />
                </SheetGate>
                <SheetGate open={!!ui.trainerDetail} variant="detail" keyFor={ui.trainerDetail?.id}>
                  <TrainerDetailSheet
                    trainer={ui.trainerDetail}
                    onClose={() => ui.setTrainerDetail(null)}
                    onBook={() => { ui.setTrainerDetail(null); handleTab('book'); }}
                    onCheckout={(ctx) => { ui.setTrainerDetail(null); ui.setCheckoutCtx(ctx); }}
                  />
                </SheetGate>
                <SheetGate open={!!ui.checkoutCtx} variant="checkout" keyFor={ui.checkoutCtx?.title}>
                  <CheckoutSheet
                    ctx={ui.checkoutCtx}
                    onClose={() => ui.setCheckoutCtx(null)}
                    forceOutcome={t.paymentOutcome === 'ok' ? null : t.paymentOutcome}
                  />
                </SheetGate>
                <SheetGate open={ui.personalOpen} variant="detail">
                  <PersonalDataSheet
                    onClose={() => ui.setPersonalOpen(false)}
                    userName={t.userName}
                    setTweak={setTweak}
                  />
                </SheetGate>
                <SheetGate open={ui.cardOpen} variant="detail">
                  <CardSheet onClose={() => ui.setCardOpen(false)} />
                </SheetGate>
                <SheetGate open={ui.faqOpen} variant="list">
                  <FAQSheet
                    onClose={() => ui.setFaqOpen(false)}
                    onOpenChat={() => { ui.setFaqOpen(false); handleTab('chat'); }}
                  />
                </SheetGate>
                <SheetGate open={ui.visitHistOpen} variant="list">
                  <VisitHistorySheet onClose={() => ui.setVisitHistOpen(false)} />
                </SheetGate>
                <SheetGate open={ui.trainHistOpen} variant="list">
                  <TrainingHistorySheet onClose={() => ui.setTrainHistOpen(false)} />
                </SheetGate>

                {/* Flows */}
                <SheetGate open={!!ui.cancelBookingOpen} variant="detail">
                  <Flows.Cancel
                    booking={typeof ui.cancelBookingOpen === 'object' ? ui.cancelBookingOpen : null}
                    onClose={() => ui.setCancelBookingOpen(false)}
                    onConfirm={() => ui.setCancelBookingOpen(false)}
                  />
                </SheetGate>
                <SheetGate open={!!ui.subManageMode} variant="detail" keyFor={ui.subManageMode}>
                  <Flows.SubManage
                    mode={ui.subManageMode}
                    onClose={() => ui.setSubManageMode(null)}
                    onConfirm={() => ui.setSubManageMode(null)}
                  />
                </SheetGate>
                <SheetGate open={ui.paymentMethodsOpen} variant="list">
                  <Flows.Payments onClose={() => ui.setPaymentMethodsOpen(false)} />
                </SheetGate>
                <SheetGate open={ui.deleteAccountOpen} variant="detail">
                  <Flows.Delete
                    onClose={() => ui.setDeleteAccountOpen(false)}
                    onDeleted={() => ui.setDeleteAccountOpen(false)}
                  />
                </SheetGate>
                <SheetGate open={!!ui.smsVerifyCtx} variant="detail" keyFor={ui.smsVerifyCtx?.target}>
                  <Flows.Sms
                    channel={ui.smsVerifyCtx?.channel}
                    target={ui.smsVerifyCtx?.target}
                    onClose={() => ui.setSmsVerifyCtx(null)}
                    onVerified={() => ui.setSmsVerifyCtx(null)}
                  />
                </SheetGate>
                <SheetGate open={!!ui.reviewCtx} variant="detail">
                  <Flows.Review
                    training={ui.reviewCtx}
                    onClose={() => ui.setReviewCtx(null)}
                    onSubmit={() => ui.setReviewCtx(null)}
                  />
                </SheetGate>
                <SheetGate open={ui.trainerCancelledOpen} variant="detail">
                  <Flows.TrainerCx
                    onClose={() => ui.setTrainerCancelledOpen(false)}
                    onReschedule={() => {
                      ui.setTrainerCancelledOpen(false);
                      ui.setBookingConfirmedCtx({
                        date: 'Завтра, Чт', time: '18:00',
                        trainer: 'Аня Соколова', kind: 'Ноги + спина',
                      });
                    }}
                    onChat={() => { ui.setTrainerCancelledOpen(false); handleTab('book'); }}
                  />
                </SheetGate>
                <SheetGate open={!!ui.receiptCtx} variant="detail">
                  <Flows.Receipt
                    ctx={ui.receiptCtx?.ctx}
                    total={ui.receiptCtx?.total}
                    onClose={() => ui.setReceiptCtx(null)}
                  />
                </SheetGate>
                <SheetGate open={!!ui.bookingConfirmedCtx} variant="detail">
                  <Flows.Booking
                    booking={ui.bookingConfirmedCtx}
                    onClose={() => ui.setBookingConfirmedCtx(null)}
                  />
                </SheetGate>

                {/* Chat attachment sheet — small popover, no gate needed */}
                {ui.chatAttachOpen && (
                  <Flows.Attach
                    onClose={() => ui.setChatAttachOpen(false)}
                    onPick={(kind) => { window.__attachPick?.(kind); }}
                  />
                )}
              </Suspense>

              {/* Push notification overlay — always above sheets */}
              {ui.pushKind && (
                <PushToast
                  kind={ui.pushKind}
                  onDismiss={() => { ui.setPushKind(null); setTweak('pushKind', 'idle'); }}
                  onTap={handlePushTap}
                />
              )}
            </div>

            {!hideTabBar && (
              <TabBar
                active={tab}
                onChange={handleTab}
                unreadChat={unreadChat}
              />
            )}
          </div>

          <HomeIndicator />
        </div>
      </div>

      {/* Tweaks panel — host-protocol aware */}
      <TweaksRoot />
    </div>
  );
}
