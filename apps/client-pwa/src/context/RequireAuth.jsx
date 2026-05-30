/**
 * RequireAuth (Plan 71-07).
 *
 * Auth guard for react-router v6 protected routes.
 *
 * - status 'unknown' → show spinner while /client/me probe is pending
 * - status 'anon'    → <Navigate to="/login" replace /> (no window.location, no loop)
 * - status 'authed'  → render children
 *
 * Usage in App.jsx:
 *   <Route path="/home" element={<RequireAuth><HomeRoute /></RequireAuth>} />
 *
 * JSX file — allowJs ramp.
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { HomeSkeleton } from '@/components/skeletons.jsx'

export function RequireAuth({ children }) {
  const { status } = useAuth()

  if (status === 'unknown') {
    return <HomeSkeleton />
  }

  if (status === 'anon') {
    return <Navigate to="/login" replace />
  }

  // status === 'authed'
  return children
}

export default RequireAuth
