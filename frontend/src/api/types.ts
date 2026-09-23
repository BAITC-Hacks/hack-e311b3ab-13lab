export type Role = 'admin' | 'secretary' | 'chair' | 'participant' | 'auditor'
export type GlobalPermission = 'users:manage' | 'users:directory' | 'audit:read' | 'meetings:create'
export type MeetingPermission =
  | 'view'
  | 'read'
  | 'listen'
  | 'edit'
  | 'people'
  | 'approve'
  | 'reopen'
  | 'track'
  | 'export'
  | 'export_raw'
  | 'retry'
  | 'delete'
export type MeetingStatus = 'live' | 'queued' | 'transcribing' | 'diarizing' | 'analyzing' | 'ready' | 'approved' | 'failed'
export type ActionStatus = 'open' | 'in_progress' | 'done'
export type ExportFormat = 'docx' | 'md' | 'pdf' | 'json'

export interface User {
  id: string
  email: string
  name: string
  role: Role
  role_label: string
  active: boolean
  created_at: string
  pending: boolean
  last_login_at: string | null
  permissions: GlobalPermission[]
}

export interface DirectoryUser {
  id: string
  name: string
  role: Role
  role_label: string
}

export interface Action {
  id: string | null
  title: string
  owner: string | null
  deadline_text: string | null
  due_date: string | null
  evidence: string
  segment_ids: string[]
  status: ActionStatus
  needs_review: boolean
  assignee_id: string | null
  owner_evidence?: string | null
  owner_uncertain?: boolean
  issued_by?: string | null
  issued_by_evidence?: string | null
  deliverable?: string | null
  deliverable_evidence?: string | null
  condition?: string | null
  condition_evidence?: string | null
  deadline_resolution?: 'unspecified' | 'resolved' | 'ambiguous' | 'event' | 'conflict' | 'uncertain' | 'confirmed'
  deadline_alternatives?: Array<{ text: string; segment_id: string }>
  review_questions?: string[]
}

export interface Analysis {
  summary: string
  decisions: string[]
  actions: Action[]
  warnings: string[]
  numeric_fragments?: Array<{ segment_id: string; text: string; included: boolean }>
  corrections?: Array<{ original: string; suggestion: string; reason: string }>
}

export interface Segment {
  id: string
  text: string
  start: number | null
  end: number | null
  speaker: string | null
  speaker_uncertain?: boolean
}

export interface SourceNote {
  kind: 'correction' | 'supplement' | 'speaker' | 'owner' | 'uncertain'
  segment_id: string
  original: string
  text: string
  action_id: string | null
  audio_checked: boolean
}

export interface SourceReview {
  terms: string[]
  notes: SourceNote[]
}

export interface Approval {
  version: number
  approved_at: string
  approved_by: string
  formats: Array<'docx' | 'pdf'>
}

export interface MeetingSummary {
  id: string
  title: string
  meeting_date: string
  status: MeetingStatus
  created_at: string
  permissions: MeetingPermission[]
}

export interface Meeting extends MeetingSummary {
  updated_at: string
  version: number
  error: string | null
  created_by: string | null
  chair_id: string | null
  participant_ids: string[]
  approved_at: string | null
  approved_by: string | null
  people: Record<string, string>
  approvals: Approval[]
  transcript?: string
  segments?: Segment[]
  analysis?: Analysis | null
  speaker_names?: Record<string, string>
  source_review?: SourceReview | null
  warnings?: string[]
  source?: MeetingSource
  live?: LiveInfo | null
  participants_seen?: Array<{ platform_id: string; name: string }>
}

export type Platform = 'google_meet' | 'teams' | 'zoom' | 'browser' | 'room'

export interface MeetingSource {
  type: 'upload' | 'tab' | 'bot'
  platform?: Platform
}

export interface LiveInfo {
  status: string
  detail?: string
  connector: 'tab' | 'bot'
  platform: Platform
  started_at: string
  ended_at?: string
  duration_seconds?: number
  failed_windows?: number
  bot_name?: string | null
}

export type LiveEvent =
  | { type: 'snapshot'; meeting: Meeting }
  | { type: 'segments'; segments: Segment[]; lag_seconds?: number }
  | { type: 'status'; status: string; detail?: string }
  | { type: 'participants'; participants: Array<{ platform_id: string; name: string }>; present: string[] }
  | { type: 'speaker'; name: string; platform_id: string; at: number }
  | { type: 'warning'; message: string }
  | { type: 'finished'; status: MeetingStatus }
  | { type: 'ping' }

export interface MyAction {
  meeting_id: string
  meeting_title: string
  meeting_date: string
  action: Action
}

export interface AuditEntry {
  id: number
  at: string
  user_id: string | null
  user_email: string | null
  action: string
  meeting_id: string | null
  detail: Record<string, unknown>
}

export interface Health {
  status: string
  provider_configured: boolean
  diarization_configured: boolean
  pdf_configured: boolean
  bot_configured?: boolean
  live_max_sessions?: number
}

export type RegistrationMode = 'approval' | 'open' | 'closed'

export type RegistrationResponse = { status: 'pending' } | { status: 'active'; token: string; expires_at: number; user: User }

export interface AdminMetrics {
  timezone: string
  daily_uploads: Array<{ date: string; count: number }>
  actions: { total: number; open: number; in_progress: number; done: number; needs_review: number }
}

export interface AdminOverview {
  metrics?: AdminMetrics
  users: { total: number; active: number; pending: number; disabled: number; by_role: Record<Role, number> }
  meetings: { total: number; by_status: Partial<Record<MeetingStatus, number>> }
  system: {
    database: string
    storage: string
    provider_configured: boolean
    pdf_configured: boolean
    diarization_configured: boolean
    registration_mode: RegistrationMode
    migrations: Array<{ id: string; applied_at: string }>
  }
  pending_registrations: User[]
  recent_activity: AuditEntry[]
}

export interface LoginResponse {
  token: string
  expires_at: number
  user: User
}
