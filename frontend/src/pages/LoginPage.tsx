import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/context'
import { Brand } from '../components/Layout'
import { Button, Field, Input, Notice } from '../components/ui'

export function LoginPage() {
  const { status, expired, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (status === 'authenticated') return <Navigate to={from} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Не удалось войти')
      setPassword('')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="hidden flex-col justify-between bg-forest-900 p-12 text-forest-100 lg:flex">
        <Brand className="text-white" />
        <div>
          <p className="text-[11px] font-bold tracking-[0.2em] text-lime-300">МЕНЬШЕ РУТИНЫ. БОЛЬШЕ ЯСНОСТИ.</p>
          <h1 className="mt-5 text-5xl leading-tight font-bold tracking-tight text-white">
            Каждое решение.
            <br />
            <span className="text-lime-300">Под контролем.</span>
          </h1>
          <p className="mt-6 max-w-md leading-relaxed text-forest-200">Запись совещания превращается в протокол и поручения, которые можно проверить по исходной речи.</p>
        </div>
        <p className="text-xs text-forest-200">RU / KZ / MIX · HackAlem AI · 13Lab</p>
      </section>
      <section className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" aria-label="Вход">
          <div className="lg:hidden">
            <Brand className="text-forest-900" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Вход в рабочее пространство</h2>
            <p className="mt-1 text-sm text-ink-muted">Учётные записи создаёт администратор.</p>
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
        </form>
      </section>
    </div>
  )
}
