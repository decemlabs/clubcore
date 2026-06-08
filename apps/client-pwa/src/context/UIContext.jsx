import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

// UI overlay state — sheet/modal/push flags previously held inline in App.
// Exposed via `useUI()`. Also bridged to `window.__open*` so deeply-nested
// children (e.g. CheckoutDone → ReceiptSheet) can keep calling the original
// hooks without prop drilling.

const UICtx = createContext(null);

export function UIProvider({ children }) {
  const [qrOpen, setQrOpen] = useState(false);
  const [plansOpen, setPlansOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [manageBooking, setManageBooking] = useState(null);  // booking being managed (real API booking or null)
  const [referralOpen, setReferralOpen] = useState(false);
  const [gymInfoOpen, setGymInfoOpen] = useState(false);
  const [notifsOpen, setNotifsOpen] = useState(false);
  const [trainerDetail, setTrainerDetail] = useState(null);  // TRAINERS item or null
  const [checkoutCtx, setCheckoutCtx] = useState(null);      // { kind, title, subtitle, amount }
  const [personalOpen, setPersonalOpen] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const [faqOpen, setFaqOpen] = useState(false);
  const [visitHistOpen, setVisitHistOpen] = useState(false);
  const [trainHistOpen, setTrainHistOpen] = useState(false);

  const [pushKind, setPushKind] = useState(null);   // 'message' | 'promo' | 'cancel' | null
  const [pendingChat, setPendingChat] = useState(null);
  const [chatThreadOpen, setChatThreadOpen] = useState(false);
  const [unreadChat, setUnreadChat] = useState(0);  // Phase-94 PWA-02: Chat-tab unread badge count
  const [bookConfirmOpen, setBookConfirmOpen] = useState(false);

  // New flows
  const [cancelBookingOpen, setCancelBookingOpen] = useState(false);
  const [subManageMode, setSubManageMode] = useState(null);    // 'freeze' | 'extend' | 'refund' | null
  const [paymentMethodsOpen, setPaymentMethodsOpen] = useState(false);
  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false);
  const [smsVerifyCtx, setSmsVerifyCtx] = useState(null);       // { channel, target } | null
  const [reviewCtx, setReviewCtx] = useState(null);
  const [trainerCancelledOpen, setTrainerCancelledOpen] = useState(false);
  const [receiptCtx, setReceiptCtx] = useState(null);           // { ctx, total } | null
  const [bookingConfirmedCtx, setBookingConfirmedCtx] = useState(null);
  const [chatAttachOpen, setChatAttachOpen] = useState(false);

  // ── Bridge to window globals — keeps existing screen code working without
  // having to prop-drill through deeply-nested CheckoutDone/etc.
  useEffect(() => {
    window.__openReceipt = (ctx, total) => setReceiptCtx({ ctx, total });
    window.__openReview = (training) => setReviewCtx(training || {});
    window.__openCancelBooking = (booking) => setCancelBookingOpen(booking || true);
    window.__openSmsVerify = (channel, target) => setSmsVerifyCtx({ channel, target });
    window.__openChatAttach = () => setChatAttachOpen(true);
    window.__openDeleteAccount = () => setDeleteAccountOpen(true);
    window.__openPaymentMethods = () => setPaymentMethodsOpen(true);
    window.__openSubManage = (mode) => setSubManageMode(mode);
    return () => {
      delete window.__openReceipt;     delete window.__openReview;
      delete window.__openCancelBooking; delete window.__openSmsVerify;
      delete window.__openChatAttach;  delete window.__openDeleteAccount;
      delete window.__openPaymentMethods; delete window.__openSubManage;
    };
  }, []);

  const anySheetOpen = (
    qrOpen || plansOpen || manageOpen || referralOpen ||
    gymInfoOpen || notifsOpen || !!trainerDetail || !!checkoutCtx ||
    personalOpen || cardOpen || faqOpen || visitHistOpen || trainHistOpen ||
    !!cancelBookingOpen || !!subManageMode || paymentMethodsOpen ||
    deleteAccountOpen || !!smsVerifyCtx || !!reviewCtx || trainerCancelledOpen ||
    !!receiptCtx || !!bookingConfirmedCtx
  );

  const value = useMemo(() => ({
    // sheet state
    qrOpen, setQrOpen,
    plansOpen, setPlansOpen,
    manageOpen, setManageOpen,
    manageBooking, setManageBooking,
    referralOpen, setReferralOpen,
    gymInfoOpen, setGymInfoOpen,
    notifsOpen, setNotifsOpen,
    trainerDetail, setTrainerDetail,
    checkoutCtx, setCheckoutCtx,
    personalOpen, setPersonalOpen,
    cardOpen, setCardOpen,
    faqOpen, setFaqOpen,
    visitHistOpen, setVisitHistOpen,
    trainHistOpen, setTrainHistOpen,

    // chat / book flow
    pendingChat, setPendingChat,
    chatThreadOpen, setChatThreadOpen,
    bookConfirmOpen, setBookConfirmOpen,
    // Phase-94 PWA-02: Chat-tab unread badge (set by ChatScreen from unreadCount; capped 99+ in App)
    unreadChat, setUnreadChat,

    // push
    pushKind, setPushKind,

    // flow sheets
    cancelBookingOpen, setCancelBookingOpen,
    subManageMode, setSubManageMode,
    paymentMethodsOpen, setPaymentMethodsOpen,
    deleteAccountOpen, setDeleteAccountOpen,
    smsVerifyCtx, setSmsVerifyCtx,
    reviewCtx, setReviewCtx,
    trainerCancelledOpen, setTrainerCancelledOpen,
    receiptCtx, setReceiptCtx,
    bookingConfirmedCtx, setBookingConfirmedCtx,
    chatAttachOpen, setChatAttachOpen,

    anySheetOpen,
  }), [
    qrOpen, plansOpen, manageOpen, manageBooking, referralOpen, gymInfoOpen, notifsOpen,
    trainerDetail, checkoutCtx, personalOpen, cardOpen, faqOpen,
    visitHistOpen, trainHistOpen, pendingChat, chatThreadOpen, bookConfirmOpen,
    pushKind, cancelBookingOpen, subManageMode, paymentMethodsOpen,
    deleteAccountOpen, smsVerifyCtx, reviewCtx, trainerCancelledOpen,
    receiptCtx, bookingConfirmedCtx, chatAttachOpen, anySheetOpen, unreadChat,
  ]);

  return <UICtx.Provider value={value}>{children}</UICtx.Provider>;
}

export function useUI() {
  const v = useContext(UICtx);
  if (!v) throw new Error('useUI must be used inside <UIProvider>');
  return v;
}
