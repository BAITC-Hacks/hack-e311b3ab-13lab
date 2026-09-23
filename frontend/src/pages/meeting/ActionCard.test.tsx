import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Action } from '../../api/types'
import { ActionCard } from './ActionCard'

const action: Action = {
  id: 'a1',
  title: 'Подготовить отчёт',
  owner: 'Айжан',
  deadline_text: 'к пятнице',
  due_date: '2020-01-10',
  evidence: 'Айжан подготовит отчёт к пятнице.',
  segment_ids: ['s1'],
  status: 'open',
  needs_review: true,
  assignee_id: 'u2',
}

function renderCard(props: Partial<Parameters<typeof ActionCard>[0]> = {}) {
  const handlers = { onChange: vi.fn(), onStatusChange: vi.fn(), onLocate: vi.fn() }
  render(<ActionCard action={action} index={0} editable={false} canChangeStatus={false} directory={[]} people={{ u2: 'Айжан Серикова' }} {...handlers} {...props} />)
  return handlers
}

describe('ActionCard', () => {
  it('shows deliverables, conditions, and conflicting source deadlines', async () => {
    renderCard({ action: { ...action, deliverable: 'Отчёт по каждой площадке', condition: 'При повторном нарушении', deadline_resolution: 'conflict', deadline_alternatives: [{ text: 'две недели', segment_id: 's1' }, { text: 'десять дней', segment_id: 's2' }] } })
    await userEvent.click(screen.getByRole('button', { name: 'Раскрыть поручение 1' }))
    expect(screen.getByText(/Отчёт по каждой площадке/)).toBeInTheDocument()
    expect(screen.getByText(/При повторном нарушении/)).toBeInTheDocument()
    expect(screen.getByText(/Тип срока: противоречивый/)).toBeInTheDocument()
    expect(screen.getByText(/две недели \[s1\]/)).toBeInTheDocument()
    expect(screen.getByText(/десять дней \[s2\]/)).toBeInTheDocument()
  })
  it('is read-only for readers and shows the assigned person', () => {
    renderCard()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.getByText('Айжан Серикова')).toBeInTheDocument()
    expect(screen.getByText('Просрочено')).toBeInTheDocument()
  })

  it('lets an assignee change only the status', async () => {
    const { onStatusChange } = renderCard({ canChangeStatus: true })
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Статус поручения'), 'done')
    expect(onStatusChange).toHaveBeenCalledWith('done')
  })

  it('offers full editing to the secretary', async () => {
    const { onChange, onLocate } = renderCard({ editable: true, directory: [{ id: 'u2', name: 'Айжан Серикова', role: 'participant', role_label: 'Участник' }] })
    expect(screen.queryByLabelText('Исполнитель в системе')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Раскрыть поручение 1' }))
    await userEvent.click(screen.getByLabelText('Проверено секретарём'))
    expect(onChange).toHaveBeenCalledWith({ needs_review: false })
    await userEvent.click(screen.getByRole('button', { name: /Найти в транскрипте/ }))
    expect(onLocate).toHaveBeenCalled()
    expect(screen.getByLabelText('Исполнитель в системе')).toHaveValue('u2')
  })
})
