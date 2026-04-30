import { create } from 'zustand'
import { persist, type PersistStorage, createJSONStorage } from 'zustand/middleware'
import type { Role, SessionState } from './types'

const STORAGE_KEY = 'sportzal:session:v1'

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
      version: 1,
      storage,
      partialize: (s) => ({ role: s.role }),
      migrate: (state) => state as PersistedSession,
      skipHydration: true,
    },
  ),
)

export const SESSION_STORAGE_KEY = STORAGE_KEY
