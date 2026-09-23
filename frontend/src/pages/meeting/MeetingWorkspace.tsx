import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCheck, Download, FileCheck2, RotateCcw, Save } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { downloadFile, sendJson } from '../../api/client'
import { queryKeys, useDirectory, useHealth } from '../../api/queries'
import type { Action, ActionStatus, Analysis, ExportFormat, Meeting, MeetingPermission, SourceReview } from '../../api/types'
import { useAuth } from '../../auth/context'
import { ConfirmDialog } from '../../components/Dialog'
import { useToast } from '../../components/toast-context'
import { Button, Card, Notice, Textarea } from '../../components/ui'
import { formatDateTime, isOverdue } from '../../lib/format'
import { ActionCard } from './ActionCard'
import { PeoplePanel } from './PeoplePanel'
import { TranscriptPanel } from './TranscriptPanel'
import { SourceReviewPanel } from './SourceReviewPanel'

interface Draft {
  analysis: Analysis
  speaker_names: Record<string, string>
  source_review: SourceReview
}

function draftFrom(meeting: Meeting): Draft {
  return structuredClone({ analysis: meeting.analysis as Analysis, speaker_names: meeting.speaker_names ?? {}, source_review: meeting.source_review ?? { terms: [], notes: [] } })
}

const EXPORTS: Array<{ format: ExportFormat; label: string; extension: string }> = [
  { format: 'docx', label: 'DOCX', extension: 'docx' },
  { format: 'pdf', label: 'PDF', extension: 'pdf' },
  { format: 'md', label: 'Markdown', extension: 'md' },
  { format: 'json', label: 'JSON', extension: 'json' },
]

