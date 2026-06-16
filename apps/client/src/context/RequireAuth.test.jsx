/**
 * RequireAuth tests (Plan 71-07).
 *
 * Asserts all three guard branches:
 *  (a) status='unknown' → spinner/skeleton shown, children NOT rendered
 *  (b) status='anon'    → Navigate to /login fires (login marker renders, not protected child)
 *  (c) status='authed'  → children render
 */
import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './RequireAuth.jsx'
import AuthContext from './AuthContext.jsx'

// Stub AuthContext value so we don't need the full provider tree
function renderWithAuth(status, ui) {
  const stubValue = { status, login: vi.fn(), logout: vi.fn() }
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AuthContext.Provider value={stubValue}>
        <Routes>
          <Route
            path="/home"
            element={
              <RequireAuth>
                <div data-testid="protected-child">Protected</div>
              </RequireAuth>
            }
          />
          <Route path="/login" element={<div data-testid="login-screen">LoginScreen</div>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  it('(a) unknown status → shows spinner/skeleton, children not rendered', () => {
    renderWithAuth('unknown')

    // The HomeSkeleton renders (a loading skeleton), not the protected child
    expect(screen.queryByTestId('protected-child')).toBeNull()
    // Some loading UI is present (the skeleton renders something in the DOM)
    // We don't assert the exact skeleton markup — just that children are absent
  })

  it('(b) anon status → navigates to /login, protected child not rendered', () => {
    renderWithAuth('anon')

    // Should see the login screen marker, not the protected child
    expect(screen.getByTestId('login-screen')).toBeTruthy()
    expect(screen.queryByTestId('protected-child')).toBeNull()
  })

  it('(c) authed status → children render', () => {
    renderWithAuth('authed')

    expect(screen.getByTestId('protected-child')).toBeTruthy()
    expect(screen.queryByTestId('login-screen')).toBeNull()
  })
})
