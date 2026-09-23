import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { useRegistrationMode } from '../api/queries'
import { useAuth } from '../auth/context'
import { AuthLayout } from '../components/AuthLayout'
import { Button, Field, Input, Notice } from '../components/ui'

export function LoginPage() {
  const { user, status, expired, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const registration = useRegistrationMode()

  const target = (role?: string) => (from === '/' && role === 'admin' ? '/admin' : from)

  if (status === 'authenticated') return <Navigate to={target(user?.role)} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      const current = await login(email, password)
      navigate(target(current.role), { replace: true })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Не удалось войти')
      setPassword('')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthLayout>
        <form onSubmit={submit} className="space-y-5" aria-label="Вход">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Вход в рабочее пространство</h2>
            <p className="mt-1 text-sm text-ink-muted">Войдите учётной записью, выданной администратором, или зарегистрируйтесь.</p>
          </div>
          {expired && <Notice tone="info">Сессия завершена. Войдите снова.</Notice>}
          <Field label="Email">
            <Input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} autoFocus />
          </Field>
          <Field label="Пароль">
            <Input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" variant="primary" className="w-full" loading={pending}>
            Войти
          </Button>
          {registration.data && registration.data !== 'closed' && (
            <p className="text-center text-sm text-ink-muted">
              Нет учётной записи?{' '}
              <Link to="/register" className="font-semibold text-forest-800 underline">
                Зарегистрироваться
              </Link>
            </p>
          )}
        </form>
    </AuthLayout>
  )
}
