import { useQuery } from '@tanstack/react-query'
import { ACTIVE_STATUSES } from '../lib/labels'
import { getJson } from './client'
import type { AdminOverview, AuditEntry, DirectoryUser, Health, Meeting, MeetingSummary, MyAction, RegistrationMode, User } from './types'

export const queryKeys = {
  health: ['health'] as const,
  meetings: ['meetings'] as const,
  meeting: (id: string) => ['meetings', id] as const,
  directory: ['directory'] as const,
  users: ['users'] as const,
  audit: (meetingId: string, limit: number) => ['audit', meetingId, limit] as const,
  tasks: ['tasks'] as const,
  registration: ['registration'] as const,
  adminOverview: ['admin', 'overview'] as const,
}

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: ({ signal }) => getJson<Health>('/api/health', signal), staleTime: 60_000 })
}

export function useMeetings() {
  return useQuery({
    queryKey: queryKeys.meetings,
    queryFn: ({ signal }) => getJson<MeetingSummary[]>('/api/meetings', signal),
    refetchInterval: (query) => (query.state.data?.some((meeting) => ACTIVE_STATUSES.has(meeting.status)) ? 4000 : false),
  })
}

export function useMeeting(id: string) {
  return useQuery({
    queryKey: queryKeys.meeting(id),
    queryFn: ({ signal }) => getJson<Meeting>(`/api/meetings/${encodeURIComponent(id)}`, signal),
    refetchInterval: (query) => (query.state.data && ACTIVE_STATUSES.has(query.state.data.status) ? 2500 : false),
  })
}

export function useDirectory(enabled: boolean) {
  return useQuery({ queryKey: queryKeys.directory, queryFn: ({ signal }) => getJson<DirectoryUser[]>('/api/users/directory', signal), enabled, staleTime: 60_000 })
}

export function useUsers() {
  return useQuery({ queryKey: queryKeys.users, queryFn: ({ signal }) => getJson<User[]>('/api/users', signal) })
}

export function useAudit(meetingId: string, limit: number) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (meetingId) params.set('meeting_id', meetingId)
  return useQuery({ queryKey: queryKeys.audit(meetingId, limit), queryFn: ({ signal }) => getJson<AuditEntry[]>(`/api/audit?${params}`, signal) })
}

export function useRegistrationMode() {
  return useQuery({ queryKey: queryKeys.registration, queryFn: async ({ signal }) => (await getJson<{ mode: RegistrationMode }>('/api/auth/registration', signal)).mode, staleTime: 300_000 })
}

export function useAdminOverview() {
  return useQuery({ queryKey: queryKeys.adminOverview, queryFn: ({ signal }) => getJson<AdminOverview>('/api/admin/overview', signal), refetchInterval: 30_000 })
}

export function useMyActions() {
  return useQuery({ queryKey: queryKeys.tasks, queryFn: ({ signal }) => getJson<MyAction[]>('/api/me/actions', signal) })
}
