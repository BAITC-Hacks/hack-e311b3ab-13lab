import { clsx } from 'clsx'
import { Headphones } from 'lucide-react'
import { useEffect, useState, type RefObject } from 'react'
import { request } from '../../api/client'
import type { Segment } from '../../api/types'
import { Field, Input } from '../../components/ui'
import { formatTimestamp } from '../../lib/format'

interface TranscriptPanelProps {
  meetingId: string
  canListen: boolean
  segments: Segment[]
  speakerNames: Record<string, string>
  confirmedSpeakers?: Record<string, string>
  editableSpeakers: boolean
  highlight: string | null
  audioRef: RefObject<HTMLAudioElement | null>
  onSpeakerName: (speaker: string, name: string) => void
}

export function TranscriptPanel({ meetingId, canListen, segments, speakerNames, confirmedSpeakers = {}, editableSpeakers, highlight, audioRef, onSpeakerName }: TranscriptPanelProps) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioError, setAudioError] = useState('')
  const [query, setQuery] = useState('')
  const [previousHighlight, setPreviousHighlight] = useState(highlight)
  if (previousHighlight !== highlight) {
    setPreviousHighlight(highlight)
    setQuery('')
  }
  const speakers = [...new Set(segments.map((segment) => segment.speaker).filter((speaker): speaker is string => Boolean(speaker)))]

  useEffect(() => {
    if (!canListen) return
    const controller = new AbortController()
    let url: string | null = null
    request(`/api/meetings/${encodeURIComponent(meetingId)}/audio`, { signal: controller.signal })
      .then((response) => response.blob())
      .then((blob) => {
        if (controller.signal.aborted) return
        url = URL.createObjectURL(blob)
        setAudioUrl(url)
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) setAudioError(error instanceof Error ? error.message : 'Не удалось загрузить запись')
      })
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [meetingId, canListen])

  function play(start: number) {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = start
    void audio.play().catch(() => undefined)
  }

  return (
    <aside className="rounded-2xl border border-sand-200 bg-white p-5 sm:p-7" aria-label="Источник">
      <h2 className="text-lg font-semibold">Запись и расшифровка</h2>
      {canListen ? (
        <>
          <audio ref={audioRef} onLoadedMetadata={() => {
            const start = segments.find((segment) => segment.id === highlight)?.start
            if (start != null && audioRef.current) audioRef.current.currentTime = start
          }} controls src={audioUrl ?? undefined} className="mt-3 w-full" />
          <p className="mt-2 text-xs text-ink-muted">{audioError || 'Нажмите на время, чтобы прослушать фрагмент.'}</p>
        </>
      ) : (
        <p className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
          <Headphones className="size-4" aria-hidden /> Прослушивание доступно секретарю и председателю.
        </p>
      )}

      {speakers.length > 0 && (
        <details className="mt-5 rounded-xl bg-sand-50 p-4"><summary className="cursor-pointer text-sm font-medium">Говорящие · {speakers.length} — сопоставить с именами</summary><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <p className="text-xs text-ink-muted sm:col-span-2 lg:col-span-3">Голосов: {speakers.length}. Сопоставьте голоса с именами по записи.</p>
          {speakers.map((speaker) =>
            editableSpeakers ? (
              <Field key={speaker} label={`Имя для «${speaker}»`}>
                <Input value={speakerNames[speaker] ?? ''} placeholder={speaker} onChange={(event) => onSpeakerName(speaker, event.target.value)} />
              </Field>
            ) : null,
          )}
        </div></details>
      )}

      <Input aria-label="Поиск в расшифровке" placeholder="Найти фразу в разговоре" value={query} onChange={(e) => setQuery(e.target.value)} className="my-4" />
      <div className="mt-4 max-h-[65vh] overflow-y-auto pr-1">
        {segments.filter((segment) => `${segment.text} ${segment.speaker ? speakerNames[segment.speaker] ?? segment.speaker : ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).map((segment) => (
          <div key={segment.id} id={`segment-${segment.id}`} className={clsx('border-b border-sand-200 py-3 text-sm leading-relaxed transition-colors', highlight === segment.id && 'rounded-lg bg-lime-200 px-2')}>
            <div className="mb-1 flex items-center gap-2">
              {segment.start !== null && canListen && (
                <button type="button" onClick={() => play(segment.start ?? 0)} className="rounded-md border border-sand-300 bg-white px-1.5 py-0.5 font-mono text-[11px] hover:bg-sand-50">
                  {formatTimestamp(segment.start)}
                </button>
              )}
              {segment.start !== null && !canListen && <span className="font-mono text-[11px] text-ink-soft">{formatTimestamp(segment.start)}</span>}
              <strong className="text-xs text-lime-700">{confirmedSpeakers[segment.id] || (segment.speaker && speakerNames[segment.speaker]) || segment.speaker || 'Говорящий не определён'}</strong>
              <span className="text-xs text-ink-muted">{confirmedSpeakers[segment.id] ? 'Подтверждено по аудио' : 'Имя не подтверждено'}</span>
              {segment.speaker_uncertain && <span className="text-xs text-amber-700">Проверьте по аудио</span>}
            </div>
            <p>{segment.text}</p>
          </div>
        ))}
      </div>
    </aside>
  )
}
