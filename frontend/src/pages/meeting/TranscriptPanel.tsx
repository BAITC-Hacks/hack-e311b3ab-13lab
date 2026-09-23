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
  editableSpeakers: boolean
  highlight: string | null
  audioRef: RefObject<HTMLAudioElement | null>
  onSpeakerName: (speaker: string, name: string) => void
}

export function TranscriptPanel({ meetingId, canListen, segments, speakerNames, editableSpeakers, highlight, audioRef, onSpeakerName }: TranscriptPanelProps) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioError, setAudioError] = useState('')
  const speakers = [...new Set(segments.map((segment) => segment.speaker).filter((speaker): speaker is string => Boolean(speaker)))]

  useEffect(() => {
    if (!canListen) return
    const controller = new AbortController()
    let url: string | null = null
    request(`/api/meetings/${encodeURIComponent(meetingId)}/audio`, { signal: controller.signal })
      .then((response) => response.blob())
      .then((blob) => {
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
    <aside className="rounded-2xl bg-sand-100 p-5 lg:sticky lg:top-6 lg:self-start" aria-label="Источник">
      <h2 className="text-lg font-semibold">Источник</h2>
      {canListen ? (
        <>
          <audio ref={audioRef} controls src={audioUrl ?? undefined} className="mt-3 w-full" />
          <p className="mt-2 text-xs text-ink-muted">{audioError || 'Нажмите на время, чтобы прослушать фрагмент.'}</p>
        </>
      ) : (
        <p className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
          <Headphones className="size-4" aria-hidden /> Прослушивание доступно секретарю и председателю.
        </p>
      )}

      {speakers.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-ink-muted">Голосов: {speakers.length}. Сопоставьте голоса с именами по записи.</p>
          {speakers.map((speaker) =>
            editableSpeakers ? (
              <Field key={speaker} label={`Имя для «${speaker}»`}>
                <Input value={speakerNames[speaker] ?? ''} placeholder={speaker} onChange={(event) => onSpeakerName(speaker, event.target.value)} />
              </Field>
            ) : null,
          )}
        </div>
      )}

      <div className="mt-4 max-h-[65vh] overflow-y-auto pr-1">
        {segments.map((segment) => (
          <div key={segment.id} id={`segment-${segment.id}`} className={clsx('border-b border-sand-200 py-3 text-sm leading-relaxed transition-colors', highlight === segment.id && 'rounded-lg bg-lime-200 px-2')}>
            <div className="mb-1 flex items-center gap-2">
              {segment.start !== null && canListen && (
                <button type="button" onClick={() => play(segment.start ?? 0)} className="rounded-md border border-sand-300 bg-white px-1.5 py-0.5 font-mono text-[11px] hover:bg-sand-50">
                  {formatTimestamp(segment.start)}
                </button>
              )}
              {segment.start !== null && !canListen && <span className="font-mono text-[11px] text-ink-soft">{formatTimestamp(segment.start)}</span>}
              <strong className="text-xs text-lime-700">{(segment.speaker && speakerNames[segment.speaker]) || segment.speaker || 'Говорящий не определён'}</strong>
              {segment.speaker_uncertain && <span className="text-xs text-amber-700">Проверьте по аудио</span>}
            </div>
            <p>{segment.text}</p>
          </div>
        ))}
      </div>
    </aside>
  )
}
