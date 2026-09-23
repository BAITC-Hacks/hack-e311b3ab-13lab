import { useState } from 'react'
import { ArrowDownToLine, ArrowUpRight, CheckCheck, ClipboardList, Clock3, FileCheck2, ShieldCheck, Users } from 'lucide-react'
import { Link } from 'react-router'
import type { AdminOverview, MeetingStatus } from '../../api/types'
import { STATUS_LABELS } from '../../lib/labels'

const COLORS: Record<MeetingStatus, string> = { approved: '#1b4a44', ready: '#bad98b', queued: '#c6d5e0', transcribing: '#8bafc3', diarizing: '#819db9', analyzing: '#6585a4', failed: '#cd8170' }
const STATUSES: MeetingStatus[] = ['approved', 'ready', 'queued', 'transcribing', 'diarizing', 'analyzing', 'failed']
const number = (value: number) => value.toLocaleString('ru-RU')
const percent = (value: number, total: number) => total ? Math.round(value / total * 100) : 0
const shortDate = (value: string) => new Date(`${value}T12:00:00Z`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: 'UTC' })

export function AdminMetrics({ data }: { data: AdminOverview }) {
  const [period, setPeriod] = useState<7 | 30>(7)
  const [focusedDate, setFocusedDate] = useState<string | null>(null)
  const statuses = data.meetings.by_status
  const approved = statuses.approved ?? 0
  const ready = statuses.ready ?? 0
  const processing = (statuses.queued ?? 0) + (statuses.transcribing ?? 0) + (statuses.diarizing ?? 0) + (statuses.analyzing ?? 0)
  const failed = statuses.failed ?? 0
  const actions = data.metrics?.actions
  const days = data.metrics?.daily_uploads.slice(-period) ?? []
  const selected = days.find(day => day.date === focusedDate)
  const total = days.reduce((sum, day) => sum + day.count, 0)
  const max = Math.max(1, ...days.map(day => day.count))
  const peak = days.reduce<typeof days[number] | undefined>((best, day) => !best || day.count > best.count ? day : best, undefined)
  const chartWidth = 640
  const step = days.length ? 580 / days.length : 1
  const segments = STATUSES.filter(status => (statuses[status] ?? 0) > 0).map(status => ({ status, count: statuses[status] ?? 0 }))
  const attention = ready + failed + data.users.pending
  const cards = [
    { label: 'Всего совещаний', value: number(data.meetings.total), caption: 'За всё время', icon: ClipboardList, accent: true },
    { label: 'Протоколов утверждено', value: number(approved), caption: data.meetings.total ? `${percent(approved, data.meetings.total)}% от всех совещаний` : 'Появятся после утверждения', icon: FileCheck2 },
    { label: 'Поручений выполнено', value: actions ? `${number(actions.done)} / ${number(actions.total)}` : '—', caption: 'В готовых и утверждённых протоколах', icon: CheckCheck },
    { label: 'Активных пользователей', value: number(data.users.active), caption: `${number(data.users.total)} аккаунтов · ${number(data.users.disabled)} отключено`, icon: Users },
  ]

  return <div className="admin-metrics">
    <section className="admin-pulse" aria-label="Оперативная сводка">
      <span className="admin-pulse-icon"><ShieldCheck size={21} /></span>
      <div><h2>{attention ? 'Рабочий процесс — под контролем' : 'Всё готово к следующей встрече'}</h2><p>{ready} на проверке <span>·</span> {processing} в обработке <span>·</span> {failed} с ошибкой</p></div>
      <span className="admin-live-label"><i /> Данные из системы</span>
    </section>
    <dl className="admin-kpis">{cards.map(({ label, value, caption, icon: Icon, accent }) => <div key={label} className={`admin-kpi${accent ? ' admin-kpi-accent' : ''}`}><dt>{label}<Icon size={19} /></dt><dd>{value}</dd><p>{caption}</p></div>)}</dl>

    <div className="admin-chart-grid">
      <section className="admin-panel admin-volume" aria-label="Динамика загрузок">
        <div className="admin-panel-heading"><div><p className="admin-overline">АКТИВНОСТЬ</p><h2>Поток совещаний</h2></div><div className="admin-period" aria-label="Период графика">{([7, 30] as const).map(value => <button key={value} type="button" aria-pressed={period === value} onClick={() => { setPeriod(value); setFocusedDate(null) }}>{value} дней</button>)}</div></div>
        {days.length ? <>
          <div className="admin-chart-summary"><strong>{number(total)}</strong><span>загружено за {period} дней<br /><small>По дате загрузки · Алматы (UTC+5)</small></span><ArrowDownToLine size={22} /></div>
          <div className="admin-chart-readout" aria-live="polite">{selected ? `${shortDate(selected.date)} — ${selected.count} совещаний` : total ? 'Наведите на столбец или выберите его клавишей Tab' : 'В этом периоде загрузок пока нет'}</div>
          <svg className="admin-bar-chart" viewBox={`0 0 ${chartWidth} 210`} role="group" aria-label={`Загрузки совещаний за ${period} дней`}>
            {[0, 1, 2].map(index => <g key={index}><line x1="40" x2="625" y1={30 + index * 70} y2={30 + index * 70} stroke="#e9ede5" strokeDasharray="3 5" /><text x="25" y={34 + index * 70} textAnchor="end" fill="#85917d" fontSize="10">{Math.ceil(max / 2) * (2 - index)}</text></g>)}
            {days.map((day, index) => { const height = day.count / (Math.ceil(max / 2) * 2) * 140; const x = 42 + index * step; return <g key={day.date} tabIndex={0} role="img" aria-label={`${shortDate(day.date)}: ${day.count} совещаний`} onFocus={() => setFocusedDate(day.date)} onBlur={() => setFocusedDate(null)} onMouseEnter={() => setFocusedDate(day.date)} onMouseLeave={() => setFocusedDate(null)} onClick={() => setFocusedDate(day.date)}>
              <rect x={x} y="25" width={step - 3} height="149" fill="transparent" />
              <rect x={x + step * .15} y={170 - Math.max(height, 2)} width={step * .65} height={Math.max(height, 2)} rx={period === 7 ? 5 : 2} fill={!day.count ? '#e8eee1' : selected?.date === day.date ? '#1b4a44' : '#afce88'} />
              {(period === 7 || index % 7 === 0 || index === days.length - 1) && <text x={x + step / 2} y="195" textAnchor="middle" fill="#7b8972" fontSize="10">{shortDate(day.date)}</text>}
            </g> })}
          </svg>
          <div className="admin-chart-footer"><span>Среднее за день <b>{(total / days.length).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</b></span><span>Пик загрузок <b>{total && peak ? `${peak.count} · ${shortDate(peak.date)}` : '—'}</b></span></div>
        </> : <p className="admin-no-data">Динамика пока недоступна. Обновите данные после подключения аналитики.</p>}
      </section>

      <section className="admin-panel" aria-label="Статусы совещаний">
        <div className="admin-panel-heading"><div><p className="admin-overline">ПРОТОКОЛЫ</p><h2>От записи к решению</h2></div><FileCheck2 size={20} /></div>
        <div className="admin-donut"><svg viewBox="0 0 200 200" role="img" aria-label={`${approved} утверждено из ${data.meetings.total} совещаний`}><circle cx="100" cy="100" r="75" fill="none" stroke="#f0f3eb" strokeWidth="17" />{segments.map((segment, index) => { const before = segments.slice(0, index).reduce((sum, item) => sum + item.count, 0); const fraction = segment.count / data.meetings.total * 100; return <circle key={segment.status} cx="100" cy="100" r="75" fill="none" stroke={COLORS[segment.status]} strokeWidth="17" pathLength="100" strokeDasharray={`${fraction} ${100 - fraction}`} strokeDashoffset={-before / data.meetings.total * 100} transform="rotate(-90 100 100)" /> })}<text x="100" y="97" textAnchor="middle" className="admin-donut-value">{data.meetings.total ? `${percent(approved, data.meetings.total)}%` : '—'}</text><text x="100" y="119" textAnchor="middle" className="admin-donut-caption">утверждено</text></svg></div>
        <ul className="admin-status-legend">{(segments.length ? segments : [{ status: 'ready' as const, count: 0 }]).map(({ status, count }) => <li key={status}><svg width="8" height="8" aria-hidden><circle cx="4" cy="4" r="4" fill={COLORS[status]} /></svg><span>{STATUS_LABELS[status]}</span><b>{number(count)}</b></li>)}</ul>
        <p className="admin-footnote">Текущее состояние · за всё время</p>
      </section>
    </div>

    <div className="admin-focus-grid">
      <section className="admin-panel" aria-label="Исполнение поручений"><div className="admin-panel-heading"><div><p className="admin-overline">РЕЗУЛЬТАТ ВСТРЕЧ</p><h2>Исполнение поручений</h2></div><CheckCheck size={21} /></div>
        {actions ? <><div className="admin-action-total"><strong>{percent(actions.done, actions.total)}<small>%</small></strong><span>{actions.done} из {actions.total} выполнено</span></div><progress className="admin-progress" value={actions.done} max={actions.total || 1} aria-label="Доля выполненных поручений" /><div className="admin-action-states"><div><b>{actions.open}</b><span>Открыто</span></div><div><b>{actions.in_progress}</b><span>В работе</span></div><div><b>{actions.done}</b><span>Выполнено</span></div></div><p className="admin-footnote">Готовые и утверждённые протоколы · без доступа к содержанию</p></> : <p className="admin-no-data">Статистика поручений пока недоступна.</p>}
      </section>
      <section className="admin-panel admin-attention" aria-label="Требует внимания"><div className="admin-panel-heading"><div><p className="admin-overline">СЛЕДУЮЩИЕ ШАГИ</p><h2>Требует внимания</h2></div><Clock3 size={21} /></div>
        <div className="admin-attention-row"><span className="admin-attention-number">{ready}</span><div><strong>Протоколы на проверке</strong><p>Секретарю нужно сверить результат</p></div></div>
        <div className="admin-attention-row"><span className={`admin-attention-number${failed ? ' has-errors' : ''}`}>{failed}</span><div><strong>Ошибки обработки</strong><p>{failed ? 'Нужна проверка и повторный запуск' : 'Ошибок обработки сейчас нет'}</p></div></div>
        <div className="admin-attention-row"><span className="admin-attention-number">{actions?.needs_review ?? '—'}</span><div><strong>Поручения для уточнения</strong><p>Исполнитель, срок или формулировка</p></div></div>
        <a className="admin-queue-link" href="#registration-queue">Заявки на доступ <b>{data.users.pending}</b><ArrowUpRight size={16} /></a>
      </section>
    </div>
    <div className="admin-section-title"><div><p className="admin-overline">УПРАВЛЕНИЕ</p><h2>Команда и инфраструктура</h2></div><Link to="/users">Пользователи <ArrowUpRight size={15} /></Link></div>
  </div>
}