export function MeetingWorkspace({ meeting }: { meeting: Meeting }) {
  const queryClient = useQueryClient()
  const { user, can: canGlobal } = useAuth()
  const { notify } = useToast()
  const health = useHealth()
  const can = (permission: MeetingPermission) => meeting.permissions.includes(permission)
  const directory = useDirectory(canGlobal('users:directory') && can('edit'))
  const audioRef = useRef<HTMLAudioElement>(null)

  const [draft, setDraft] = useState(() => draftFrom(meeting))
  const [draftVersion, setDraftVersion] = useState(meeting.version)
  if (draftVersion !== meeting.version) {
    // The server copy changed (save, approval, status update): start again from it.
    setDraftVersion(meeting.version)
    setDraft(draftFrom(meeting))
  }
  const [highlight, setHighlight] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<'approve' | 'reopen' | null>(null)

  const editable = can('edit') && meeting.status === 'ready'
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(draftFrom(meeting)), [draft, meeting])
  const actions = draft.analysis.actions
  const lastApproval = meeting.approvals.at(-1)

  function store(result: Meeting) {
    queryClient.setQueryData(queryKeys.meeting(meeting.id), result)
    void queryClient.invalidateQueries({ queryKey: queryKeys.meetings })
    void queryClient.invalidateQueries({ queryKey: queryKeys.tasks })
  }

  const save = useMutation({
    mutationFn: () => sendJson<Meeting>(`/api/meetings/${meeting.id}/review`, 'PUT', { version: meeting.version, analysis: draft.analysis, speaker_names: draft.speaker_names, source_review: { ...draft.source_review, terms: draft.source_review.terms.map((term) => term.trim()).filter(Boolean) } }),
    onSuccess: store,
  })

  async function saveIfNeeded(): Promise<number> {
    if (!editable || !dirty) return meeting.version
    return (await save.mutateAsync()).version
  }

  const approve = useMutation({
    mutationFn: async () => sendJson<Meeting>(`/api/meetings/${meeting.id}/approve`, 'POST', { version: await saveIfNeeded() }),
    onSuccess: (result) => {
      store(result)
      setConfirm(null)
      notify('Протокол утверждён')
      result.warnings?.forEach((warning) => notify(warning, 'info'))
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const reopen = useMutation({
    mutationFn: () => sendJson<Meeting>(`/api/meetings/${meeting.id}/reopen`, 'POST'),
    onSuccess: (result) => {
      store(result)
      setConfirm(null)
      notify('Протокол возвращён на доработку')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const statusUpdate = useMutation({
    mutationFn: ({ actionId, status }: { actionId: string; status: ActionStatus }) => sendJson<Meeting>(`/api/meetings/${meeting.id}/actions/${actionId}`, 'PATCH', { status }),
    onSuccess: (result) => {
      store(result)
      notify('Статус поручения обновлён')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  async function exportFile(format: ExportFormat, extension: string) {
    try {
      await saveIfNeeded()
      await downloadFile(`/api/meetings/${meeting.id}/export/${format}`, `protocol-${meeting.meeting_date}.${extension}`)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось выгрузить', 'error')
    }
  }

  async function downloadApproved(format: 'docx' | 'pdf') {
    try {
      await downloadFile(`/api/meetings/${meeting.id}/approved/${format}`, `protocol-${meeting.meeting_date}-v${lastApproval?.version}.${format}`)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Не удалось скачать', 'error')
    }
  }

  function updateAction(index: number, patch: Partial<Action>) {
    setDraft((current) => ({ ...current, analysis: { ...current.analysis, actions: current.analysis.actions.map((action, position) => (position === index ? { ...action, ...patch } : action)) } }))
  }

  function locateSegments(segmentIds: string[]) {
    const segment = meeting.segments?.find((item) => segmentIds.includes(item.id))
    if (!segment) return notify('Для этой цитаты нет точной привязки к транскрипту', 'info')
    setHighlight(segment.id)
    document.getElementById(`segment-${segment.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (segment.start !== null && audioRef.current) audioRef.current.currentTime = segment.start
  }

  const canChangeStatus = (action: Action) =>
    !editable && Boolean(action.id) && ((can('track') && ['ready', 'approved'].includes(meeting.status)) || (meeting.status === 'approved' && action.assignee_id === user?.id))

  const stats = [
    { label: 'Поручений', value: actions.length },
    { label: 'Требуют проверки', value: actions.filter((action) => action.needs_review).length },
    { label: 'Выполнено', value: actions.filter((action) => action.status === 'done').length },
    { label: 'Просрочено', value: actions.filter((action) => isOverdue(action)).length },
  ]

  return (
    <>
      {meeting.status === 'approved' && (
        <div className="mb-5">
          <Notice tone="success" title="Протокол утверждён">
            {formatDateTime(meeting.approved_at)} · {meeting.approved_by ? (meeting.people[meeting.approved_by] ?? 'пользователь удалён') : ''}. Правки закрыты; статусы поручений можно менять.
          </Notice>
        </div>
      )}

      <div className="mb-6 flex flex-wrap gap-2" role="toolbar" aria-label="Действия с протоколом">
        {editable && (
          <Button variant="primary" icon={<Save className="size-4" />} disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => notify('Изменения сохранены'), onError: (error) => notify(error.message, 'error') })}>
            Сохранить
          </Button>
        )}
        {can('approve') && meeting.status === 'ready' && (
          <Button icon={<CheckCheck className="size-4" />} onClick={() => setConfirm('approve')}>
            Утвердить
          </Button>
        )}
        {can('reopen') && meeting.status === 'approved' && (
          <Button icon={<RotateCcw className="size-4" />} onClick={() => setConfirm('reopen')}>
            Вернуть на доработку
          </Button>
        )}
        {can('export') &&
          EXPORTS.filter(({ format }) => (format !== 'json' || can('export_raw')) && (format !== 'pdf' || health.data?.pdf_configured !== false)).map(({ format, label, extension }) => (
            <Button key={format} variant="ghost" icon={<Download className="size-4" />} onClick={() => void exportFile(format, extension)}>
              {label}
            </Button>
          ))}
        {can('export') &&
          meeting.status === 'approved' &&
          lastApproval?.formats.map((format) => (
            <Button key={`approved-${format}`} variant="ghost" icon={<FileCheck2 className="size-4" />} onClick={() => void downloadApproved(format)}>
              Утверждённый {format.toUpperCase()}
            </Button>
          ))}
      </div>

      <dl className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-5">
            <dt className="text-xs text-ink-muted">{stat.label}</dt>
            <dd className="mt-1 text-3xl font-bold">{stat.value}</dd>
          </Card>
        ))}
      </dl>

      {draft.analysis.warnings.length > 0 && (
        <div className="mb-6 space-y-2">
          {draft.analysis.warnings.map((warning, index) => (
            <Notice key={index}>{warning}</Notice>
          ))}
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,1fr)]">
        <div className="min-w-0 space-y-6">
          <PeoplePanel key={`${meeting.chair_id}:${meeting.participant_ids.join()}`} meeting={meeting} directory={directory.data ?? []} editable={can('people')} />
          <SourceReviewPanel meetingId={meeting.id} segments={meeting.segments ?? []} actions={actions} value={draft.source_review} editable={editable && can('listen')}
            onChange={(source_review) => setDraft((current) => ({ ...current, source_review }))}
            onOwner={(actionId, owner) => setDraft((current) => ({ ...current, analysis: { ...current.analysis, actions: current.analysis.actions.map((action) => action.id === actionId ? { ...action, owner, owner_uncertain: false, owner_evidence: null, assignee_id: null, needs_review: true } : action) } }))}
            onLocate={(segmentId) => locateSegments([segmentId])} />

          <section>
            <h2 className="mb-3 text-lg font-semibold">Краткое содержание</h2>
            {Boolean(draft.analysis.numeric_fragments?.length) && <p className="mb-2 text-sm text-ink-muted">
              Числовых фрагментов дословно: {draft.analysis.numeric_fragments?.filter((item) => item.included).length}/{draft.analysis.numeric_fragments?.length}. Это не оценка точности фактов.{dirty ? ' После сохранения счётчик будет пересчитан.' : ''}
            </p>}
            {editable ? (
              <Textarea rows={5} value={draft.analysis.summary} onChange={(event) => setDraft((current) => ({ ...current, analysis: { ...current.analysis, summary: event.target.value } }))} aria-label="Краткое содержание" />
            ) : (
              <p className="leading-relaxed whitespace-pre-line">{draft.analysis.summary || '—'}</p>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Решения</h2>
            {draft.analysis.decisions.length ? (
              <ul className="list-disc space-y-1.5 pl-5 leading-relaxed">
                {draft.analysis.decisions.map((decision, index) => (
                  <li key={index}>{decision}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">Решения не выделены.</p>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">
              Поручения {editable && <span className="ml-2 text-xs font-normal text-ink-muted">Проверьте перед утверждением</span>}
            </h2>
            <div className="space-y-4">
              {actions.map((action, index) => (
                <ActionCard
                  key={action.id ?? index}
                  action={action}
                  index={index}
                  editable={editable}
                  canChangeStatus={canChangeStatus(action)}
                  statusPending={statusUpdate.isPending}
                  directory={directory.data ?? []}
                  people={meeting.people}
                  onChange={(patch) => updateAction(index, patch)}
                  onStatusChange={(status) => action.id && statusUpdate.mutate({ actionId: action.id, status })}
                  onLocate={() => locateSegments(action.segment_ids)}
                />
              ))}
              {actions.length === 0 && <p className="text-sm text-ink-muted">Поручения не выделены.</p>}
            </div>
          </section>
        </div>

        <TranscriptPanel
          meetingId={meeting.id}
          canListen={can('listen')}
          segments={meeting.segments ?? []}
          speakerNames={draft.speaker_names}
          confirmedSpeakers={Object.fromEntries(draft.source_review.notes.filter((note) => note.kind === 'speaker' && note.audio_checked).map((note) => [note.segment_id, note.text]))}
          editableSpeakers={editable}
          highlight={highlight}
          audioRef={audioRef}
          onSpeakerName={(speaker, name) => setDraft((current) => ({ ...current, speaker_names: { ...current.speaker_names, [speaker]: name } }))}
        />
      </div>

      <ConfirmDialog open={confirm === 'approve'} title="Утвердить протокол?" confirmLabel="Утвердить" loading={approve.isPending} onConfirm={() => approve.mutate()} onClose={() => setConfirm(null)}>
        Несохранённые правки будут сохранены. После утверждения протокол закрывается для правок, участники и исполнители получают к нему доступ, а копии DOCX и PDF сохраняются в хранилище.
      </ConfirmDialog>
      <ConfirmDialog open={confirm === 'reopen'} title="Вернуть на доработку?" confirmLabel="Вернуть" loading={reopen.isPending} onConfirm={() => reopen.mutate()} onClose={() => setConfirm(null)}>
        Участники потеряют доступ до повторного утверждения. Сохранённые копии прошлых утверждений останутся в хранилище.
      </ConfirmDialog>
    </>
  )
}
