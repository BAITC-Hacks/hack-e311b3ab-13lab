import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { ClipboardList } from 'lucide-react'
import { Link } from 'react-router'
import { sendJson } from '../api/client'
import { queryKeys, useMyActions } from '../api/queries'
import type { ActionStatus, Meeting } from '../api/types'
import { useToast } from '../components/toast-context'
import { Badge, Card, EmptyState, Notice, PageHeader, Select, Spinner } from '../components/ui'
import { deadlineLabel, formatDate, isOverdue } from '../lib/format'
import { ACTION_STATUS_LABELS } from '../lib/labels'

export function TasksPage() {
  const tasks = useMyActions()
  const queryClient = useQueryClient()
  const { notify } = useToast()

  const update = useMutation({
    mutationFn: ({ meetingId, actionId, status }: { meetingId: string; actionId: string; status: ActionStatus }) => sendJson<Meeting>(`/api/meetings/${meetingId}/actions/${actionId}`, 'PATCH', { status }),
    onSuccess: (meeting) => {
      queryClient.setQueryData(queryKeys.meeting(meeting.id), meeting)
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks })
      notify('Статус обновлён')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const open = (tasks.data ?? []).filter((task) => task.action.status !== 'done').length

  return (
    <>
      <PageHeader eyebrow="Исполнение" title="Мои поручения">
        Поручения из утверждённых протоколов, где вы назначены исполнителем{tasks.data ? ` · открыто: ${open}` : ''}.
      </PageHeader>
      {tasks.isPending && <Spinner />}
      {tasks.isError && <Notice tone="error">{tasks.error.message}</Notice>}
      {tasks.data?.length === 0 && (
        <EmptyState icon={<ClipboardList className="size-8" />} title="Поручений нет">
          Когда секретарь назначит вас исполнителем и утвердит протокол, поручение появится здесь.
        </EmptyState>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {tasks.data?.map(({ meeting_id, meeting_title, meeting_date, action }) => {
          const overdue = isOverdue(action)
          return (
            <Card key={`${meeting_id}:${action.id}`} className={clsx('flex flex-col p-5', overdue && 'border-red-200')}>
              <Link to={`/meetings/${meeting_id}`} className="text-xs text-ink-muted hover:text-ink">
                {meeting_title} · {formatDate(meeting_date)}
              </Link>
              <p className="mt-2 font-semibold leading-snug">{action.title}</p>
              <blockquote className="mt-3 border-l-3 border-lime-200 pl-3 text-sm text-ink-muted">{action.evidence}</blockquote>
              <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-4">
                <div className="text-sm">
                  <span className="text-xs text-ink-soft">Срок</span>
                  <p className={clsx(overdue && 'font-semibold text-red-700')}>
                    {deadlineLabel(action)} {overdue && <Badge tone="danger">Просрочено</Badge>}
                  </p>
                </div>
                <div className="w-44">
                  <Select
                    aria-label="Статус поручения"
                    className="mt-0 py-1.5"
                    value={action.status}
                    disabled={update.isPending || !action.id}
                    onChange={(event) => action.id && update.mutate({ meetingId: meeting_id, actionId: action.id, status: event.target.value as ActionStatus })}
                  >
                    {Object.entries(ACTION_STATUS_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </>
  )
}
