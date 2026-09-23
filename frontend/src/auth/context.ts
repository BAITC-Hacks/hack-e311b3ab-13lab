import { createContext, useContext } from 'react'
import type { GlobalPermission, User } from '../api/types'

export interface AuthState {
  user: User | null
  status: 'loading' | 'anonymous' | 'authenticated'
  expired: boolean
  login: (email: string, password: string) => Promise<User>
  acceptSession: (token: string, user: User) => void
  logout: () => Promise<void>
  can: (permission: GlobalPermission) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
