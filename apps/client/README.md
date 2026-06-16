# Мой зал — Gym Client PWA

Production-ready Vite + React rebuild of the original single-file HTML prototype.

## Stack

- React 18.3 + JSX (no Babel-in-browser)
- Vite 5 (esbuild + Rollup)
- React Router v6
- Bun-first, npm-compatible

## Run

```bash
# Bun (preferred)
bun install
bun run dev

# npm
npm install
npm run dev
```

Production build:

```bash
bun run build
bun run preview
```

## Structure

```
src/
├── main.jsx              # entry: createRoot + providers + router
├── App.jsx               # routed device shell + sheet/push overlays
├── styles.css            # design tokens + global styles
├── data/                 # mock data (trainers, conversations, plans …)
├── hooks/                # useCountdown, useLongPress, useRipple
├── utils/                # format, subInfo, accent
├── services/             # pwa.js (SW registration + install prompt)
├── context/              # TweaksContext, UIContext
├── components/           # atoms (Icon, Avatar, TabBar, Skeletons, Tweaks …)
└── screens/              # routed tab screens
    └── sheets/           # lazy-loaded modal sheets + flows
```

Each tab screen and every sheet is a real ES module loaded via `React.lazy`,
so the initial bundle stays small and overlays load on demand.

## Routes

| Path        | Screen          |
| ----------- | --------------- |
| `/`         | redirects → `/home` |
| `/home`     | Home            |
| `/book`     | Book            |
| `/chat`     | Chat list/thread |
| `/profile`  | Profile          |

Sheets and push toasts are overlays driven by `UIContext` and rendered above
the routed content — same z-index stack as the original prototype.

## PWA

`public/manifest.json`, `public/sw.js`, icons and `offline.html` are served from
the build root. SW registration + `beforeinstallprompt` capture live in
`src/services/pwa.js`.
