import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileAudio, Upload } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { request } from '../api/client'
import { queryKeys, useHealth } from '../api/queries'
import type { Meeting } from '../api/types'
import { useToast } from '../components/toast-context'
import { Button, Card, Field, Input, Notice, PageHeader } from '../components/ui'
import { todayISO } from '../lib/format'

const ACCEPT = '.mp3,.wav,.m4a,.ogg,.flac,.webm,.mp4'

export function NewMeetingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const health = useHealth()
  const [title, setTitle] = useState('')
  const [meetingDate, setMeetingDate] = useState(todayISO())
  const [file, setFile] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)

  const upload = useMutation({
    mutationFn: async () => {
      const form = new FormData()
      form.set('title', title)
      form.set('meeting_date', meetingDate)
      form.set('recording_consent', String(consent))
      form.set('audio', file as File)
      return (await request('/api/meetings', { method: 'POST', body: form })).json() as Promise<Meeting>
    },
    onSuccess: (meeting) => {
      queryClient.setQueryData(queryKeys.meeting(meeting.id), meeting)
      void queryClient.invalidateQueries({ queryKey: queryKeys.meetings })
      notify('Запись загружена. Обработка началась.')
      navigate(`/meetings/${meeting.id}`)
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (file && consent) upload.mutate()
  }

  return (
    <>
      <PageHeader eyebrow="Новое совещание" title="Загрузите запись">
        Получите протокол и поручения, которые можно проверить по исходной речи.
      </PageHeader>
      <Card className="max-w-3xl p-6 sm:p-8">
        <form onSubmit={submit} className="space-y-6">
          <div className="grid gap-5 sm:grid-cols-[2fr_1fr]">
            <Field label="Название встречи">
              <Input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Еженедельное совещание команды" />
            </Field>
            <Field label="Дата встречи" hint="Реальная дата, от неё считаются сроки">
              <Input type="date" required value={meetingDate} onChange={(event) => setMeetingDate(event.target.value)} />
            </Field>
          </div>
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-sand-300 bg-sand-50 px-6 py-10 text-center hover:border-forest-700">
            <FileAudio className="size-8 text-forest-700" aria-hidden />
            <span className="font-semibold">{file ? file.name : 'Выберите запись совещания'}</span>
            <span className="text-xs text-ink-soft">MP3, WAV, M4A, OGG, FLAC, WebM, MP4 · до 100 МБ по умолчанию</span>
            <input type="file" accept={ACCEPT} required className="sr-only" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-0.5 size-4 accent-forest-700" />
            Участники уведомлены о записи и обработке средствами ИИ.
          </label>
          {health.data && !health.data.provider_configured && <Notice>Ключ сервиса моделей не задан на сервере: обработка завершится ошибкой.</Notice>}
          {upload.isError && <Notice tone="error">{upload.error.message}</Notice>}
          <Button type="submit" variant="primary" loading={upload.isPending} disabled={!file || !consent} icon={<Upload className="size-4" />}>
            Создать протокол
          </Button>
        </form>
      </Card>
    </>
  )
}
