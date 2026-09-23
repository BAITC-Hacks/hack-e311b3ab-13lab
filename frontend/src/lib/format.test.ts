import { describe, expect, it } from 'vitest'
import { deadlineLabel, formatTimestamp, isOverdue, todayISO } from './format'

describe('format helpers', () => {
  it('uses the Almaty calendar day', () => {
    expect(todayISO(new Date('2026-09-23T20:30:00Z'))).toBe('2026-09-24')
  })

  it('marks only unfinished past-due actions as overdue', () => {
    expect(isOverdue({ due_date: '2026-09-20', status: 'open' }, '2026-09-23')).toBe(true)
    expect(isOverdue({ due_date: '2026-09-20', status: 'done' }, '2026-09-23')).toBe(false)
    expect(isOverdue({ due_date: null, status: 'open' }, '2026-09-23')).toBe(false)
  })

  it('falls back to the spoken deadline', () => {
    expect(deadlineLabel({ due_date: null, deadline_text: 'после совещания' })).toBe('после совещания')
    expect(deadlineLabel({ due_date: null, deadline_text: null })).toBe('Не указан')
  })

  it('formats timestamps', () => {
    expect(formatTimestamp(65.9)).toBe('1:05')
    expect(formatTimestamp(3725)).toBe('1:02:05')
  })
})
