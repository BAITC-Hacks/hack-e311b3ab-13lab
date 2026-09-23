import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import type { GlobalPermission } from '../api/types'
import { Spinner } from '../components/ui'
import { useAuth } from './context'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Spinner label="Проверяем сессию…" />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}

export function RequirePermission({ permission, children }: { permission: GlobalPermission; children: ReactNode }) {
  const { can } = useAuth()
  return can(permission) ? children : <Navigate to="/" replace />
}
