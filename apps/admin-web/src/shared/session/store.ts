import { create } from 'zustand'
import { persist, type PersistStorage, createJSONStorage } from 'zustand/middleware'
import type { Role, SessionState } from './types'

const STORAGE_KEY = 'clubcore:session:v2'

type PersistedSession = Pick<SessionState, 'role'>

const storage: PersistStorage<PersistedSession> | undefined = createJSONStorage<PersistedSession>(
  () => window.localStorage,
)

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      role: 'owner' as Role,
      setRole: (role) => set({ role }),
    }),
    {
      name: STORAGE_KEY,
      version: 2,
      storage,
      partialize: (s) => ({ role: s.role }),
      // Pass-through: persisted shape is identical v1→v2 (Phase 62 D-62-06).
      // The legacy-key → STORAGE_KEY copy runs as a pre-rehydrate side
      // effect in `src/app/main.tsx` (see STORE_MIGRATIONS).
      migrate: (state) => state as PersistedSession,
      skipHydration: true,
    },
  ),
)

export const SESSION_STORAGE_KEY = STORAGE_KEY
