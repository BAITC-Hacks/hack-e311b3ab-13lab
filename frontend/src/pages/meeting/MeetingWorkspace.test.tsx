import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Meeting } from '../../api/types'
import { mockApi } from '../../test/fetch'
import { renderRoutes } from '../../test/render'
import { MeetingWorkspace } from './MeetingWorkspace'

const meeting: Meeting = {
  id:'demo', title:'Планирование', meeting_date:'2026-09-23', status:'ready', created_at:'', updated_at:'', version:1, error:null,
  created_by:null, chair_id:null, participant_ids:[], approved_at:null, approved_by:null, people:{}, approvals:[],
  permissions:['read','edit','people','approve','export'], speaker_names:{},
  segments:[{id:'s1',text:'Айжан, подготовьте план к пятнице.',start:12,end:15,speaker:'SPEAKER_01'}],
  analysis:{summary:'Обсудили запуск.',decisions:['Обновить план.'],warnings:['Уточните срок.'],actions:[
    {id:'a1',title:'Подготовить план',owner:'Айжан',deadline_text:'к пятнице',due_date:null,evidence:'Айжан, подготовьте план к пятнице.',segment_ids:['s1'],status:'open',needs_review:true,assignee_id:null},
    {id:'a2',title:'Согласовать бюджет',owner:'Тимур',deadline_text:null,due_date:null,evidence:'Согласуйте бюджет.',segment_ids:[],status:'done',needs_review:false,assignee_id:null},
  ]},
}

beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn()
  mockApi({'GET /api/health':{body:{provider_configured:true,pdf_configured:true}}})
})
function openWorkspace() { renderRoutes([{path:'/',element:<MeetingWorkspace meeting={meeting} />}],'/') }
function section(name: string) { return within(screen.getByRole('navigation',{name:'Содержание совещания'})).getByRole('button',{name}) }

describe('Meeting workspace navigation', () => {
  it('starts in reading mode and filters tasks without editing them', async () => {
    openWorkspace()
    expect(screen.getByText('Обсудили запуск.')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    await userEvent.click(section('Поручения 2'))
    expect(screen.getAllByRole('article')).toHaveLength(2)
    await userEvent.type(screen.getByLabelText('Поиск поручений'),'Айжан')
    expect(screen.getAllByRole('article')).toHaveLength(1)
    expect(screen.queryByLabelText('Суть поручения')).not.toBeInTheDocument()
  })

  it('keeps unsaved edits when opening the quote and prevents people changes from losing them', async () => {
    openWorkspace()
    await userEvent.click(section('Поручения 2'))
    await userEvent.click(screen.getByRole('button',{name:'Раскрыть поручение 1'}))
    await userEvent.clear(screen.getByLabelText('Ответственный из речи'))
    await userEvent.type(screen.getByLabelText('Ответственный из речи'),'Айжан Серикова')
    await userEvent.click(screen.getByRole('button',{name:'Найти в транскрипте'}))
    expect(screen.getByRole('heading',{name:'Запись и расшифровка'})).toBeInTheDocument()
    expect(document.getElementById('segment-s1')).toHaveTextContent('подготовьте план')
    await userEvent.click(section('Участники'))
    expect(screen.getByText(/Сначала сохраните правки/)).toBeInTheDocument()
    await userEvent.click(section('Поручения 2'))
    await userEvent.click(screen.getByRole('button',{name:'Раскрыть поручение 1'}))
    expect(screen.getByLabelText('Ответственный из речи')).toHaveValue('Айжан Серикова')
  })
})
