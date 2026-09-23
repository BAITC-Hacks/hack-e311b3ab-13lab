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
    await userEvent.click(screen.getByLabelText('Проверено секретарём'))
    expect(onChange).toHaveBeenCalledWith({ needs_review: false })
    await userEvent.click(screen.getByRole('button', { name: /Найти в транскрипте/ }))
    expect(onLocate).toHaveBeenCalled()
    expect(screen.getByLabelText('Исполнитель в системе')).toHaveValue('u2')
  })
})
