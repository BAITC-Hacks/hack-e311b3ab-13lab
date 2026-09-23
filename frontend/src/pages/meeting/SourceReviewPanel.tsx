import { useState } from 'react'
import { sendJson } from '../../api/client'
import type { Action, Segment, SourceNote, SourceReview } from '../../api/types'
import { Button, Field, Input, Textarea } from '../../components/ui'

const labels: Record<SourceNote['kind'], string> = {
  correction: 'Исправление ASR', supplement: 'Дополнение по аудио', speaker: 'Говорящий этой реплики', owner: 'Исполнитель поручения', uncertain: 'Нужно уточнить',
}
interface Suggestion { segment_id: string; original: string; candidates: string[] }
interface Props {
  meetingId: string
  segments: Segment[]
  actions: Action[]
  value: SourceReview
  editable: boolean
  onChange: (value: SourceReview) => void
  onOwner: (actionId: string, owner: string) => void
  onLocate: (segmentId: string) => void
}
const emptyNote = (): SourceNote => ({ kind: 'correction', segment_id: '', original: '', text: '', action_id: null, audio_checked: false })

export function SourceReviewPanel({ meetingId, segments, actions, value, editable, onChange, onOwner, onLocate }: Props) {
  const [note, setNote] = useState(emptyNote)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  function patch(update: Partial<SourceNote>) {
    setNote((current) => ({ ...current, ...update, audio_checked: false }))
  }
  async function suggest() {
    setBusy(true)
    setMessage('')
    try {
      const result = await sendJson<Suggestion[]>(`/api/meetings/${meetingId}/source-suggestions`, 'POST', { terms: value.terms.map((term) => term.trim()).filter(Boolean) })
      setSuggestions(result)
      setMessage(result.length ? 'Это гипотезы, не автоматические исправления.' : 'Похожих слов не найдено. Сверьте спорные места вручную.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Ошибка поиска')
    } finally {
      setBusy(false)
    }
  }
  function add() {
    const segment = segments.find((item) => item.id === note.segment_id)
    if (!segment || !note.text.trim()) return setMessage('Выберите реплику и заполните результат проверки.')
    if (note.kind !== 'uncertain' && !note.audio_checked) return setMessage('Сначала прослушайте и подтвердите аудио.')
    if (note.kind === 'correction' && (!note.original.trim() || !segment.text.includes(note.original))) return setMessage('Исходный фрагмент должен точно совпадать с ASR.')
    if (note.kind === 'owner' && !note.action_id) return setMessage('Выберите поручение.')
    if (value.notes.some((item) => item.kind === note.kind && ((note.kind === 'speaker' && item.segment_id === note.segment_id) || (note.kind === 'owner' && item.action_id === note.action_id)))) return setMessage('Сначала удалите предыдущее подтверждение этого голоса или исполнителя.')
    const saved = { ...note, text: note.text.trim() }
    onChange({ ...value, notes: [...value.notes, saved] })
    if (saved.kind === 'owner' && saved.action_id) onOwner(saved.action_id, saved.text)
    setNote(emptyNote())
    setMessage('Добавлено в черновик. Нажмите «Сохранить».')
  }
  return <section className="space-y-3 rounded-xl border border-sand-300 p-4" aria-label="Сверка с аудио">
    <h2 className="text-lg font-semibold">Сверка с аудио</h2>
    <p className="text-sm text-ink-muted">Исходный ASR и цитаты не меняются. Дополнения — ручные записи, не вывод модели. Если фрагмент неразборчив, оставьте «Нужно уточнить». Голос не определяет исполнителя автоматически.</p>
    {value.notes.map((item, index) => <div key={index} className="rounded-lg bg-sand-100 p-3 text-sm">
      <strong>{labels[item.kind]}</strong> · <button type="button" className="underline" onClick={() => onLocate(item.segment_id)}>{item.segment_id}: слушать</button>
      <p>{item.original && `«${item.original}» → `}{item.text}</p>
      {item.action_id && <p>Поручение: {actions.find((action) => action.id === item.action_id)?.title ?? item.action_id}</p>}
      <p>{item.audio_checked ? 'Подтверждено пользователем по аудио' : 'Не подтверждено'}</p>
      {editable && <button type="button" className="underline" onClick={() => onChange({ ...value, notes: value.notes.filter((_, position) => position !== index) })}>Удалить отметку {index + 1}</button>}
    </div>)}
    {editable && <>
      <Field label="Словарь: ФИО, регионы, термины (по одному на строку)">
        <Textarea rows={3} value={value.terms.join('\n')} onChange={(event) => onChange({ ...value, terms: event.target.value.split('\n') })} />
      </Field>
      <Button onClick={() => void suggest()} loading={busy}>Найти похожие слова</Button>
      {suggestions.map((suggestion, index) => <div key={index} className="text-sm">
        {suggestion.segment_id}: «{suggestion.original}» → {suggestion.candidates.map((candidate) => <button key={candidate} type="button" className="m-1 underline" onClick={() => setNote({ ...emptyNote(), segment_id: suggestion.segment_id, original: suggestion.original, text: candidate })}>{candidate}</button>)}
      </div>)}
      <Field label="Тип проверки"><select className="w-full rounded border p-2" value={note.kind} onChange={(event) => patch({ kind: event.target.value as SourceNote['kind'], original: '', action_id: null, text: '' })}>
        {Object.entries(labels).map(([kind, label]) => <option key={kind} value={kind}>{label}</option>)}
      </select></Field>
      <Field label="Реплика-источник"><select className="w-full rounded border p-2" value={note.segment_id} onChange={(event) => patch({ segment_id: event.target.value })}>
        <option value="">Выберите реплику</option>{segments.map((segment) => <option key={segment.id} value={segment.id}>{segment.id}: {segment.text.slice(0, 90)}</option>)}
      </select></Field>
      {note.segment_id && <Button onClick={() => onLocate(note.segment_id)}>Открыть фрагмент в аудиоплеере</Button>}
      {note.kind === 'owner' && <Field label="Поручение для подтверждения"><select className="w-full rounded border p-2" value={note.action_id ?? ''} onChange={(event) => patch({ action_id: event.target.value || null })}>
        <option value="">Выберите поручение</option>{actions.filter((action) => action.id).map((action) => <option key={action.id} value={action.id!}>{action.title}</option>)}
      </select></Field>}
      {note.kind === 'correction' && <Field label="Исходный фрагмент ASR"><Input value={note.original} onChange={(event) => patch({ original: event.target.value })} /></Field>}
      <Field label="Результат проверки / вопрос"><Textarea rows={2} maxLength={['speaker', 'owner'].includes(note.kind) ? 200 : 4000} value={note.text} onChange={(event) => patch({ text: event.target.value })} /></Field>
      {note.kind !== 'uncertain' && <label className="flex gap-2 text-sm"><input type="checkbox" checked={note.audio_checked} onChange={(event) => setNote((current) => ({ ...current, audio_checked: event.target.checked }))} />Я прослушал(а) этот фрагмент и подтверждаю запись</label>}
      <Button onClick={add} disabled={value.notes.length >= 200}>Добавить отметку</Button>
      {message && <p role="status" className="text-sm">{message}</p>}
    </>}
  </section>
}
