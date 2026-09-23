import { useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Bot, Mic, MonitorUp, Radio } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { sendJson } from '../../api/client'
import { queryKeys, useHealth } from '../../api/queries'
import type { Meeting } from '../../api/types'
import { useToast } from '../../components/toast-context'
import { Button, Card, Field, Input, Notice, PageHeader } from '../../components/ui'
import { todayISO } from '../../lib/format'
import { PLATFORM_LABELS } from '../../lib/labels'
import { detectPlatform } from '../../lib/platform'
import { CaptureError, pickMeetingTab, pickMicrophone, tabCapture } from '../../live/capture'

type Mode = 'bot' | 'tab' | 'mic'

export function LiveStartPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const health = useHealth()
  const botReady = Boolean(health.data?.bot_configured)
  const [mode, setMode] = useState<Mode>('tab')
  const [title, setTitle] = useState('')
  const [meetingDate, setMeetingDate] = useState(todayISO())
  const [url, setUrl] = useState('')
  const [consent, setConsent] = useState(false)
  const [withMic, setWithMic] = useState(true)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const platform = url ? detectPlatform(url) : null

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setPending(true)
    let streams: MediaStream[] = []
    try {
      if (mode === 'tab') streams = await pickMeetingTab(withMic)
      if (mode === 'mic') streams = await pickMicrophone()
      const meeting = await sendJson<Meeting>('/api/live', 'POST', {
        title,
        meeting_date: meetingDate,
        recording_consent: consent,
        source: mode === 'bot' ? 'bot' : 'tab',
        meeting_url: mode === 'mic' ? null : url || null,
        platform: mode === 'mic' ? 'room' : null,
      })
      if (mode !== 'bot') await tabCapture.start(meeting.id, streams, mode === 'mic' || withMic)
      queryClient.setQueryData(queryKeys.meeting(meeting.id), meeting)
      void queryClient.invalidateQueries({ queryKey: queryKeys.meetings })
      notify(mode === 'bot' ? 'Бот подключается к совещанию' : mode === 'mic' ? 'Запись с микрофона началась' : 'Запись вкладки началась')
      navigate(`/meetings/${meeting.id}`)
    } catch (failure) {
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      setError(failure instanceof CaptureError || failure instanceof Error ? failure.message : 'Не удалось начать сессию')
    } finally {
      setPending(false)
    }
  }

  const tabs: Array<{ id: Mode; label: string; icon: typeof Bot; hint: string }> = [
    { id: 'bot', label: 'Пригласить бота', icon: Bot, hint: 'Бот входит в Google Meet, Teams или Zoom как участник' },
    { id: 'tab', label: 'Захватить вкладку', icon: MonitorUp, hint: 'Звук совещания, открытого в этом браузере' },
    { id: 'mic', label: 'Микрофон в переговорной', icon: Mic, hint: 'Очная встреча: запись с микрофона этого компьютера' },
  ]

  return (
    <>
      <PageHeader eyebrow="Онлайн-совещание" title="Подключить ИИ-секретаря">
        Расшифровка идёт во время встречи. После завершения протокол готовится как для загруженной записи.
      </PageHeader>
      <Card className="max-w-3xl p-6 sm:p-8">
        <div className="grid gap-3 sm:grid-cols-3" role="tablist" aria-label="Источник звука">
          {tabs.map(({ id, label, icon: Icon, hint }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mode === id}
              onClick={() => setMode(id)}
              className={clsx('flex items-start gap-3 rounded-xl border p-4 text-left transition-colors', mode === id ? 'border-forest-700 bg-lime-100' : 'border-sand-200 hover:bg-sand-50')}
            >
              <Icon className="mt-0.5 size-5 shrink-0 text-forest-700" aria-hidden />
              <span>
                <span className="block font-semibold">{label}</span>
                <span className="text-xs text-ink-muted">{hint}</span>
              </span>
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="mt-6 space-y-5">
          <div className="grid gap-5 sm:grid-cols-[2fr_1fr]">
            <Field label="Название встречи">
              <Input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Еженедельная планёрка" />
            </Field>
            <Field label="Дата встречи">
              <Input type="date" required value={meetingDate} onChange={(event) => setMeetingDate(event.target.value)} />
            </Field>
          </div>
          {mode !== 'mic' && <Field label="Ссылка на совещание" hint={platform ? `Платформа: ${PLATFORM_LABELS[platform]}` : mode === 'bot' ? 'Google Meet, Microsoft Teams или Zoom' : 'Необязательно: поможет отметить платформу в протоколе'}>
            <Input type="url" required={mode === 'bot'} value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://meet.google.com/abc-defg-hij" />
          </Field>}
          {mode === 'bot' && url && !platform && <Notice tone="error">Ссылка не похожа на Google Meet, Teams или Zoom. Бот открывает только такие адреса.</Notice>}
          {mode === 'bot' && !botReady && <Notice>Сервис бота не настроен на сервере. Используйте захват вкладки или задайте BOT_SERVICE_URL и BOT_TOKEN.</Notice>}
          {mode === 'bot' && botReady && <Notice tone="info">Бот попросит войти во встречу: впустите его из зала ожидания. Он напишет в чат, что ведётся запись.</Notice>}
          {mode === 'tab' && (
            <Notice tone="info" title="Как захватить вкладку">
              Откройте совещание в этом браузере. После нажатия кнопки выберите вкладку с совещанием и включите «Поделиться звуком вкладки». Ваш голос не звучит во вкладке, поэтому оставьте микрофон включённым.
            </Notice>
          )}
          {mode === 'mic' && <Notice tone="info">Поставьте компьютер ближе к центру стола. Браузер попросит доступ к микрофону; страницу во время встречи не закрывайте.</Notice>}
          {mode === 'tab' && (
            <label className="flex items-center gap-3 text-sm">
              <input type="checkbox" checked={withMic} onChange={(event) => setWithMic(event.target.checked)} className="size-4 accent-forest-700" />
              Добавить мой микрофон
            </label>
          )}
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-0.5 size-4 accent-forest-700" />
            Участники уведомлены о записи и расшифровке средствами ИИ.
          </label>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" variant="primary" loading={pending} disabled={!consent || (mode === 'bot' && (!platform || !botReady))} icon={<Radio className="size-4" />}>
            {mode === 'bot' ? 'Отправить бота' : mode === 'mic' ? 'Начать запись с микрофона' : 'Начать запись вкладки'}
          </Button>
        </form>
      </Card>
    </>
  )
}
