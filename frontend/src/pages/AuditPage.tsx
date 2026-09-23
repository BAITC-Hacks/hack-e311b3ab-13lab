import { X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { useAudit } from '../api/queries'
import type { AuditEntry } from '../api/types'
import { Button, Card, EmptyState, Notice, PageHeader, Select, Spinner } from '../components/ui'
import { formatDateTime } from '../lib/format'
import { AUDIT_LABELS } from '../lib/labels'

const LIMITS = [100, 300, 1000]

function describe(detail: AuditEntry['detail']): string {
  return Object.entries(detail)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    .join(' · ')
}

export function AuditPage() {
  const [params, setParams] = useSearchParams()
  const meetingId = params.get('meeting') ?? ''
  const limit = Number(params.get('limit')) || 100
  const audit = useAudit(meetingId, limit)

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  return (
    <>
      <PageHeader
        eyebrow="Контроль"
        title="Журнал действий"
        actions={
          <Select aria-label="Количество записей" className="mt-0 w-36" value={limit} onChange={(event) => setParam('limit', event.target.value)}>
            {LIMITS.map((value) => (
              <option key={value} value={value}>
                {value} записей
              </option>
            ))}
          </Select>
        }
      >
        Входы, загрузки, правки, утверждения, прослушивания и выгрузки. Новые записи сверху.
      </PageHeader>
      {meetingId && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          Только совещание <code className="rounded bg-sand-100 px-1.5 py-0.5 text-xs">{meetingId}</code>
          <Button size="sm" variant="ghost" icon={<X className="size-3.5" />} onClick={() => setParam('meeting', '')}>
            Сбросить
          </Button>
        </div>
      )}
      {audit.isPending && <Spinner />}
      {audit.isError && <Notice tone="error">{audit.error.message}</Notice>}
      {audit.data?.length === 0 && <EmptyState title="Записей нет" />}
      {audit.data && audit.data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead className="border-b border-sand-200 text-xs text-ink-muted">
              <tr>
                <th className="px-5 py-3 font-medium">Время</th>
                <th className="px-5 py-3 font-medium">Пользователь</th>
                <th className="px-5 py-3 font-medium">Действие</th>
                <th className="px-5 py-3 font-medium">Совещание</th>
                <th className="px-5 py-3 font-medium">Подробности</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand-200">
              {audit.data.map((entry) => (
                <tr key={entry.id} className={entry.action === 'login_failed' ? 'bg-red-50/60' : undefined}>
                  <td className="px-5 py-3 whitespace-nowrap text-ink-muted">{formatDateTime(entry.at)}</td>
                  <td className="px-5 py-3">{entry.user_email ?? '—'}</td>
                  <td className="px-5 py-3 font-medium">{AUDIT_LABELS[entry.action] ?? entry.action}</td>
                  <td className="px-5 py-3">
                    {entry.meeting_id ? (
                      <Link to={`/audit?meeting=${entry.meeting_id}`} className="font-mono text-xs text-forest-800 underline">
                        {entry.meeting_id.slice(0, 8)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="max-w-md px-5 py-3 text-xs break-words text-ink-muted">{describe(entry.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
