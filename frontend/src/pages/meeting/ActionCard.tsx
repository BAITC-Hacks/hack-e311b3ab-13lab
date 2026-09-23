import { clsx } from 'clsx'
import { AlertTriangle, CheckCircle2, LocateFixed } from 'lucide-react'
import type { Action, ActionStatus, DirectoryUser } from '../../api/types'
import { Badge, Button, Field, Input, Select, Textarea } from '../../components/ui'
import { deadlineLabel, isOverdue } from '../../lib/format'
import { ACTION_STATUS_LABELS } from '../../lib/labels'

interface ActionCardProps {
  action: Action
  index: number
  editable: boolean
  canChangeStatus: boolean
  statusPending?: boolean
  directory: DirectoryUser[]
  people: Record<string, string>
  onChange: (patch: Partial<Action>) => void
  onStatusChange: (status: ActionStatus) => void
  onLocate: () => void
}

const STATUSES = Object.entries(ACTION_STATUS_LABELS) as Array<[ActionStatus, string]>

export function ActionCard({ action, index, editable, canChangeStatus, statusPending, directory, people, onChange, onStatusChange, onLocate }: ActionCardProps) {
  const overdue = isOverdue(action)
  const assigneeName = action.assignee_id ? (people[action.assignee_id] ?? directory.find((user) => user.id === action.assignee_id)?.name) : undefined
  const knownAssignee = !action.assignee_id || directory.some((user) => user.id === action.assignee_id)

  return (
    <article className={clsx('rounded-2xl border bg-white p-5', overdue ? 'border-red-200' : 'border-sand-200')} aria-label={`Поручение ${index + 1}`}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold tracking-[0.15em] text-ink-soft">ПОРУЧЕНИЕ {String(index + 1).padStart(2, '0')}</span>
        {action.needs_review ? (
          <Badge tone="review">
            <AlertTriangle className="size-3" aria-hidden /> Требует проверки
          </Badge>
        ) : (
          <Badge tone="success">
            <CheckCircle2 className="size-3" aria-hidden /> Проверено
          </Badge>
        )}
        {overdue && <Badge tone="danger">Просрочено</Badge>}
      </div>

      {editable ? (
        <Textarea rows={2} value={action.title} onChange={(event) => onChange({ title: event.target.value })} aria-label="Суть поручения" className="mt-0 font-semibold" />
      ) : (
        <p className="font-semibold leading-snug">{action.title}</p>
      )}

      {editable ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Ответственный из речи">
            <Input value={action.owner ?? ''} onChange={(event) => onChange({ owner: event.target.value || null })} />
          </Field>
          <Field label="Дата исполнения" hint={`В речи: ${action.deadline_text || 'не указан'}`}>
            <Input type="date" value={action.due_date ?? ''} onChange={(event) => onChange({ due_date: event.target.value || null })} />
          </Field>
          <Field label="Исполнитель в системе" hint="Увидит поручение после утверждения">
            <Select value={action.assignee_id ?? ''} onChange={(event) => onChange({ assignee_id: event.target.value || null })}>
              <option value="">Не назначен</option>
              {!knownAssignee && <option value={action.assignee_id ?? ''}>{assigneeName ?? 'Недоступный пользователь'}</option>}
              {directory.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name} · {user.role_label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Статус">
            <Select value={action.status} onChange={(event) => onChange({ status: event.target.value as ActionStatus })}>
              {STATUSES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      ) : (
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-ink-soft">Ответственный</dt>
            <dd className="mt-0.5">{assigneeName ?? action.owner ?? 'Не указан'}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-soft">Срок</dt>
            <dd className={clsx('mt-0.5', overdue && 'font-semibold text-red-700')}>{deadlineLabel(action)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-soft">Статус</dt>
            <dd className="mt-0.5">
              {canChangeStatus ? (
                <Select value={action.status} disabled={statusPending} onChange={(event) => onStatusChange(event.target.value as ActionStatus)} aria-label="Статус поручения" className="mt-0 py-1.5">
                  {STATUSES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              ) : (
                ACTION_STATUS_LABELS[action.status]
              )}
            </dd>
          </div>
        </dl>
      )}

      <blockquote className="mt-4 border-l-3 border-lime-200 pl-3 text-sm leading-relaxed text-ink-muted">{action.evidence}</blockquote>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Button size="sm" variant="ghost" onClick={onLocate} icon={<LocateFixed className="size-3.5" />}>
          Найти в транскрипте
        </Button>
        {editable && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!action.needs_review} onChange={(event) => onChange({ needs_review: !event.target.checked })} className="size-4 accent-forest-700" />
            Проверено секретарём
          </label>
        )}
      </div>
    </article>
  )
}
