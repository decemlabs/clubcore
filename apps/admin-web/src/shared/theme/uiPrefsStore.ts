import { create } from 'zustand'
import { persist, createJSONStorage, type PersistStorage } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'system'

export interface UiPrefsState {
  theme: Theme
  sidebarCollapsed: boolean
  setTheme: (theme: Theme) => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

type PersistedUi = Pick<UiPrefsState, 'theme' | 'sidebarCollapsed'>

const STORAGE_KEY = 'clubcore:ui:v2'

const storage: PersistStorage<PersistedUi> | undefined = createJSONStorage<PersistedUi>(
  () => window.localStorage,
)

export const useUiPrefsStore = create<UiPrefsState>()(
  persist(
    (set) => ({
      theme: 'system',
      sidebarCollapsed: false,
      setTheme: (theme) => set({ theme }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
    }),
    {
      name: STORAGE_KEY,
      version: 2,
      storage,
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
      // Pass-through: persisted shape is identical v1→v2 (Phase 62 D-62-06).
      // Zustand requires `migrate` whenever `version` increments above stored
      // version; without this callback rehydrate would throw on v1 payloads.
      // The legacy-key → STORAGE_KEY copy runs as a pre-rehydrate side
      // effect in `src/app/main.tsx` (see STORE_MIGRATIONS).
      migrate: (state) => state as PersistedUi,
      skipHydration: true,
    },
  ),
)

export const UI_PREFS_STORAGE_KEY = STORAGE_KEY
