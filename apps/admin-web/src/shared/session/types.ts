export type Role = 'owner' | 'reception'

export interface SessionState {
  role: Role
  setRole: (role: Role) => void
}
