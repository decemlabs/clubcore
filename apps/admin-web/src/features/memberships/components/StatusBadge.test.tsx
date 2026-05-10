import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders Активен for active', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByText('Активен')).toBeInTheDocument()
  })

  it('renders Истёк for expired', () => {
    render(<StatusBadge status="expired" />)
    expect(screen.getByText('Истёк')).toBeInTheDocument()
  })

  it('renders Отменён for cancelled', () => {
    render(<StatusBadge status="cancelled" />)
    expect(screen.getByText('Отменён')).toBeInTheDocument()
  })

  it('renders Заморожен for frozen with warning semantic className', () => {
    const { container } = render(<StatusBadge status="frozen" />)
    expect(screen.getByText('Заморожен')).toBeInTheDocument()
    const badge = container.querySelector('[class*="bg-warning"]')
    expect(badge).not.toBeNull()
  })
})
