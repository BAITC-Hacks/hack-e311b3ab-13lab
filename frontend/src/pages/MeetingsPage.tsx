import { clsx } from 'clsx'
import { ChevronRight, FilePlus2, Search, Video } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useMeetings } from '../api/queries'
import type { MeetingSummary } from '../api/types'
import { useAuth } from '../auth/context'
import { Card, EmptyState, Input, Notice, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { formatDate } from '../lib/format'
import { ACTIVE_STATUSES } from '../lib/labels'

const FILTERS: Array<{ id: string; label: string; match: (meeting: MeetingSummary) => boolean }> = [
  { id: 'all', label: 'Все', match: () => true },
  { id: 'processing', label: 'В обработке', match: (meeting) => ACTIVE_STATUSES.has(meeting.status) },
  { id: 'ready', label: 'На проверке', match: (meeting) => meeting.status === 'ready' },
  { id: 'approved', label: 'Утверждены', match: (meeting) => meeting.status === 'approved' },
  { id: 'failed', label: 'Ошибки', match: (meeting) => meeting.status === 'failed' },
]

export function MeetingsPage() {
  const { user, can } = useAuth()
  const meetings = useMeetings()
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const canCreate = can('meetings:create')

  const visible = useMemo(() => {
    const matcher = FILTERS.find((item) => item.id === filter)?.match ?? (() => true)
    const needle = search.trim().toLocaleLowerCase('ru')
    return (meetings.data ?? []).filter((meeting) => matcher(meeting) && (!needle || meeting.title.toLocaleLowerCase('ru').includes(needle)))
  }, [meetings.data, filter, search])

  return (
    <>
      <PageHeader
        eyebrow="Протоколы"
        title="Совещания"
        actions={
          canCreate && (
            <Link to="/meetings/new" className="inline-flex items-center gap-2 rounded-lg bg-lime-300 px-4 py-2.5 text-sm font-semibold text-forest-900 hover:bg-lime-400">
              <FilePlus2 className="size-4" /> Новое совещание
            </Link>
          )
        }
      >
        {user?.role === 'participant' && 'Здесь появляются утверждённые протоколы совещаний, в которых вы указаны участником.'}
        {user?.role === 'auditor' && 'Вам доступны только метаданные совещаний: название, дата и статус.'}
      </PageHeader>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl bg-sand-100 p-1" role="tablist" aria-label="Фильтр по статусу">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              onClick={() => setFilter(item.id)}
              className={clsx('rounded-lg px-3 py-1.5 text-sm', filter === item.id ? 'bg-white font-semibold shadow-sm' : 'text-ink-muted hover:text-ink')}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-full sm:w-64">
          <Search className="pointer-events-none absolute top-1/2 left-3 mt-0.5 size-4 -translate-y-1/2 text-ink-soft" aria-hidden />
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию" aria-label="Поиск по названию" className="pl-9" />
        </div>
      </div>

      {meetings.isPending && <Spinner />}
      {meetings.isError && <Notice tone="error">{meetings.error.message}</Notice>}
      {meetings.data && meetings.data.length === 0 && (
        <EmptyState
          icon={<Video className="size-8" />}
          title="Совещаний пока нет"
          action={
            canCreate && (
              <Link to="/meetings/new" className="text-sm font-semibold text-forest-800 underline">
                Загрузить первую запись
              </Link>
            )
          }
        >
          {canCreate ? 'Загрузите запись совещания, чтобы получить протокол и поручения.' : 'Когда протокол с вашим участием утвердят, он появится здесь.'}
        </EmptyState>
      )}
      {meetings.data && meetings.data.length > 0 && visible.length === 0 && <Notice tone="info">Нет совещаний по выбранному фильтру.</Notice>}
      {visible.length > 0 && (
        <Card className="divide-y divide-sand-200 overflow-hidden">
          {visible.map((meeting) => (
            <Link key={meeting.id} to={`/meetings/${meeting.id}`} className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-sand-50">
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{meeting.title}</p>
                <p className="mt-0.5 text-sm text-ink-muted">{formatDate(meeting.meeting_date)}</p>
              </div>
              <StatusBadge status={meeting.status} />
              <ChevronRight className="size-4 shrink-0 text-ink-soft" aria-hidden />
            </Link>
          ))}
        </Card>
      )}
    </>
  )
}
