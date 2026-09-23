import { useState } from 'react'
import { ArrowRight, FileAudio, Video, Users, CalendarDays, FileText, Link2 } from 'lucide-react'

const connectors = [
  { id:'upload', name:'Аудиофайл', icon:FileAudio, short:'MP3 / WAV / M4A', logo:null, available:true, title:'Запись уже у вас? Начните с неё.', description:'Загрузите файл после входа. Приложение распознает речь, выделит поручения и подготовит протокол для проверки.', action:'Загрузить запись' },
  { id:'zoom', name:'Zoom', icon:Video, short:'Онлайн-встречи', logo:'/brand/integrations/zoom.svg', available:false, title:'Из Zoom — прямо к протоколу.', description:'Планируем подключение встреч по ссылке. Сейчас можно загрузить запись Zoom вручную; автоматическое подключение ещё недоступно.', action:'Пока можно загрузить запись' },
  { id:'teams', name:'Microsoft Teams', icon:Users, short:'Командные звонки', logo:'/brand/integrations/teams.svg', available:false, title:'Решения команды в одном месте.', description:'Коннектор Teams появится позже. Пока сохраните запись встречи и загрузите её как аудиофайл.', action:'Загрузить сохранённую запись' },
  { id:'meet', name:'Google Meet', icon:Video, short:'Рабочие созвоны', logo:'/brand/integrations/gmeet.svg', available:false, title:'Встреча в Meet. Поручения в HATTAMA.', description:'Планируем автоматический приём записи из Google Meet. На этом этапе работает ручная загрузка файла.', action:'Перейти к загрузке файла' },
  { id:'calendar', name:'Календарь', icon:CalendarDays, short:'Расписание встреч', logo:null, available:false, title:'Планирование без лишних переключений.', description:'Синхронизация календаря и напоминания — следующий этап. HATTAMA пока не читает ваше расписание и не подключает аккаунты.', action:'Открыть рабочее пространство' },
]

export function Integrations() {
  const [selected, setSelected] = useState('upload')
  const current = connectors.find((item) => item.id === selected) ?? connectors[0]
  const Icon = current.icon
  return <section id="integrations" className="integrations-section">
    <div className="section-heading"><p className="brand-eyebrow">ВАША ВСТРЕЧА. ПРИВЫЧНЫЙ СЕРВИС.</p><h2>Один протокол.<br className="sm:hidden" /> Разные источники.</h2><p>Начните с записи. Прямые подключения к сервисам встреч добавим следующим шагом.</p></div>
    <div className="connector-grid" aria-label="Источники совещаний">{connectors.map(({id,name,icon: ConnectorIcon,short,available,logo}) => <button key={id} type="button" aria-label={`${name} ${short} ${available ? 'Доступно' : 'Скоро'}`} aria-pressed={selected===id} onClick={() => setSelected(id)}><span className={`connector-symbol connector-${id}`}>{logo ? <img src={logo} alt="" width={32} height={32} /> : <ConnectorIcon size={26} strokeWidth={1.7} />}</span><strong>{name}</strong></button>)}</div>
    <p className="connector-availability">Загрузка файла доступна · Прямые подключения скоро</p>
    <div className="connector-detail" role="region" aria-label={`Подробнее: ${current.name}`}><div className="connector-detail-title">{current.logo ? <img src={current.logo} alt="" width={22} height={22} /> : <Icon size={22} />}<h3>{current.title}</h3></div><p>{current.description}</p><a href="#sign-in">{current.action}<ArrowRight size={15} /></a></div>
    <div className="output-path" aria-label="Что вы получите"><span><FileAudio size={16} /> Запись</span><ArrowRight size={15} /><span><FileText size={16} /> Протокол и поручения</span><ArrowRight size={15} /><span><Link2 size={16} /> Проверяемые цитаты</span><div className="output-formats"><b>DOCX</b><b>PDF</b><b>MD</b></div></div>
  </section>
}
