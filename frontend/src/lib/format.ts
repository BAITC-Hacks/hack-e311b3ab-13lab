import type { Action } from '../api/types'

const TIME_ZONE = 'Asia/Almaty'

/** Today's date in Almaty as YYYY-MM-DD, used to decide whether an action is overdue. */
export function todayISO(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
}

export function isOverdue(action: Pick<Action, 'due_date' | 'status'>, today: string = todayISO()): boolean {
  return Boolean(action.due_date && action.due_date < today && action.status !== 'done')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: TIME_ZONE }).format(date)
}

export function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(whole / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  const rest = String(whole % 60).padStart(2, '0')
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`
}

export function deadlineLabel(action: Pick<Action, 'due_date' | 'deadline_text'>): string {
  if (action.due_date) return formatDate(action.due_date)
  return action.deadline_text || 'Не указан'
}
