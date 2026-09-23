import { useMutation, useQueryClient } from '@tanstack/react-query'
import { KeyRound, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { sendJson } from '../api/client'
import { queryKeys, useUsers } from '../api/queries'
import type { Role, User } from '../api/types'
import { useAuth } from '../auth/context'
import { Dialog } from '../components/Dialog'
import { useToast } from '../components/toast-context'
import { Badge, Button, Card, Field, Input, Notice, PageHeader, Select, Spinner } from '../components/ui'
import { formatDate, formatDateTime } from '../lib/format'
import { ROLE_DESCRIPTIONS, ROLE_LABELS } from '../lib/labels'

const ROLES = Object.keys(ROLE_LABELS) as Role[]

export function UsersPage() {
  const users = useUsers()
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [resetting, setResetting] = useState<User | null>(null)

  const update = useMutation({
    mutationFn: ({ id, ...changes }: { id: string; role?: Role; active?: boolean; password?: string }) => sendJson<User>(`/api/users/${id}`, 'PATCH', changes),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users })
      void queryClient.invalidateQueries({ queryKey: queryKeys.directory })
      notify('Пользователь обновлён')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  return (
    <>
      <PageHeader eyebrow="Администрирование" title="Пользователи">
        Роль определяет доступ. Отключение пользователя сразу завершает его сессии.
      </PageHeader>
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0">
          {users.isPending && <Spinner />}
          {users.isError && <Notice tone="error">{users.error.message}</Notice>}
          {users.data && (
            <Card className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="border-b border-sand-200 text-xs text-ink-muted">
                  <tr>
                    <th className="px-5 py-3 font-medium">Пользователь</th>
                    <th className="px-5 py-3 font-medium">Роль</th>
                    <th className="px-5 py-3 font-medium">Статус</th>
                    <th className="px-5 py-3 font-medium">
                      <span className="sr-only">Действия</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand-200">
                  {users.data.map((user) => (
                    <tr key={user.id} className={user.active ? '' : 'text-ink-soft'}>
                      <td className="px-5 py-3">
                        <p className="font-semibold">
                          {user.name} {user.id === me?.id && <Badge>вы</Badge>} {user.pending && <Badge tone="review">Ожидает подтверждения</Badge>}
                        </p>
                        <p className="text-xs text-ink-muted">
                          {user.email} · с {formatDate(user.created_at)} · {user.last_login_at ? `вход ${formatDateTime(user.last_login_at)}` : 'ещё не входил'}
                        </p>
                      </td>
                      <td className="px-5 py-3">
                        <Select aria-label={`Роль ${user.name}`} className="mt-0 w-48 py-1.5" value={user.role} disabled={update.isPending} onChange={(event) => update.mutate({ id: user.id, role: event.target.value as Role })}>
                          {ROLES.map((role) => (
                            <option key={role} value={role}>
                              {ROLE_LABELS[role]}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="px-5 py-3">
                        <label className="flex items-center gap-2">
                          <input type="checkbox" className="size-4 accent-forest-700" checked={user.active} disabled={update.isPending} onChange={(event) => update.mutate({ id: user.id, active: event.target.checked })} />
                          {user.active ? 'Активен' : user.pending ? 'Заявка' : 'Отключён'}
                        </label>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Button size="sm" variant="ghost" icon={<KeyRound className="size-3.5" />} onClick={() => setResetting(user)}>
                          Пароль
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
          <Card className="mt-6 p-5">
            <h2 className="font-semibold">Роли</h2>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
              {ROLES.map((role) => (
                <div key={role}>
                  <dt className="font-medium">{ROLE_LABELS[role]}</dt>
                  <dd className="text-ink-muted">{ROLE_DESCRIPTIONS[role]}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
        <CreateUserForm />
      </div>
      <ResetPasswordDialog
        user={resetting}
        pending={update.isPending}
        onClose={() => setResetting(null)}
        onSubmit={(password) => resetting && update.mutate({ id: resetting.id, password }, { onSuccess: () => setResetting(null) })}
      />
    </>
  )
}

function CreateUserForm() {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [form, setForm] = useState({ name: '', email: '', role: 'participant' as Role, password: '' })

  const create = useMutation({
    mutationFn: () => sendJson<User>('/api/users', 'POST', form),
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users })
      void queryClient.invalidateQueries({ queryKey: queryKeys.directory })
      notify(`Создан пользователь ${user.email}`)
      setForm({ name: '', email: '', role: 'participant', password: '' })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate()
  }

  return (
    <Card className="h-fit p-5">
      <h2 className="flex items-center gap-2 font-semibold">
        <UserPlus className="size-4" aria-hidden /> Новый пользователь
      </h2>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <Field label="Имя">
          <Input required maxLength={200} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </Field>
        <Field label="Email">
          <Input type="email" required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        </Field>
        <Field label="Роль" hint={ROLE_DESCRIPTIONS[form.role]}>
          <Select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as Role })}>
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Временный пароль" hint="Не короче 10 символов; передайте его лично">
          <Input type="password" autoComplete="new-password" required minLength={10} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        </Field>
        {create.isError && <Notice tone="error">{create.error.message}</Notice>}
        <Button type="submit" variant="primary" className="w-full" loading={create.isPending}>
          Создать
        </Button>
      </form>
    </Card>
  )
}

function ResetPasswordDialog({ user, pending, onClose, onSubmit }: { user: User | null; pending: boolean; onClose: () => void; onSubmit: (password: string) => void }) {
  const [password, setPassword] = useState('')
  function close() {
    setPassword('')
    onClose()
  }
  return (
    <Dialog open={Boolean(user)} onClose={close} title={`Новый пароль: ${user?.name ?? ''}`}>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(password)
          setPassword('')
        }}
        className="space-y-4"
      >
        <Field label="Новый пароль" hint="Все сессии пользователя будут завершены">
          <Input type="password" autoComplete="new-password" required minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button onClick={close}>Отмена</Button>
          <Button type="submit" variant="primary" loading={pending}>
            Сменить пароль
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
