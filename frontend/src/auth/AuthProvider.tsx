import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getJson, getToken, onUnauthorized, sendJson, setToken } from '../api/client'
import type { GlobalPermission, LoginResponse, User } from '../api/types'
import { AuthContext, type AuthState } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthState['status']>(() => (getToken() ? 'loading' : 'anonymous'))
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    if (!getToken()) return
    const controller = new AbortController()
    getJson<User>('/api/auth/me', controller.signal)
      .then((current) => {
        setUser(current)
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setToken('')
        setStatus('anonymous')
      })
    return () => controller.abort()
  }, [])

  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null)
        setStatus('anonymous')
        setExpired(true)
        queryClient.clear()
      }),
    [queryClient],
  )

  const login = useCallback(async (email: string, password: string) => {
    const response = await sendJson<LoginResponse>('/api/auth/login', 'POST', { email, password })
    setToken(response.token)
    setUser(response.user)
    setExpired(false)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    await sendJson('/api/auth/logout', 'POST').catch(() => undefined)
    setToken('')
    setUser(null)
    setStatus('anonymous')
    queryClient.clear()
  }, [queryClient])

  const can = useCallback((permission: GlobalPermission) => Boolean(user?.permissions.includes(permission)), [user])

  const value = useMemo<AuthState>(() => ({ user, status, expired, login, logout, can }), [user, status, expired, login, logout, can])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
