import type { ReactNode } from 'react'
import { useCurrentRole } from './useCurrentRole'
import { can, type Action, type Resource } from './can'

export type { Action, Resource } from './can'

interface RoleGateProps {
  action: Action
  resource: Resource
  fallback?: ReactNode
  children: ReactNode
}

export function RoleGate({ action, resource, fallback = null, children }: RoleGateProps) {
  const role = useCurrentRole()
  return <>{can(role, action, resource) ? children : fallback}</>
}
