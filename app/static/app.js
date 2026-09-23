const $ = (selector) => document.querySelector(selector);
let selected = null;
let token = sessionStorage.getItem('qorytyn-token') || '';
let audioURL = null;
let poll = null;
const labels = {queued:'В очереди', transcribing:'Распознаём речь', diarizing:'Обрабатываем говорящих', analyzing:'Выделяем поручения', ready:'Готов к проверке', failed:'Ошибка обработки'};
const text = (tag, value, className) => { const element = document.createElement(tag); element.textContent = value; if (className) element.className = className; return element; };
function notify(message) { $('#message').textContent = message; $('#message').hidden = !message; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers:{...options.headers, ...(token ? {Authorization:`Bearer ${token}`} : {})}});
  if (response.status === 401) { if (!$('#auth').open) $('#auth').showModal(); throw new Error('Введите токен доступа'); }
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === 'string' ? body.detail : `Ошибка запроса (${response.status})`); }
  return response;
}
async function listMeetings() {
  const meetings = await (await api('/api/meetings')).json();
  $('#meetings').replaceChildren(...meetings.map(meeting => {
    const button = text('button', `${meeting.title} · ${labels[meeting.status]}`);
    if (selected?.id === meeting.id) button.className = 'active';
    button.onclick = () => openMeeting(meeting.id).catch(error => notify(error.message));
    return button;
  }));
}
function field(label, value, onChange, type = 'text') {
  const container = text('label', label);
  const input = document.createElement('input'); input.type = type; input.value = value || '';
  input.oninput = () => onChange(input.value || null); container.append(input); return container;
}
function renderActions() {
  $('#actions').replaceChildren(...selected.analysis.actions.map((action, index) => {
    const card = document.createElement('article'); card.className = 'action';
    card.append(text('small', `ПОРУЧЕНИЕ ${String(index + 1).padStart(2,'0')}`));
    const title = document.createElement('textarea'); title.rows = 2; title.value = action.title; title.setAttribute('aria-label','Суть поручения'); title.oninput = () => action.title = title.value; card.append(title);
    const grid = document.createElement('div'); grid.className = 'grid';
    grid.append(field('Ответственный', action.owner, value => action.owner = value), field('Дата исполнения', action.due_date, value => action.due_date = value, 'date'));
    card.append(grid, text('small', `Срок в речи: ${action.deadline_text || 'Не указан'}`), text('blockquote', action.evidence));
    const source = text('button','Найти в транскрипте ↗'); source.onclick = () => {
      document.querySelectorAll('.segment').forEach(item => item.classList.remove('highlight'));
      const segment = selected.segments.find(item => action.segment_ids.includes(item.id));
      if (segment) { const element = document.getElementById(`segment-${segment.id}`); element.classList.add('highlight'); element.scrollIntoView({behavior:'smooth',block:'center'}); if (segment.start !== null) $('#player').currentTime = segment.start; }
      else notify('Для этой цитаты нет точной привязки ко времени. Проверьте полный транскрипт.');
    }; card.append(source);
    const status = document.createElement('select'); status.setAttribute('aria-label','Статус поручения');
    for (const [value, label] of [['open','Открыто'],['in_progress','В работе'],['done','Выполнено']]) { const option = text('option', label); option.value = value; status.append(option); }
    status.value = action.status; status.onchange = () => { action.status = status.value; renderStats(); }; card.append(status);
    const review = text('label','Проверено секретарём'); review.className = 'consent'; const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = !action.needs_review; checkbox.onchange = () => { action.needs_review = !checkbox.checked; renderStats(); }; review.prepend(checkbox); card.append(review);
    return card;
  }));
}
function renderStats() {
  const actions = selected.analysis.actions;
  const today = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Almaty',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const items = [[actions.length,'Поручений'],[actions.filter(item => item.needs_review).length,'Требуют проверки'],[actions.filter(item => item.due_date && item.due_date < today && item.status !== 'done').length,'Просрочено']];
  $('#stats').replaceChildren(...items.map(([value,label]) => { const card = document.createElement('article'); card.append(text('b',value),text('span',label)); return card; }));
}
async function openMeeting(id) {
  clearTimeout(poll); notify('');
  selected = await (await api(`/api/meetings/${id}`)).json();
  $('#welcome').hidden = true; $('#detail').hidden = false;
  $('#title').textContent = selected.title; $('#meeting-date').textContent = selected.meeting_date;
  $('#status').textContent = labels[selected.status]; $('#progress').textContent = selected.error || (selected.status !== 'ready' ? 'Запись обрабатывается на сервере. Страницу можно закрыть.' : '');
  $('#retry').hidden = selected.status !== 'failed'; $('#result').hidden = selected.status !== 'ready';
  await listMeetings();
  if (!['ready','failed'].includes(selected.status)) { poll = setTimeout(() => openMeeting(id).catch(error => notify(error.message)),2500); return; }
  if (selected.status !== 'ready') return;
  $('#summary').value = selected.analysis.summary; $('#summary').oninput = () => selected.analysis.summary = $('#summary').value;
  $('#decisions').replaceChildren(...selected.analysis.decisions.map(value => text('li',value)));
  $('#warnings').replaceChildren(...selected.analysis.warnings.map(value => text('div',value,'warning')));
  renderActions(); renderStats();
  $('#speakers').replaceChildren(...[...new Set(selected.segments.map(item => item.speaker).filter(Boolean))].map(speaker => field(`Имя ${speaker}`,selected.speaker_names[speaker],value => selected.speaker_names[speaker] = value || speaker)));
  $('#transcript').replaceChildren(...selected.segments.map(segment => {
    const item = document.createElement('div'); item.className = 'segment'; item.id = `segment-${segment.id}`;
    if (segment.start !== null) { const button = text('button',`${Math.floor(segment.start/60)}:${String(Math.floor(segment.start%60)).padStart(2,'0')}`); button.onclick = () => { $('#player').currentTime = segment.start; $('#player').play().catch(() => {}); }; item.append(button); }
    item.append(text('strong',selected.speaker_names[segment.speaker] || segment.speaker || 'Говорящий не определён'),text('p',segment.text)); return item;
  }));
  if (audioURL) URL.revokeObjectURL(audioURL);
  audioURL = URL.createObjectURL(await (await api(`/api/meetings/${id}/audio`)).blob()); $('#player').src = audioURL;
}
$('#new').onclick = () => { clearTimeout(poll); selected = null; $('#player').pause(); $('#welcome').hidden = false; $('#detail').hidden = true; notify(''); };
$('#upload').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true; notify('');
  try { const data = new FormData(event.target); data.set('recording_consent','true'); const meeting = await (await api('/api/meetings',{method:'POST',body:data})).json(); await openMeeting(meeting.id); }
  catch(error) { notify(error.message); } finally { button.disabled = false; }
};
async function save() { selected = await (await api(`/api/meetings/${selected.id}/review`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:selected.version,analysis:selected.analysis,speaker_names:selected.speaker_names})})).json(); }
$('#save').onclick = async () => { try { await save(); notify('Изменения сохранены.'); } catch(error) { notify(error.message); } };
$('#retry').onclick = async () => { try { await api(`/api/meetings/${selected.id}/retry`,{method:'POST'}); await openMeeting(selected.id); } catch(error) { notify(error.message); } };
document.querySelectorAll('[data-export]').forEach(button => button.onclick = async () => {
  try { await save(); const format = button.dataset.export; const blob = await (await api(`/api/meetings/${selected.id}/export/${format}`)).blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `protocol-${selected.meeting_date}.${format}`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url),1000); }
  catch(error) { notify(error.message); }
});
$('#auth').addEventListener('close',() => { token = $('#token').value; sessionStorage.setItem('qorytyn-token',token); listMeetings().catch(error => notify(error.message)); });
$('[name="meeting_date"]').value = new Date().toLocaleDateString('en-CA');
api('/api/health').then(response => response.json()).then(health => { $('#health').textContent = health.provider_configured ? '● Сервис настроен' : '○ Настройте ключ на сервере'; }).catch(error => notify(error.message));
listMeetings().catch(error => notify(error.message));
