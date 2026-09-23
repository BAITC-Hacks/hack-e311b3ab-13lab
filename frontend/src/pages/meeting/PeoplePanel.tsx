import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { useState } from 'react'
import { sendJson } from '../../api/client'
import { queryKeys } from '../../api/queries'
import type { DirectoryUser, Meeting } from '../../api/types'
import { useToast } from '../../components/toast-context'
import { Button, Card, Field, Select } from '../../components/ui'

export function PeoplePanel({ meeting, directory, editable }: { meeting: Meeting; directory: DirectoryUser[]; editable: boolean }) {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [chairId, setChairId] = useState(meeting.chair_id ?? '')
  const [participants, setParticipants] = useState<string[]>(meeting.participant_ids)
  const dirty = chairId !== (meeting.chair_id ?? '') || participants.join() !== meeting.participant_ids.join()

  const save = useMutation({
    mutationFn: () => sendJson<Meeting>(`/api/meetings/${meeting.id}/people`, 'PUT', { chair_id: chairId || null, participant_ids: participants }),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.meeting(meeting.id), result)
      notify('Участники сохранены')
    },
    onError: (error: Error) => notify(error.message, 'error'),
  })

  const name = (id: string) => meeting.people[id] ?? directory.find((user) => user.id === id)?.name ?? 'Пользователь'

  if (!editable) {
    if (!meeting.chair_id && meeting.participant_ids.length === 0) return null
    return (
      <Card className="p-5">
        <h2 className="flex items-center gap-2 font-semibold">
          <Users className="size-4" aria-hidden /> Участники
        </h2>
        {meeting.chair_id && <p className="mt-2 text-sm">Председатель: {name(meeting.chair_id)}</p>}
        {meeting.participant_ids.length > 0 && <p className="mt-1 text-sm text-ink-muted">{meeting.participant_ids.map(name).join(', ')}</p>}
      </Card>
    )
  }

  const chairs = directory.filter((user) => user.role === 'chair')
  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 font-semibold">
        <Users className="size-4" aria-hidden /> Участники и доступ
      </h2>
      <p className="mt-1 text-xs text-ink-muted">Участники увидят протокол после утверждения. Председатель может править и утверждать этот протокол.</p>
      <Field label="Председатель" className="mt-4">
        <Select value={chairId} onChange={(event) => setChairId(event.target.value)}>
          <option value="">Не назначен</option>
          {chairs.map((user) => (
            <option key={user.id} value={user.id}>
              {user.name}
            </option>
          ))}
        </Select>
      </Field>
      <fieldset className="mt-4">
        <legend className="text-xs font-medium text-ink-muted">Участники</legend>
        <div className="mt-2 grid max-h-48 gap-1 overflow-y-auto sm:grid-cols-2">
          {directory.map((user) => (
            <label key={user.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-sand-50">
              <input
                type="checkbox"
                className="size-4 accent-forest-700"
                checked={participants.includes(user.id)}
                onChange={(event) => setParticipants((current) => (event.target.checked ? [...current, user.id] : current.filter((id) => id !== user.id)))}
              />
              <span className="truncate">{user.name}</span>
              <span className="ml-auto text-xs text-ink-soft">{user.role_label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <Button className="mt-4" size="sm" variant="primary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>
        Сохранить участников
      </Button>
    </Card>
  )
}
