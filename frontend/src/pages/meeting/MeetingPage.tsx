import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { ArrowLeft, Check, Lock, RefreshCw, ScrollText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, sendJson } from '../../api/client'
import { queryKeys, useMeeting } from '../../api/queries'
import type { Meeting } from '../../api/types'
import { useAuth } from '../../auth/context'
import { ConfirmDialog } from '../../components/Dialog'
import { useToast } from '../../components/toast-context'
import { Button, Card, EmptyState, Notice, Spinner, StatusBadge } from '../../components/ui'
import { formatDate } from '../../lib/format'
import { ACTIVE_STATUSES, PROCESSING_STEPS, STATUS_LABELS } from '../../lib/labels'
import { MeetingWorkspace } from './MeetingWorkspace'

export function MeetingPage() {
  const { id = '' } = useParams()
  const meeting = useMeeting(id)

  if (meeting.isPending) return <Spinner />
  if (meeting.isError) {
    const missing = meeting.error instanceof ApiError && meeting.error.status === 404
    return (
      <EmptyState title={missing ? 'Совещание не найдено' : 'Не удалось загрузить совещание'} action={<BackLink />}>
        {missing ? 'Возможно, оно удалено или у вас нет к нему доступа.' : meeting.error.message}
      </EmptyState>
    )
  }
  return <MeetingView meeting={meeting.data} />
}

function BackLink() {
  return (
    <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink">
      <ArrowLeft className="size-4" /> Все совещания
    </Link>
  )
}

function MeetingView({ meeting }: { meeting: Meeting }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { can: canGlobal } = useAuth()
  const { notify } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const can = (permission: string) => meeting.permissions.includes(permission as Meeting['permissions'][number])
  const active = ACTIVE_STATUSES.has(meeting.status)

  const retry = useMutation({
    mutationFn: () => sendJson<Meeting>(`/api/meetings/${meeting.id}/retry`, 'POST'),
    onSuccess: (result) => queryClient.setQueryData(queryKeys.meeting(meeting.id), result),
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const remove = useMutation({
    mutationFn: () => sendJson(`/api/meetings/${meeting.id}`, 'DELETE'),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: queryKeys.meeting(meeting.id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.meetings })
      notify('Совещание удалено вместе с записью')
      navigate('/')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const creator = meeting.created_by ? meeting.people[meeting.created_by] : undefined
  const chair = meeting.chair_id ? meeting.people[meeting.chair_id] : undefined

  return (
    <>
      <BackLink />
      <div className="mt-4 mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-bold tracking-[0.18em] text-lime-700 uppercase">{formatDate(meeting.meeting_date)}</p>
          <h1 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-balance sm:text-3xl">{meeting.title}</h1>
          <p className="mt-2 text-sm text-ink-muted">
            {creator && `Загрузил: ${creator}`}
            {creator && chair && ' · '}
            {chair && `Председатель: ${chair}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={meeting.status} />
          {canGlobal('audit:read') && (
            <Link to={`/audit?meeting=${meeting.id}`} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-forest-800 hover:bg-sand-100">
              <ScrollText className="size-3.5" /> Журнал
            </Link>
          )}
          {can('delete') && !active && (
            <Button size="sm" variant="ghost" icon={<Trash2 className="size-3.5" />} onClick={() => setConfirmDelete(true)}>
              Удалить
            </Button>
          )}
        </div>
      </div>

      {active && <ProcessingCard meeting={meeting} />}

      {meeting.status === 'failed' && (
        <div className="space-y-3">
          <Notice tone="error" title="Обработка завершилась ошибкой">
            {meeting.error}
          </Notice>
          {can('retry') && (
            <Button variant="primary" icon={<RefreshCw className="size-4" />} loading={retry.isPending} onClick={() => retry.mutate()}>
              Повторить обработку
            </Button>
          )}
        </div>
      )}

      {!can('read') && !active && meeting.status !== 'failed' && (
        <Card className="flex items-start gap-4 p-6">
          <Lock className="mt-0.5 size-5 shrink-0 text-ink-soft" aria-hidden />
          <div className="text-sm leading-relaxed">
            <p className="font-semibold">Содержание протокола недоступно для вашей роли</p>
            <p className="mt-1 text-ink-muted">Видны только название, дата и статус. Свои поручения смотрите в разделе «Мои поручения».</p>
          </div>
        </Card>
      )}

      {can('read') && ['ready', 'approved'].includes(meeting.status) && meeting.analysis && <MeetingWorkspace key={meeting.id} meeting={meeting} />}

      <ConfirmDialog open={confirmDelete} danger title="Удалить совещание?" confirmLabel="Удалить навсегда" loading={remove.isPending} onConfirm={() => remove.mutate()} onClose={() => setConfirmDelete(false)}>
        Будут удалены запись, транскрипт, протокол и сохранённые утверждённые копии. Действие нельзя отменить; в журнале останется запись об удалении.
      </ConfirmDialog>
    </>
  )
}

function ProcessingCard({ meeting }: { meeting: Meeting }) {
  const current = PROCESSING_STEPS.indexOf(meeting.status)
  return (
    <Card className="p-6">
      <p className="font-semibold">Запись обрабатывается на сервере</p>
      <p className="mt-1 text-sm text-ink-muted">Страницу можно закрыть: статус обновляется автоматически.</p>
      <ol className="mt-5 grid gap-3 sm:grid-cols-4">
        {PROCESSING_STEPS.map((step, index) => (
          <li key={step} className={clsx('flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm', index < current && 'border-lime-200 bg-lime-100', index === current && 'border-forest-700 bg-white font-semibold', index > current && 'border-sand-200 text-ink-soft')}>
            {index < current ? <Check className="size-4 text-lime-700" /> : <span className="grid size-5 place-items-center rounded-full bg-sand-100 text-[11px]">{index + 1}</span>}
            {STATUS_LABELS[step]}
          </li>
        ))}
      </ol>
    </Card>
  )
}
