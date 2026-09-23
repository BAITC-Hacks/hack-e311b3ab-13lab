import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { ArrowRight, Check, CircleAlert, CircleCheck, ScrollText, UserCheck, Users, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { sendJson } from '../api/client'
import { queryKeys, useAdminOverview } from '../api/queries'
import type { AdminOverview, MeetingStatus, Role, User } from '../api/types'
import { ConfirmDialog } from '../components/Dialog'
import { useToast } from '../components/toast-context'
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Select, Spinner } from '../components/ui'
import { formatDateTime } from '../lib/format'
import { AUDIT_LABELS, ROLE_DESCRIPTIONS, ROLE_LABELS, STATUS_LABELS } from '../lib/labels'

const ROLES = Object.keys(ROLE_LABELS) as Role[]
const REGISTRATION_LABELS = { approval: 'С подтверждением администратором', open: 'Открытая, роль «Участник»', closed: 'Отключена' }

export function AdminPage() {
  const overview = useAdminOverview()

  return (
    <>
      <PageHeader
        eyebrow="Администрирование"
        title="Админ-панель"
        actions={
          <>
            <Link to="/users" className="inline-flex items-center gap-2 rounded-lg border border-sand-200 bg-white px-4 py-2.5 text-sm hover:bg-sand-100">
              <Users className="size-4" /> Пользователи
            </Link>
            <Link to="/audit" className="inline-flex items-center gap-2 rounded-lg border border-sand-200 bg-white px-4 py-2.5 text-sm hover:bg-sand-100">
              <ScrollText className="size-4" /> Журнал
            </Link>
          </>
        }
      >
        Заявки на регистрацию, состояние системы и последние действия.
      </PageHeader>
      {overview.isPending && <Spinner />}
      {overview.isError && <Notice tone="error">{overview.error.message}</Notice>}
      {overview.data && <Dashboard data={overview.data} />}
    </>
  )
}

