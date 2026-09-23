import { useMutation } from '@tanstack/react-query'
import { Clock3 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { sendJson } from '../api/client'
import { useRegistrationMode } from '../api/queries'
import type { RegistrationResponse } from '../api/types'
import { useAuth } from '../auth/context'
import { AuthLayout } from '../components/AuthLayout'
import { Button, Field, Input, Notice, Spinner } from '../components/ui'

export function RegisterPage() {
  const { status, acceptSession } = useAuth()
  const navigate = useNavigate()
  const mode = useRegistrationMode()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [mismatch, setMismatch] = useState(false)

  const register = useMutation({
    mutationFn: () => sendJson<RegistrationResponse>('/api/auth/register', 'POST', { name: form.name, email: form.email, password: form.password }),
    onSuccess: (response) => {
      if (response.status === 'active') {
        acceptSession(response.token, response.user)
        navigate('/', { replace: true })
      }
    },
  })

  if (status === 'authenticated') return <Navigate to="/" replace />

  function submit(event: FormEvent) {
    event.preventDefault()
    setMismatch(form.password !== form.confirm)
    if (form.password === form.confirm) register.mutate()
  }

  const backToLogin = (
    <p className="text-center text-sm text-ink-muted">
      Уже есть учётная запись?{' '}
      <Link to="/login" className="font-semibold text-forest-800 underline">
        Войти
      </Link>
    </p>
  )

  if (mode.isPending) return <AuthLayout><Spinner /></AuthLayout>

  if (mode.data === 'closed') {
    return (
      <AuthLayout>
        <h2 className="text-2xl font-bold tracking-tight">Регистрация закрыта</h2>
        <Notice tone="info">Учётные записи создаёт администратор. Обратитесь к нему, чтобы получить доступ.</Notice>
        {backToLogin}
      </AuthLayout>
    )
  }

  if (register.data?.status === 'pending') {
    return (
      <AuthLayout>
        <Clock3 className="size-10 text-forest-700" aria-hidden />
        <h2 className="text-2xl font-bold tracking-tight">Заявка отправлена</h2>
        <p className="text-sm leading-relaxed text-ink-muted" role="status">
          Администратор проверит заявку и назначит роль. После подтверждения войдите с email <strong className="text-ink">{form.email}</strong> и выбранным паролем.
        </p>
        {backToLogin}
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <form onSubmit={submit} className="space-y-5" aria-label="Регистрация">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Регистрация</h2>
          <p className="mt-1 text-sm text-ink-muted">
            {mode.data === 'approval' ? 'Доступ откроется после подтверждения администратором.' : 'Новая учётная запись получает роль участника; расширенные права выдаёт администратор.'}
          </p>
        </div>
        <Field label="Имя и фамилия">
          <Input required maxLength={200} autoComplete="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} autoFocus />
        </Field>
        <Field label="Email">
          <Input type="email" required autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        </Field>
        <Field label="Пароль" hint="Не короче 10 символов">
          <Input type="password" required minLength={10} autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        </Field>
        <Field label="Повторите пароль">
          <Input type="password" required minLength={10} autoComplete="new-password" value={form.confirm} onChange={(event) => setForm({ ...form, confirm: event.target.value })} />
        </Field>
        {mismatch && <Notice tone="error">Пароли не совпадают</Notice>}
        {register.isError && <Notice tone="error">{register.error.message}</Notice>}
        <Button type="submit" variant="primary" className="w-full" loading={register.isPending}>
          Зарегистрироваться
        </Button>
        {backToLogin}
      </form>
    </AuthLayout>
  )
}
