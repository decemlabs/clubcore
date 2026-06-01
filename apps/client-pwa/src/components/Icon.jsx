// SVG icon set — minimalist 24px line icons.
// Adding a new icon: add a key to `paths` and ship a single React fragment.

export function Icon({ name, size = 22, color = 'currentColor', strokeWidth = 1.8 }) {
  const s = strokeWidth;
  const paths = {
    home: <><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-7h-6v7H4a1 1 0 01-1-1v-9z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3" stroke={color} strokeWidth={s} fill="none"/><path d="M3 10h18M8 3v4M16 3v4" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    chat: <><path d="M4 5a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2h-7l-4 4v-4H6a2 2 0 01-2-2V5z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    user: <><circle cx="12" cy="8" r="4" stroke={color} strokeWidth={s} fill="none"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    users: <><circle cx="9" cy="8" r="3.5" stroke={color} strokeWidth={s} fill="none"/><path d="M2 20c0-3.5 3.5-6 7-6s7 2.5 7 6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/><circle cx="17" cy="6.5" r="3" stroke={color} strokeWidth={s} fill="none"/><path d="M16 14c3 0.3 6 2.4 6 5.5" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    qr: <><rect x="3" y="3" width="7" height="7" rx="1.5" stroke={color} strokeWidth={s} fill="none"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke={color} strokeWidth={s} fill="none"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke={color} strokeWidth={s} fill="none"/><path d="M14 14h3v3M21 14v7M14 21h3M17 17v4" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    bell: <><path d="M6 9a6 6 0 1112 0c0 7 3 7 3 9H3c0-2 3-2 3-9z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/><path d="M10 21a2 2 0 004 0" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    bellOff: <><path d="M6 9a6 6 0 0110-4.4M18 9c0 7 3 7 3 9H8M3 3l18 18" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="M10 21a2 2 0 004 0" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    box: <><path d="M3 7l9-4 9 4M3 7v10l9 4 9-4V7M3 7l9 4 9-4M12 11v10" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round" strokeLinecap="round"/></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 002 2h6a2 2 0 002-2l1-13M10 11v7M14 11v7" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    chevronRight: <><path d="M9 6l6 6-6 6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    chevronLeft: <><path d="M15 6l-6 6 6 6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    chevronDown: <><path d="M6 9l6 6 6-6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    close: <><path d="M6 6l12 12M18 6L6 18" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    check: <><path d="M5 12l5 5L20 6" stroke={color} strokeWidth={s + 0.4} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    plus: <><path d="M12 5v14M5 12h14" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    star: <><path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1L3.2 9.4l6.1-.9L12 3z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    starFill: <><path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1L3.2 9.4l6.1-.9L12 3z" fill={color}/></>,
    send: <><path d="M4 12l16-8-6 17-3-7-7-2z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    copy: <><rect x="9" y="9" width="11" height="11" rx="2" stroke={color} strokeWidth={s} fill="none"/><path d="M5 15V5a2 2 0 012-2h10" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    link: <><path d="M10 14a4 4 0 005.66 0l3-3a4 4 0 00-5.66-5.66L11 7" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/><path d="M14 10a4 4 0 00-5.66 0l-3 3a4 4 0 005.66 5.66L13 17" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    image: <><rect x="3" y="5" width="18" height="14" rx="2" stroke={color} strokeWidth={s} fill="none"/><circle cx="8.5" cy="10" r="1.5" stroke={color} strokeWidth={s} fill="none"/><path d="M21 15l-5-5L5 19" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    paperclip: <><path d="M21 11.5l-9 9a5 5 0 01-7-7l9-9a3.5 3.5 0 015 5l-9 9a2 2 0 01-3-3l8.5-8.5" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    alert: <><path d="M10.3 3.86l-7.66 12a2 2 0 001.71 3h15.3a2 2 0 001.71-3l-7.66-12a2 2 0 00-3.4 0zM12 9v4M12 17h0" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    settings: <><circle cx="12" cy="12" r="3" stroke={color} strokeWidth={s} fill="none"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    logout: <><path d="M16 17l5-5-5-5M21 12H9M12 21H5a2 2 0 01-2-2V5a2 2 0 012-2h7" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    flame: <><path d="M12 3c1 4 5 5 5 10a5 5 0 11-10 0c0-2 1-3 2-4-1 4 4 4 3-1 0-2 0-3 0-5z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    clock: <><circle cx="12" cy="12" r="9" stroke={color} strokeWidth={s} fill="none"/><path d="M12 7v5l3 2" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    card: <><rect x="3" y="6" width="18" height="13" rx="3" stroke={color} strokeWidth={s} fill="none"/><path d="M3 11h18" stroke={color} strokeWidth={s}/></>,
    lock: <><rect x="5" y="11" width="14" height="10" rx="2" stroke={color} strokeWidth={s} fill="none"/><path d="M8 11V7a4 4 0 018 0v4" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    info: <><circle cx="12" cy="12" r="9" stroke={color} strokeWidth={s} fill="none"/><path d="M12 11v6M12 7.5v.5" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    tag: <><path d="M3 12V4a1 1 0 011-1h8l9 9-9 9-9-9z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/><circle cx="8" cy="8" r="1.5" fill={color}/></>,
    sparkle: <><path d="M12 3v18M3 12h18M6 6l12 12M18 6L6 18" stroke={color} strokeWidth={s * 0.7} strokeLinecap="round" opacity="0.8"/></>,
    arrowRight: <><path d="M5 12h14M13 6l6 6-6 6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    history: <><path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.3M3 4v4h4" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="M12 7v5l3 2" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    moon: <><path d="M21 13A9 9 0 1111 3a7 7 0 0010 10z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    phone: <><path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round" strokeLinecap="round"/></>,
    mapPin: <><path d="M12 22s7-7.6 7-13a7 7 0 10-14 0c0 5.4 7 13 7 13z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/><circle cx="12" cy="9" r="2.5" stroke={color} strokeWidth={s} fill="none"/></>,
    navigation: <><path d="M3 11l18-8-8 18-2-8-8-2z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    parking: <><rect x="4" y="4" width="16" height="16" rx="3" stroke={color} strokeWidth={s} fill="none"/><path d="M10 17V8h3.5a2.5 2.5 0 010 5H10" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round" strokeLinecap="round"/></>,
    wifi: <><path d="M5 12.5a10 10 0 0114 0M8 16a6 6 0 018 0M11 19.5a1.5 1.5 0 012 0" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    shower: <><path d="M5 22V11a4 4 0 014-4h0a4 4 0 014 4M13 7V3M11 3h4" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="M3 13h12M6 17v1M9 17v1.5M12 17v1" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    locker: <><rect x="5" y="3" width="14" height="18" rx="2" stroke={color} strokeWidth={s} fill="none"/><path d="M12 3v18M9 9h0M15 9h0M9 13h0M15 13h0" stroke={color} strokeWidth={s + 0.4} strokeLinecap="round"/></>,
    sauna: <><path d="M3 19h18M3 15h18M3 11c2-2 4-2 6 0s4 2 6 0 4-2 6 0M9 7s-1 1 0 2 1-1 0-2zM15 6s-1 1 0 2 1-1 0-2z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    towel: <><rect x="5" y="3" width="14" height="18" rx="2" stroke={color} strokeWidth={s} fill="none"/><path d="M9 7l6 10M15 7L9 17" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    water: <><path d="M12 3s7 8 7 13a7 7 0 11-14 0c0-5 7-13 7-13z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    kids: <><circle cx="9" cy="6" r="2.5" stroke={color} strokeWidth={s} fill="none"/><circle cx="17" cy="9" r="2" stroke={color} strokeWidth={s} fill="none"/><path d="M3 22c0-3 3-5 6-5s6 2 6 5M14 22c0-2 2-4 4-4s4 2 4 4" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    instagram: <><rect x="3" y="3" width="18" height="18" rx="5" stroke={color} strokeWidth={s} fill="none"/><circle cx="12" cy="12" r="4" stroke={color} strokeWidth={s} fill="none"/><circle cx="17" cy="7" r="0.8" fill={color}/></>,
    telegram: <><path d="M3 11l18-7-3 17-7-5-3 4v-5l11-9-13 8-3-3z" stroke={color} strokeWidth={s} fill="none" strokeLinejoin="round"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" stroke={color} strokeWidth={s} fill="none"/><path d="M3 8l9 6 9-6" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    wifiOff: <><path d="M1 1l22 22M16.7 16.7A10 10 0 005.3 5.3M10.7 10.7A6 6 0 0113 12.6M10.8 16.8A3 3 0 0115 17" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/><circle cx="12" cy="20" r="1" fill={color}/></>,
    alertCircle: <><circle cx="12" cy="12" r="9" stroke={color} strokeWidth={s} fill="none"/><path d="M12 8v4M12 16h0" stroke={color} strokeWidth={s + 0.4} strokeLinecap="round"/></>,
    x: <><path d="M6 6l12 12M18 6L6 18" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/></>,
    // Phase 999.5 onboarding icons
    flag: <><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><line x1="4" x2="4" y1="22" y2="15" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    idCard: <><rect x="2" y="5" width="20" height="14" rx="2.5" stroke={color} strokeWidth={s} fill="none"/><circle cx="9" cy="11" r="2" stroke={color} strokeWidth={s} fill="none"/><path d="M6.2 15.2a3 3 0 0 1 5.6 0" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round"/><path d="M15.5 10.5h3M15.5 14h3" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    ruler: <><path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="m14.5 12.5 2-2M11.5 9.5l2-2M8.5 6.5l2-2M17.5 15.5l2-2" stroke={color} strokeWidth={s} strokeLinecap="round"/></>,
    barbell: <><path d="M4 9v6M7 7v10M17 7v10M20 9v6M7 12h10" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    lightning: <><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    heart: <><path d="M20.8 5.6a5 5 0 0 0-8.8-1.6A5 5 0 0 0 3.2 5.6c-1.6 2.5-.8 5.5 3 8.7L12 19l5.8-4.7c3.8-3.2 4.6-6.2 3-8.7z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    // Phase 999.5-05: receipt-email gate icon
    shield: <><path d="M12 3l8 3v5c0 5-4 8.5-8 10C8 19.5 4 16 4 11V6l8-3z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
    // Plan 260601-oan: ticket icon for first-visit promo illustration
    ticket: <><path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z" stroke={color} strokeWidth={s} fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="M14 6v12" stroke={color} strokeWidth={s} strokeLinecap="round" strokeDasharray="2.5 2.5"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
         style={{ display: 'block', flexShrink: 0 }}
         aria-hidden="true" focusable="false">
      {paths[name]}
    </svg>
  );
}
