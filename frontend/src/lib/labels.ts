import type { ActionStatus, MeetingStatus, Role } from '../api/types'

export const ACTIVE_STATUSES: ReadonlySet<MeetingStatus> = new Set(['live', 'queued', 'transcribing', 'diarizing', 'analyzing'])
export const PROCESSING_STEPS: MeetingStatus[] = ['queued', 'transcribing', 'diarizing', 'analyzing']

export const STATUS_LABELS: Record<MeetingStatus, string> = {
  live: 'Онлайн-сессия',
  queued: 'В очереди',
  transcribing: 'Распознаём речь',
  diarizing: 'Обрабатываем говорящих',
  analyzing: 'Выделяем поручения',
  ready: 'На проверке',
  approved: 'Утверждён',
  failed: 'Ошибка обработки',
}

export const ACTION_STATUS_LABELS: Record<ActionStatus, string> = {
  open: 'Открыто',
  in_progress: 'В работе',
  done: 'Выполнено',
}

export const PLATFORM_LABELS: Record<string, string> = {
  google_meet: 'Google Meet',
  teams: 'Microsoft Teams',
  zoom: 'Zoom',
  browser: 'Вкладка браузера',
  room: 'Переговорная (микрофон)',
}

export const LIVE_STATUS_LABELS: Record<string, string> = {
  joining: 'Подключение',
  lobby: 'В зале ожидания: впустите бота',
  waiting_audio: 'Ожидание звука из вкладки',
  joined: 'Подключён',
  live: 'Идёт ИИ-расшифровка',
  ended: 'Совещание завершено',
  error: 'Ошибка подключения',
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Администратор',
  secretary: 'Секретарь',
  chair: 'Председатель',
  participant: 'Участник',
  auditor: 'Аудитор',
}

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  admin: 'Полный доступ: все совещания и протоколы, пользователи, роли и журнал.',
  secretary: 'Загрузка, проверка, утверждение и выгрузка всех протоколов.',
  chair: 'То же, что секретарь, но только для своих совещаний.',
  participant: 'Чтение утверждённых протоколов, где он указан участником.',
  auditor: 'Журнал действий и метаданные без содержания.',
}

export const AUDIT_LABELS: Record<string, string> = {
  login: 'Вход',
  login_failed: 'Неудачный вход',
  logout: 'Выход',
  password_changed: 'Смена пароля',
  user_created: 'Создан пользователь',
  user_updated: 'Изменён пользователь',
  meeting_created: 'Загружено совещание',
  meeting_retried: 'Повтор обработки',
  review_saved: 'Сохранены правки',
  people_updated: 'Изменены участники',
  action_status_changed: 'Статус поручения',
  meeting_approved: 'Протокол утверждён',
  meeting_reopened: 'Возвращён на доработку',
  meeting_exported: 'Выгрузка',
  approved_copy_downloaded: 'Скачана утверждённая копия',
  audio_opened: 'Прослушивание записи',
  meeting_deleted: 'Удалено совещание',
  user_registered: 'Регистрация',
  registration_approved: 'Заявка одобрена',
  registration_rejected: 'Заявка отклонена',
}

export type Tone = 'neutral' | 'progress' | 'review' | 'success' | 'danger'

export function statusTone(status: MeetingStatus): Tone {
  if (ACTIVE_STATUSES.has(status)) return 'progress'
  if (status === 'ready') return 'review'
  if (status === 'approved') return 'success'
  return 'danger'
}
