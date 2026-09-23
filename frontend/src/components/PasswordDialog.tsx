import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { sendJson, setToken } from '../api/client'
import { Dialog } from './Dialog'
import { useToast } from './toast-context'
import { Button, Field, Input, Notice } from './ui'

export function PasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notify } = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => sendJson<{ token: string }>('/api/auth/password', 'POST', { current_password: current, new_password: next }),
    onSuccess: (response) => {
      setToken(response.token)
      notify('Пароль изменён. Другие сессии завершены.')
      close()
    },
    onError: (failure: Error) => setError(failure.message),
  })

  function close() {
    setCurrent('')
    setNext('')
    setConfirm('')
    setError('')
    onClose()
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (next !== confirm) return setError('Новые пароли не совпадают')
    setError('')
    mutation.mutate()
  }

  return (
    <Dialog open={open} onClose={close} title="Смена пароля">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Текущий пароль">
          <Input type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} />
        </Field>
        <Field label="Новый пароль" hint="Не короче 10 символов">
          <Input type="password" autoComplete="new-password" required minLength={10} value={next} onChange={(event) => setNext(event.target.value)} />
        </Field>
        <Field label="Повторите новый пароль">
          <Input type="password" autoComplete="new-password" required minLength={10} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </Field>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="flex justify-end gap-2 pt-2">
          <Button onClick={close}>Отмена</Button>
          <Button type="submit" variant="primary" loading={mutation.isPending}>
            Сохранить
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
