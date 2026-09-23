import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SourceReviewPanel } from './SourceReviewPanel'

function setup(editable = true) {
  const onChange = vi.fn()
  render(<SourceReviewPanel meetingId="m1" segments={[{ id: 's1', text: 'Ботагус доложит.', speaker: null, start: 0, end: 3 }]} actions={[]} value={{ terms: [], notes: [] }} editable={editable} onChange={onChange} onOwner={vi.fn()} onLocate={vi.fn()} />)
  return onChange
}

describe('SourceReviewPanel', () => {
  it('requires listening confirmation and invalidates it when text changes', async () => {
    const onChange = setup()
    await userEvent.selectOptions(screen.getByLabelText('Реплика-источник'), 's1')
    await userEvent.type(screen.getByLabelText('Исходный фрагмент ASR'), 'Ботагус')
    await userEvent.type(screen.getByLabelText('Результат проверки / вопрос'), 'Ботагоз')
    await userEvent.click(screen.getByRole('button', { name: 'Добавить отметку' }))
    expect(onChange).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.type(screen.getByLabelText('Результат проверки / вопрос'), 'а')
    expect(screen.getByRole('checkbox')).not.toBeChecked()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Добавить отметку' }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ notes: [expect.objectContaining({ original: 'Ботагус', text: 'Ботагоза', audio_checked: true })] }))
  })

  it('allows uncertainty without inventing a correction', async () => {
    const onChange = setup()
    await userEvent.selectOptions(screen.getByLabelText('Тип проверки'), 'uncertain')
    await userEvent.selectOptions(screen.getByLabelText('Реплика-источник'), 's1')
    await userEvent.type(screen.getByLabelText('Результат проверки / вопрос'), 'Имя неразборчиво')
    await userEvent.click(screen.getByRole('button', { name: 'Добавить отметку' }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ notes: [expect.objectContaining({ kind: 'uncertain', audio_checked: false })] }))
  })

  it('hides editing for readers', () => {
    setup(false)
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
