import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCheck, Download, FileCheck2, RotateCcw, Save, ArrowRight, ListChecks, FileText, Headphones, Users, Search, Pencil, ChevronDown, MessageCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { downloadFile, sendJson } from '../../api/client'
import { queryKeys, useDirectory, useHealth } from '../../api/queries'
import type { Action, ActionStatus, Analysis, ExportFormat, Meeting, MeetingPermission, SourceReview } from '../../api/types'
import { useAuth } from '../../auth/context'
import { ConfirmDialog } from '../../components/Dialog'
import { useToast } from '../../components/toast-context'
import { Button, Card, Input, Notice, Textarea } from '../../components/ui'
import { formatDateTime, deadlineLabel } from '../../lib/format'
import { ActionCard } from './ActionCard'
import { PeoplePanel } from './PeoplePanel'
import { MeetingQA } from '../../features/qa/MeetingQA'
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
  const [view, setView] = useState<'overview' | 'actions' | 'recording' | 'people' | 'qa'>('overview')
  const [search, setSearch] = useState('')
  const [reviewOnly, setReviewOnly] = useState(false)
  const [editingSummary, setEditingSummary] = useState(false)
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
    setView('recording')
    setHighlight(segment.id)
  }

  const canChangeStatus = (action: Action) =>
    !editable && Boolean(action.id) && ((can('track') && ['ready', 'approved'].includes(meeting.status)) || (meeting.status === 'approved' && action.assignee_id === user?.id))

  useEffect(() => {
    if (view !== 'recording' || !highlight) return
    document.getElementById(`segment-${highlight}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const segment = meeting.segments?.find((item) => item.id === highlight)
    if (segment?.start != null && audioRef.current) audioRef.current.currentTime = segment.start
  }, [view, highlight, meeting.segments])

  const reviewCount = actions.filter((action) => action.needs_review).length
  const filteredActions = actions.map((action, index) => ({ action, index })).filter(({ action }) =>
    (!reviewOnly || action.needs_review) && `${action.title} ${action.owner ?? ''} ${action.deadline_text ?? ''}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  const tabs = [
    { id: 'overview', label: 'Обзор', icon: FileText },
    { id: 'actions', label: 'Поручения', icon: ListChecks },
    { id: 'recording', label: 'Запись и речь', icon: Headphones },
    { id: 'people', label: 'Участники', icon: Users },
    { id: 'qa', label: 'Q&A · демо', icon: MessageCircle },
  ] as const

  return (
    <>
      <div className="workspace-toolbar" role="toolbar" aria-label="Действия с протоколом">
        <div className="text-sm text-ink-muted" role="status">
          {dirty ? <span className="font-medium text-amber-800">Есть несохранённые изменения</span> : meeting.status === 'approved' ? 'Утверждённый протокол' : 'Черновик · проверьте перед утверждением'}
        </div>
        <div className="flex flex-wrap gap-2">
          {editable && dirty && <Button variant="primary" icon={<Save className="size-4" />} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => notify('Изменения сохранены'), onError: (error) => notify(error.message, 'error') })}>Сохранить</Button>}
          {can('export') && <details className="export-menu">
            <summary className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-sand-200 bg-white px-4 py-2.5 text-sm"><Download className="size-4" /> Скачать <ChevronDown className="size-3" /></summary>
            <div className="export-options">
              {EXPORTS.filter(({ format }) => (format !== 'json' || can('export_raw')) && (format !== 'pdf' || health.data?.pdf_configured !== false)).map(({ format, label, extension }) => <Button key={format} variant="ghost" className="w-full justify-start" onClick={() => void exportFile(format, extension)}>{label}</Button>)}
              {meeting.status === 'approved' && lastApproval?.formats.map((format) => <Button key={format} variant="ghost" icon={<FileCheck2 className="size-4" />} onClick={() => void downloadApproved(format)}>Утверждённый {format.toUpperCase()}</Button>)}
            </div>
          </details>}
          {can('approve') && meeting.status === 'ready' && <Button variant="primary" icon={<CheckCheck className="size-4" />} onClick={() => setConfirm('approve')}>Утвердить</Button>}
          {can('reopen') && meeting.status === 'approved' && <Button icon={<RotateCcw className="size-4" />} onClick={() => setConfirm('reopen')}>На доработку</Button>}
        </div>
      </div>

      <nav className="workspace-tabs" aria-label="Содержание совещания">
        {tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-label={id === 'actions' ? `${label} ${actions.length}` : label} aria-current={view === id ? 'page' : undefined} onClick={() => setView(id)}><Icon className="size-4" />{label}{id === 'actions' && <span className="tab-count">{actions.length}</span>}</button>)}
      </nav>

      {meeting.status === 'approved' && <div className="mb-5"><Notice tone="success" title="Протокол утверждён">{formatDateTime(meeting.approved_at)} · {meeting.approved_by ? (meeting.people[meeting.approved_by] ?? 'пользователь удалён') : ''}</Notice></div>}

      {view === 'overview' && <div className="overview-grid">
        <div className="space-y-6">
          <Card className="p-5 sm:p-7">
            <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">О чём договорились</h2>{editable && <Button size="sm" variant="ghost" icon={<Pencil className="size-3.5" />} onClick={() => setEditingSummary(!editingSummary)}>{editingSummary ? 'Завершить правку' : 'Изменить'}</Button>}</div>
            {Boolean(draft.analysis.numeric_fragments?.length) && <p className="mb-2 text-sm text-ink-muted">
              Числовых фрагментов дословно: {draft.analysis.numeric_fragments?.filter((item) => item.included).length}/{draft.analysis.numeric_fragments?.length}. Это не оценка точности фактов.{dirty ? ' После сохранения счётчик будет пересчитан.' : ''}
            </p>}
            {Boolean(draft.analysis.numeric_fragments?.length) && <details className="mb-3 text-sm">
              <summary className="cursor-pointer">Проверить числовые фрагменты по источнику</summary>
              <p className="my-2 text-ink-muted">Это исходные фрагменты ASR, а не подтверждённые факты. Отсутствие дословного совпадения может означать пересказ. Ошибки распознавания проверяются по аудио.</p>
              <ul className="space-y-2">
                {draft.analysis.numeric_fragments?.map((item, index) => <li key={`${item.segment_id}:${index}`}>
                  <button type="button" className="underline" onClick={() => locateSegments([item.segment_id])}>{item.segment_id}</button>
                  {' — '}{item.text}{' '}<span className="text-ink-muted">({item.included ? 'дословно в саммари' : 'нет полного дословного совпадения'})</span>
                </li>)}
              </ul>
            </details>}
            {editingSummary && editable ? <Textarea rows={7} value={draft.analysis.summary} aria-label="Краткое содержание" onChange={(event) => setDraft((current) => ({ ...current, analysis: { ...current.analysis, summary: event.target.value } }))} /> : <p className="summary-copy">{draft.analysis.summary || 'Краткое содержание пока не подготовлено.'}</p>}
            {draft.analysis.decisions.length > 0 && <div className="mt-6 border-t border-sand-200 pt-5"><h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-muted">Ключевые решения</h3><ul className="decision-list">{draft.analysis.decisions.map((decision, i) => <li key={i}><span>{String(i+1).padStart(2, '0')}</span><p>{decision}</p></li>)}</ul></div>}
          </Card>
          <section aria-label="Краткий список поручений">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Следующие шаги</h2><Button size="sm" variant="ghost" onClick={() => setView('actions')} icon={<ArrowRight className="size-4" />}>Все поручения</Button></div>
            <div className="overflow-hidden rounded-2xl border border-sand-200 bg-white">{actions.slice(0, 4).map((action, i) => <button type="button" key={action.id ?? i} className="action-preview" onClick={() => {setSearch(action.title); setReviewOnly(false); setView('actions')}}><span className="action-number">{String(i+1).padStart(2, '0')}</span><span className="min-w-0 flex-1"><span className="block text-sm font-medium leading-relaxed">{action.title}</span><span className="mt-1 block text-xs text-ink-muted">{action.owner || 'Исполнитель не указан'} · {deadlineLabel(action)}</span></span><ArrowRight className="size-4 shrink-0 text-ink-soft" /></button>)}{!actions.length && <p className="p-5 text-sm text-ink-muted">Поручения не выделены.</p>}</div>
          </section>
        </div>
        <aside className="space-y-4">
          <div className="review-guide"><span className="text-xs font-semibold uppercase tracking-widest text-forest-200">Перед утверждением</span><h2 className="mt-4 text-2xl font-semibold">{reviewCount ? `${reviewCount} поручений ждут проверки` : 'Поручения проверены'}</h2><p className="mt-3 text-sm leading-relaxed text-forest-100">Сверьте исполнителей и сроки. Каждое поручение связано с исходной репликой.</p><Button className="mt-5 w-full" variant="primary" onClick={() => {setSearch(''); setReviewOnly(reviewCount > 0); setView('actions')}}>{reviewCount ? 'Проверить поручения' : 'Открыть поручения'}<ArrowRight className="size-4" /></Button><div className="mt-5 flex justify-between border-t border-forest-700 pt-4 text-xs text-forest-200"><span>{actions.length} всего</span><span>{actions.length - reviewCount} проверено</span></div></div>
          {draft.analysis.warnings.length > 0 && <details className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><summary className="cursor-pointer text-sm font-semibold text-amber-900">На что обратить внимание · {draft.analysis.warnings.length}</summary><ul className="mt-3 list-disc space-y-3 pl-4 text-xs leading-relaxed text-amber-900">{draft.analysis.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details>}
          <button className="w-full rounded-2xl border border-sand-200 bg-white p-5 text-left" type="button" onClick={() => setView('recording')}><Headphones className="mb-3 size-5 text-forest-700" /><span className="block text-sm font-semibold">Вернуться к разговору</span><span className="mt-1 block text-xs text-ink-muted">Аудиозапись, реплики и голоса →</span></button>
        </aside>
      </div>}

      {view === 'actions' && <section aria-label="Список поручений">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Поручения <span className="font-normal text-ink-soft">/ {actions.length}</span></h2><p className="mt-1 text-sm text-ink-muted">Раскройте поручение, чтобы проверить цитату и внести правки.</p></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewOnly} onChange={(e) => setReviewOnly(e.target.checked)} className="size-4 accent-forest-700" />Только непроверенные ({reviewCount})</label></div>
        <div className="relative mb-5"><Search className="pointer-events-none absolute top-3 left-3 size-4 text-ink-soft" /><Input className="mt-0 pl-10" placeholder="Найти по поручению, имени или сроку" aria-label="Поиск поручений" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <div className="space-y-3">{filteredActions.map(({ action, index }) => <ActionCard key={action.id ?? index} action={action} index={index} editable={editable} canChangeStatus={canChangeStatus(action)} statusPending={statusUpdate.isPending} directory={directory.data ?? []} people={meeting.people} onChange={(patch) => updateAction(index, patch)} onStatusChange={(status) => action.id && statusUpdate.mutate({ actionId: action.id, status })} onLocate={() => locateSegments(action.segment_ids)} />)}</div>
        {!filteredActions.length && <div className="py-12 text-center"><p className="text-ink-muted">По выбранным условиям поручений нет.</p><Button className="mt-3" onClick={() => {setSearch(''); setReviewOnly(false)}}>Показать все</Button></div>}
      </section>}

      {view === 'recording' && <div className="space-y-6"><TranscriptPanel meetingId={meeting.id} canListen={can('listen')} segments={meeting.segments ?? []} speakerNames={draft.speaker_names} confirmedSpeakers={Object.fromEntries(draft.source_review.notes.filter((note) => note.kind === 'speaker' && note.audio_checked).map((note) => [note.segment_id, note.text]))} editableSpeakers={editable} highlight={highlight} audioRef={audioRef} onSpeakerName={(speaker, name) => setDraft((current) => ({ ...current, speaker_names: { ...current.speaker_names, [speaker]: name } }))} />
          <SourceReviewPanel meetingId={meeting.id} segments={meeting.segments ?? []} actions={actions} value={draft.source_review} editable={editable && can('listen')}
            onChange={(source_review) => setDraft((current) => ({ ...current, source_review }))}
            onOwner={(actionId, owner) => setDraft((current) => ({ ...current, analysis: { ...current.analysis, actions: current.analysis.actions.map((action) => action.id === actionId ? { ...action, owner, owner_uncertain: false, owner_evidence: null, assignee_id: null, needs_review: true } : action) } }))}
            onLocate={(segmentId) => locateSegments([segmentId])} />
      </div>}
      {view === 'qa' && <div className="meeting-qa-layout"><div><p className="brand-eyebrow">ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</p><h2 className="mt-3 text-2xl font-semibold">Вопросы по встрече</h2><p className="mt-3 text-sm leading-relaxed text-ink-muted">Скоро здесь можно будет спрашивать о решениях и поручениях текущего совещания. Пока попробуйте интерфейс на вымышленном примере «Планирование запуска».</p><p className="mt-4 text-xs text-ink-muted">Ваши данные в этом демо не используются.</p></div><MeetingQA context="meeting" /></div>}
      {view === 'people' && dirty && <Notice tone="info">Сначала сохраните правки протокола кнопкой «Сохранить», затем измените участников и доступ.</Notice>}
      {view === 'people' && !dirty && <PeoplePanel key={`${meeting.chair_id}:${meeting.participant_ids.join()}`} meeting={meeting} directory={directory.data ?? []} editable={can('people')} />}

      <ConfirmDialog open={confirm === 'approve'} title="Утвердить протокол?" confirmLabel="Утвердить" loading={approve.isPending} onConfirm={() => approve.mutate()} onClose={() => setConfirm(null)}>
        Несохранённые правки будут сохранены. После утверждения протокол закрывается для правок, участники и исполнители получают к нему доступ, а копии DOCX и PDF сохраняются в хранилище.
      </ConfirmDialog>
      <ConfirmDialog open={confirm === 'reopen'} title="Вернуть на доработку?" confirmLabel="Вернуть" loading={reopen.isPending} onConfirm={() => reopen.mutate()} onClose={() => setConfirm(null)}>
        Участники потеряют доступ до повторного утверждения. Сохранённые копии прошлых утверждений останутся в хранилище.
      </ConfirmDialog>
    </>
  )
}
