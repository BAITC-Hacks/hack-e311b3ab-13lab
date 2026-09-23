import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Mic, Square, Users } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendJson } from '../../api/client'
import { queryKeys } from '../../api/queries'
import type { Meeting } from '../../api/types'
import { useToast } from '../../components/toast-context'
import { Button, Card, Notice } from '../../components/ui'
import { formatTimestamp } from '../../lib/format'
import { LIVE_STATUS_LABELS, PLATFORM_LABELS } from '../../lib/labels'
import { CaptureError, pickMeetingTab, pickMicrophone, tabCapture } from '../../live/capture'
import { useCaptureState } from '../../live/useCapture'
import { useLiveEvents } from '../../live/useLiveEvents'

function useElapsed(startedAt: string | undefined) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return startedAt ? Math.max(0, (now - new Date(startedAt).getTime()) / 1000) : 0
}

export function LiveView({ meeting }: { meeting: Meeting }) {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const live = useLiveEvents(meeting.id, meeting.status === 'live')
  const capture = useCaptureState()
  const elapsed = useElapsed(meeting.live?.started_at)
  const transcriptEnd = useRef<HTMLDivElement>(null)
  const [resumeError, setResumeError] = useState('')
  const canEdit = meeting.permissions.includes('edit')
  const isTab = meeting.live?.connector === 'tab'
  const capturingHere = (capture.status === 'streaming' || capture.status === 'reconnecting') && capture.meetingId === meeting.id

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: 'nearest' })
  }, [live.segments.length])

  const stop = useMutation({
    mutationFn: () => sendJson<Meeting>(`/api/live/${meeting.id}/stop`, 'POST'),
    onSuccess: (result) => {
      tabCapture.stop('Сессия завершена')
      queryClient.setQueryData(queryKeys.meeting(meeting.id), result)
      notify('Сессия завершается: готовим протокол')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  async function resume() {
    setResumeError('')
    try {
      const room = meeting.live?.platform === 'room'
      const streams = room ? await pickMicrophone() : await pickMeetingTab(true)
      await tabCapture.start(meeting.id, streams, true)
    } catch (error) {
      setResumeError(error instanceof CaptureError || error instanceof Error ? error.message : 'Не удалось возобновить захват')
    }
  }

  const status = live.status
  const recording = status === 'live'

  return (
    <div className="space-y-6">
      <Card className={clsx('flex flex-wrap items-center gap-4 p-5', recording ? 'border-red-200 bg-red-50/40' : 'border-sand-200')}>
        <span className={clsx('relative flex size-3', !recording && 'opacity-40')} aria-hidden>
          {recording && <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />}
          <span className="relative inline-flex size-3 rounded-full bg-red-500" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold" role="status">
            {LIVE_STATUS_LABELS[status] ?? status}
          </p>
          <p className="text-sm text-ink-muted">
            {PLATFORM_LABELS[meeting.live?.platform ?? 'browser']} · {meeting.live?.connector === 'bot' ? `бот «${meeting.live?.bot_name ?? 'HATTAMA.AI'}»` : meeting.live?.platform === 'room' ? 'микрофон' : 'захват вкладки'} · {formatTimestamp(elapsed)}
            {live.lag > 5 && ` · расшифровка отстаёт на ${Math.round(live.lag)} с`}
          </p>
          {live.detail && <p className="mt-1 text-xs text-ink-muted">{live.detail}</p>}
        </div>
        {capturingHere && (
          <div className="flex items-center gap-2 text-xs text-ink-muted" aria-label="Уровень звука">
            <Mic className="size-4" aria-hidden />
            <div className="h-2 w-24 overflow-hidden rounded-full bg-sand-200">
              <div className="h-2 rounded-full bg-forest-700 transition-[width]" style={{ width: `${Math.min(100, capture.level * 400)}%` }} />
            </div>
            {capture.status === 'reconnecting' && 'переподключение…'}
          </div>
        )}
        {canEdit && (
          <Button variant="danger" icon={<Square className="size-4" />} loading={stop.isPending} onClick={() => stop.mutate()}>
            Завершить и подготовить протокол
          </Button>
        )}
      </Card>

      {isTab && canEdit && !capturingHere && (
        <Notice title="Звук из этого браузера не передаётся">
          <p>Если захват шёл в этой вкладке и страница перезагрузилась, возобновите его. Без звука сессия завершится автоматически.</p>
          <Button size="sm" className="mt-2" onClick={() => void resume()}>
            {meeting.live?.platform === 'room' ? 'Возобновить запись с микрофона' : 'Возобновить захват вкладки'}
          </Button>
          {resumeError && <p className="mt-2 text-red-700">{resumeError}</p>}
        </Notice>
      )}
      {live.warnings.map((warning, index) => (
        <Notice key={index}>{warning}</Notice>
      ))}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
        <Card className="p-5">
          <h2 className="text-lg font-semibold">Расшифровка в реальном времени</h2>
          <p className="mt-1 text-xs text-ink-muted">Фрагменты появляются после паузы в речи, обычно с задержкой 10–30 секунд. Итоговый протокол строится по полной записи.</p>
          <div className="mt-4 max-h-[60vh] space-y-3 overflow-y-auto pr-1" aria-live="polite">
            {live.segments.length === 0 && <p className="py-8 text-center text-sm text-ink-muted">{recording ? 'Ждём первую фразу…' : 'Расшифровка начнётся, когда появится звук.'}</p>}
            {live.segments.map((segment) => (
              <div key={segment.id} className="border-b border-sand-200 pb-3 text-sm leading-relaxed">
                <span className="mr-2 font-mono text-[11px] text-ink-soft">{segment.start !== null ? formatTimestamp(segment.start) : ''}</span>
                {segment.speaker && <strong className="mr-2 text-xs text-lime-700">{segment.speaker}</strong>}
                {segment.text}
              </div>
            ))}
            <div ref={transcriptEnd} />
          </div>
        </Card>
        <Card className="h-fit p-5">
          <h2 className="flex items-center gap-2 font-semibold">
            <Users className="size-4" aria-hidden /> Участники
          </h2>
          {live.participants.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">{meeting.live?.connector === 'bot' ? 'Список появится, когда бот войдёт во встречу.' : 'При захвате вкладки платформа не передаёт список участников: говорящих определит диаризация.'}</p>
          ) : (
            <ul className="mt-3 space-y-1.5 text-sm">
              {live.participants.map((participant) => (
                <li key={participant.platform_id} className={clsx('flex items-center gap-2', !participant.present && 'text-ink-soft line-through')}>
                  <span className={clsx('size-2 rounded-full', live.speaking === participant.name ? 'bg-red-500' : 'bg-sand-300')} aria-hidden />
                  {participant.name}
                  {live.speaking === participant.name && <span className="text-xs text-red-600">говорит</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