function Dashboard({ data }: { data: AdminOverview }) {
  const stats = [
    { label: 'Активных пользователей', value: data.users.active },
    { label: 'Ожидают подтверждения', value: data.users.pending, highlight: data.users.pending > 0 },
    { label: 'Отключено', value: data.users.disabled },
    { label: 'Совещаний', value: data.meetings.total },
  ]
  return (
    <div className="space-y-8">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className={clsx('p-5', stat.highlight && 'border-amber-300 bg-amber-50')}>
            <dt className="text-xs text-ink-muted">{stat.label}</dt>
            <dd className="mt-1 text-3xl font-bold">{stat.value}</dd>
          </Card>
        ))}
      </dl>

      <PendingRegistrations users={data.pending_registrations} mode={data.system.registration_mode} />

      <div className="grid gap-6 lg:grid-cols-3">
        <SystemCard system={data.system} />
        <Card className="p-5">
          <h2 className="font-semibold">Пользователи по ролям</h2>
          <ul className="mt-4 space-y-3">
            {ROLES.map((role) => (
              <li key={role}>
                <div className="flex justify-between text-sm">
                  <span>{ROLE_LABELS[role]}</span>
                  <span className="font-semibold">{data.users.by_role[role] ?? 0}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-sand-100">
                  <div className="h-1.5 rounded-full bg-forest-700" style={{ width: `${data.users.active ? ((data.users.by_role[role] ?? 0) / data.users.active) * 100 : 0}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <h2 className="font-semibold">Совещания по статусам</h2>
          {data.meetings.total === 0 ? (
            <p className="mt-4 text-sm text-ink-muted">Совещаний пока нет.</p>
          ) : (
            <ul className="mt-4 space-y-2 text-sm">
              {(Object.entries(data.meetings.by_status) as Array<[MeetingStatus, number]>).map(([status, count]) => (
                <li key={status} className="flex justify-between">
                  <span>{STATUS_LABELS[status] ?? status}</span>
                  <span className="font-semibold">{count}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs text-ink-soft">Содержание протоколов администратору недоступно.</p>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Последние действия</h2>
          <Link to="/audit" className="inline-flex items-center gap-1 text-sm text-forest-800 hover:underline">
            Весь журнал <ArrowRight className="size-4" />
          </Link>
        </div>
        <ul className="mt-3 divide-y divide-sand-200">
          {data.recent_activity.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 text-sm">
              <span className="w-40 shrink-0 text-xs text-ink-muted">{formatDateTime(entry.at)}</span>
              <span className="font-medium">{AUDIT_LABELS[entry.action] ?? entry.action}</span>
              <span className="text-ink-muted">{entry.user_email ?? '—'}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

function SystemCard({ system }: { system: AdminOverview['system'] }) {
  const checks: Array<{ label: string; value: string; ok: boolean }> = [
    { label: 'База данных', value: system.database === 'postgresql' ? 'PostgreSQL' : 'SQLite', ok: true },
    { label: 'Хранилище', value: system.storage === 'minio' ? 'MinIO' : 'Локальные файлы', ok: true },
    { label: 'Сервис моделей', value: system.provider_configured ? 'Ключ задан' : 'Ключ не задан', ok: system.provider_configured },
    { label: 'PDF', value: system.pdf_configured ? 'Шрифт найден' : 'Нет шрифта', ok: system.pdf_configured },
    { label: 'Диаризация', value: system.diarization_configured ? 'Настроена' : 'Не настроена', ok: system.diarization_configured },
  ]
  return (
    <Card className="p-5">
      <h2 className="font-semibold">Состояние системы</h2>
      <ul className="mt-4 space-y-2.5 text-sm">
        {checks.map((check) => (
          <li key={check.label} className="flex items-center gap-2">
            {check.ok ? <CircleCheck className="size-4 text-lime-700" aria-hidden /> : <CircleAlert className="size-4 text-amber-600" aria-hidden />}
            <span className="flex-1">{check.label}</span>
            <span className="text-ink-muted">{check.value}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-ink-muted">Регистрация: {REGISTRATION_LABELS[system.registration_mode]}</p>
      <p className="mt-2 text-xs text-ink-muted">
        Миграции: {system.migrations.length}, последняя <code className="rounded bg-sand-100 px-1">{system.migrations.at(-1)?.id ?? '—'}</code>
      </p>
    </Card>
  )
}

function PendingRegistrations({ users, mode }: { users: User[]; mode: AdminOverview['system']['registration_mode'] }) {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [roles, setRoles] = useState<Record<string, Role>>({})
  const [rejecting, setRejecting] = useState<User | null>(null)

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminOverview })
    void queryClient.invalidateQueries({ queryKey: queryKeys.users })
    void queryClient.invalidateQueries({ queryKey: queryKeys.directory })
  }

  const approve = useMutation({
    mutationFn: ({ user, role }: { user: User; role: Role }) => sendJson<User>(`/api/admin/registrations/${user.id}/approve`, 'POST', { role }),
    onSuccess: (user) => {
      refresh()
      notify(`${user.name} получил доступ: ${ROLE_LABELS[user.role]}`)
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const reject = useMutation({
    mutationFn: (user: User) => sendJson(`/api/admin/registrations/${user.id}`, 'DELETE'),
    onSuccess: () => {
      refresh()
      setRejecting(null)
      notify('Заявка отклонена')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  return (
    <section aria-label="Заявки на регистрацию">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
        <UserCheck className="size-5" aria-hidden /> Заявки на регистрацию {users.length > 0 && <Badge tone="review">{users.length}</Badge>}
      </h2>
      {users.length === 0 ? (
        <EmptyState title="Новых заявок нет">{mode === 'approval' ? 'Новые пользователи появятся здесь после регистрации.' : `Регистрация сейчас: ${REGISTRATION_LABELS[mode].toLowerCase()}.`}</EmptyState>
      ) : (
        <Card className="divide-y divide-sand-200">
          {users.map((user) => {
            const role = roles[user.id] ?? 'participant'
            return (
              <div key={user.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{user.name}</p>
                  <p className="text-xs text-ink-muted">
                    {user.email} · заявка от {formatDateTime(user.created_at)}
                  </p>
                </div>
                <div className="w-full sm:w-52">
                  <Select aria-label={`Роль для ${user.name}`} className="mt-0 py-1.5" value={role} title={ROLE_DESCRIPTIONS[role]} onChange={(event) => setRoles({ ...roles, [user.id]: event.target.value as Role })}>
                    {ROLES.map((item) => (
                      <option key={item} value={item}>
                        {ROLE_LABELS[item]}
                      </option>
                    ))}
                  </Select>
                </div>
                <Button size="sm" variant="primary" icon={<Check className="size-3.5" />} loading={approve.isPending && approve.variables?.user.id === user.id} onClick={() => approve.mutate({ user, role })}>
                  Одобрить
                </Button>
                <Button size="sm" variant="danger" icon={<X className="size-3.5" />} onClick={() => setRejecting(user)}>
                  Отклонить
                </Button>
              </div>
            )
          })}
        </Card>
      )}
      <ConfirmDialog open={Boolean(rejecting)} danger title="Отклонить заявку?" confirmLabel="Отклонить" loading={reject.isPending} onConfirm={() => rejecting && reject.mutate(rejecting)} onClose={() => setRejecting(null)}>
        Заявка {rejecting?.email} будет удалена. Пользователь сможет зарегистрироваться снова.
      </ConfirmDialog>
    </section>
  )
}
