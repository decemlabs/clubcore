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

const STORAGE_KEY = 'sportzal:ui:v1'

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
      version: 1,
      storage,
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
      skipHydration: true,
    },
  ),
)

export const UI_PREFS_STORAGE_KEY = STORAGE_KEY
