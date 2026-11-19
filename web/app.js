'use strict';
const $ = (id) => document.getElementById(id);
const state = {token: '', runs: [], projects: [], system: null, selected: null, events: [], cursor: 0, tab: 'timeline', patch: null, busy: false};
let requestKey = crypto.randomUUID();
let timer;
function node(tag, text, className) { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (className) element.className = className; return element; }
function empty(container, title, description) { container.replaceChildren(); const box = node('div', undefined, 'empty'); box.append(node('h3', title), node('p', description)); container.append(box); }
function badge(status) { return node('span', status, `status ${status}`); }
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(timer); timer = setTimeout(() => {$('toast').hidden = true;}, 4500); }
async function api(path, options = {}) {
  const response = await fetch('/api' + path, {...options, headers: {'Authorization': 'Bearer ' + state.token, 'Content-Type': 'application/json', ...(options.headers || {})}});
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail); } catch {}
    if (response.status === 401 && !$('login-dialog').open) lock();
    throw new Error(message);
  }
  return options.text ? response.text() : response.json();
}
function lock() {
  state.token = ''; state.runs = []; state.events = []; state.selected = null;
  $('connection-label').textContent = 'Authentication required'; $('connection-dot').classList.remove('online');
  $('run-detail').hidden = true; $('detail-empty').hidden = false;
  $('token').value = '';
  ['run-dialog', 'review-dialog'].forEach(id => $(id).close());
  if (!$('login-dialog').open) $('login-dialog').showModal();
  renderRuns();
}
function download(content, filename, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = node('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showPage(page) {
  document.querySelectorAll('.page').forEach(el => {el.hidden = el.id !== 'page-' + page;});
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  $('breadcrumb').textContent = {runs:'Runs', projects:'Projects', benchmarks:'Evaluation', system:'Runtime'}[page];
}
function renderRuns() {
  $('metric-total').textContent = state.token ? state.runs.length : '—';
  for (const [metric, status] of [['active','active'],['review','review'],['approved','approved']]) $('metric-' + metric).textContent = state.token ? state.runs.filter(r => r.status === status).length : '—';
  $('nav-count').textContent = state.token ? state.runs.length : '—';
  $('run-count').textContent = state.token ? `(${state.runs.length})` : '';
  const search = $('filter').value.toLowerCase(); const status = $('status-filter').value;
  const visible = state.runs.filter(r => (status === 'all' || r.status === status) && (r.request.title + r.id).toLowerCase().includes(search));
  const container = $('run-list'); container.replaceChildren();
  if (!visible.length) {empty(container, state.runs.length ? 'No matching runs.' : 'Your work starts with an issue.', state.runs.length ? 'Change the search or status filter.' : 'Queue an issue to begin. Run history contains actual backend records only.'); return;}
  for (const run of visible) {
    const row = node('button', undefined, 'run-row' + (state.selected === run.id ? ' selected' : ''));
    const top = node('div', undefined, 'row-top'); top.append(node('span', run.request.project, 'row-project'), badge(run.status));
    const bottom = node('div', undefined, 'row-bottom'); bottom.append(node('span', run.id.slice(0,8)), node('span', new Date(run.created*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})));
    row.append(top, node('h3', run.request.title), bottom); row.addEventListener('click', () => selectRun(run.id).catch(e => toast(e.message))); container.append(row);
  }
}
async function selectRun(identifier) {
  state.selected = identifier; state.events = []; state.cursor = 0; state.patch = null;
  state.tab = 'timeline'; setTabs(); renderRuns(); await updateDetail();
}
function setTabs() { document.querySelectorAll('.tab').forEach(button => {const active = button.dataset.tab === state.tab; button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active));}); }
async function updateDetail() {
  const identifier = state.selected;
  if (!identifier) return;
  const [run, events] = await Promise.all([api('/runs/' + identifier), api('/runs/' + identifier + '/events?cursor=' + state.cursor)]);
  if (state.selected !== identifier) return;
  const changed = state.current?.id !== run.id || state.current?.status !== run.status || events.length > 0;
  state.current = run;
  if (events.length) {state.events.push(...events); state.cursor = events.at(-1).sequence;}
  $('detail-empty').hidden = true; $('run-detail').hidden = false;
  $('detail-id').textContent = 'RUN / ' + run.id.slice(0,8);
  $('detail-title').textContent = run.request.title;
  $('detail-status').replaceWith(Object.assign(badge(run.status), {id:'detail-status'}));
  const metadata = [run.request.project, run.phase]; if (run.result?.duration !== undefined) metadata.push(run.result.duration + 's'); if (run.result?.tokens !== undefined) metadata.push(run.result.tokens + ' tokens');
  $('detail-meta').replaceChildren(...metadata.map(item => node('span', item)));
  $('run-error').hidden = !run.result?.reason; $('run-error').textContent = run.result?.reason || '';
  $('cancel-run').hidden = !['queued','active'].includes(run.status);
  $('download-patch').hidden = !['review','approved','rejected','failed'].includes(run.status);
  $('review-run').hidden = run.status !== 'review';
  if (changed) await renderDetail();
}
async function renderDetail() {
  const container = $('tab-content'); const run = state.current; const identifier = state.selected;
  if (!run) return;
  container.replaceChildren();
  if (state.tab === 'issue') {container.append(node('div', run.request.issue, 'issue-text')); return;}
  if (state.tab === 'patch') {
    try {
      const content = state.patch ?? await api('/runs/' + identifier + '/patch', {text:true});
      if (identifier !== state.selected || state.tab !== 'patch') return;
      state.patch = content;
      if (!content) {empty(container, 'No candidate patch.', 'This attempt did not produce an exportable patch.'); return;}
      const pre = node('pre', undefined, 'patch-code');
      for (const line of content.split('\n')) pre.append(node('span', line, 'patch-line ' + (line.startsWith('+') ? 'add' : line.startsWith('-') ? 'remove' : line.startsWith('@@') ? 'header' : '')));
      container.append(pre);
    } catch (e) {empty(container, 'Patch unavailable.', e.message);}
    return;
  }
  if (state.tab === 'tests') {
    const tests = state.events.filter(e => ['baseline','test','verification'].includes(e.kind));
    if (!tests.length) {empty(container, 'No test evidence yet.', 'Actual command output appears after the worker runs tests.'); return;}
    tests.forEach(event => {const block = node('section', undefined, 'test-block'); const heading = node('h3', event.kind); heading.append(badge(event.payload.code === 0 && !event.payload.timeout && !event.payload.overflow ? 'passed' : 'failed')); block.append(heading, node('pre', (event.payload.stdout || '') + (event.payload.stderr || ''))); container.append(block);});
    return;
  }
  if (!state.events.length) {empty(container, 'Waiting for events.', 'The worker will append its execution evidence here.'); return;}
  for (const event of state.events) {
    const item = node('article', undefined, 'event'); const heading = node('div', undefined, 'event-title');
    const label = event.kind === 'action' ? `Step ${event.payload.step} · ${event.payload.action.kind}` : event.kind.replaceAll('_',' ');
    heading.append(node('span', label), node('time', new Date(event.at*1000).toLocaleTimeString())); item.append(heading);
    const details = node('details'); if (['queued','claimed','source','failed','review'].includes(event.kind)) details.open = true;
    details.append(node('summary', 'Inspect evidence'), node('pre', JSON.stringify(event.payload,null,2))); item.append(details); container.append(item);
  }
}
function renderProjects() {
  const container = $('projects-grid'); container.replaceChildren(); $('project').replaceChildren();
  if (!state.projects.length) {empty(container, 'No registered repositories.', 'Add a project to the operator-managed projects.json and restart the service. Arbitrary filesystem paths are not accepted through the browser.'); $('new-run').disabled = true; return;}
  $('new-run').disabled = false;
  state.projects.forEach(project => {
    const card = node('article', undefined, 'project-card'); card.append(node('div', project.key.toUpperCase(), 'eyebrow'), node('h2', project.name));
    const dl = node('dl'); for (const [title,value] of [['Execution image',project.image],['Verification command',project.verify.join(' ')],['Protected paths',project.protected.join(', ') || 'None configured']]) {const dd = node('dd'); dd.append(node('code',value)); dl.append(node('dt',title),dd);} card.append(dl); container.append(card);
    const option = node('option',project.name); option.value = project.key; $('project').append(option);
  });
}
function renderSystem() {
  const info = state.system; if (!info) return;
  const container = $('system-grid'); container.replaceChildren();
  const cards = [['MODEL',info.model || 'Not configured','A running compatible endpoint is required for agent decisions.'],['EXECUTION',info.docker_cli ? 'Docker CLI detected' : 'Docker unavailable','Daemon and image readiness must also be verified.'],['DATABASE',info.database,'Durable run state, ownership leases, events and patch artifacts.'],['RUN BUDGET',info.limits.steps + ' actions',`${info.limits.seconds}s scheduling budget · ${info.limits.tokens.toLocaleString()} token ceiling`]];
  for (const [title,value,caption] of cards) {const card = node('article',undefined,'system-card'); card.append(node('div',title,'eyebrow'),node('h2',value),node('p',caption)); container.append(card);}
  const missing = []; if (!info.model) missing.push('model configuration'); if (!info.docker_cli) missing.push('Docker');
  $('runtime-banner').hidden = !missing.length;
  $('runtime-banner').textContent = missing.length ? `Runtime setup needed: ${missing.join(' and ')}. You can inspect the console and queue issues; autonomous execution needs these services.` : '';
}
function renderBenchmarks() {
  const container = $('benchmark-list'); container.replaceChildren();
  const attempts = state.runs.filter(run => run.request.benchmark_id);
  $('export-predictions').disabled = !attempts.some(r => !['queued','active'].includes(r.status));
  if (!attempts.length) {empty(container,'No benchmark attempts.','Supply an instance ID and base commit when creating a benchmark run. Official scores are not generated by this console.'); return;}
  const table = node('table'); const head = node('thead'); const header = node('tr'); ['INSTANCE','MODEL','LOCAL STATUS'].forEach(label => header.append(node('th',label))); head.append(header); table.append(head);
  const body = node('tbody'); attempts.forEach(run => {const row = node('tr'); const status = node('td'); status.append(badge(run.status)); row.append(node('td',run.request.benchmark_id),node('td',run.result?.model || state.system?.model || 'Unconfigured'),status); body.append(row);}); table.append(body); container.append(table);
}
async function refresh() {
  if (!state.token || state.busy) return;
  state.busy = true;
  try {state.runs = await api('/runs'); renderRuns(); renderBenchmarks(); await updateDetail(); $('connection-label').textContent = 'Connected · live updates'; $('connection-dot').classList.add('online');}
  catch (error) {$('connection-label').textContent = 'Connection interrupted'; $('connection-dot').classList.remove('online'); toast(error.message);}
  finally {state.busy = false;}
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); state.token = $('token').value; const button = event.submitter; button.disabled = true;
  try {const [system,projects] = await Promise.all([api('/system'),api('/projects')]); state.system = system; state.projects = projects; renderSystem(); renderProjects(); $('login-error').textContent = ''; $('token').value = ''; $('login-dialog').close(); await refresh();}
  catch (error) {state.token = ''; $('login-error').textContent = error.message;}
  finally {button.disabled = false;}
});
$('login-dialog').addEventListener('cancel', event => event.preventDefault());
$('logout').addEventListener('click', lock);
document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => showPage(button.dataset.page)));
document.querySelectorAll('.close-dialog').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {state.tab = button.dataset.tab; setTabs(); renderDetail().catch(e => toast(e.message));}));
$('filter').addEventListener('input',renderRuns); $('status-filter').addEventListener('change',renderRuns);
$('new-run').addEventListener('click', () => {$('submit-error').textContent = ''; $('run-dialog').showModal();});
$('run-form').addEventListener('input', () => {requestKey = crypto.randomUUID();});
$('run-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  const payload = {project:$('project').value,title:$('title').value,issue:$('issue').value,commit:$('commit').value || null,benchmark_id:$('benchmark-id').value || null};
  try {const result = await api('/runs',{method:'POST',headers:{'Idempotency-Key':requestKey},body:JSON.stringify(payload)}); $('run-dialog').close(); $('run-form').reset(); requestKey = crypto.randomUUID(); await refresh(); await selectRun(result.id); toast('Run queued. Waiting for an execution worker.');}
  catch (error) {$('submit-error').textContent = error.message;}
  finally {button.disabled = false;}
});
$('cancel-run').addEventListener('click',async () => {try {await api('/runs/'+state.selected+'/cancel',{method:'POST'}); await refresh(); toast('Cancellation recorded. In-flight operations may take time to stop.');} catch (e) {toast(e.message);}});
$('download-patch').addEventListener('click',async () => {try {download(await api('/runs/'+state.selected+'/patch',{text:true}),state.selected+'.patch');} catch(e) {toast(e.message);}});
$('review-run').addEventListener('click', () => {$('review-error').textContent = ''; $('review-dialog').showModal();});
$('review-form').addEventListener('submit',async event => {event.preventDefault(); event.submitter.disabled = true; try {await api('/runs/'+state.selected+'/review',{method:'POST',body:JSON.stringify({decision:$('review-decision').value,note:$('review-note').value})}); $('review-dialog').close(); $('review-form').reset(); await refresh(); toast('Review recorded. No code was merged.');} catch(e) {$('review-error').textContent = e.message;} finally {event.submitter.disabled = false;}});
$('export-predictions').addEventListener('click',async () => {try {const runs = state.runs.filter(r => r.request.benchmark_id && !['queued','active'].includes(r.status)); const ids = runs.map(r => r.request.benchmark_id); if (new Set(ids).size !== ids.length) throw new Error('Multiple attempts share an instance ID. Export selected attempts through the API.'); const lines = await Promise.all(runs.map(r => api('/runs/'+r.id+'/prediction',{text:true}))); download(lines.join(''),'devmind-predictions.jsonl','application/x-ndjson');} catch(e) {toast(e.message);}});
async function poll() {if (!document.hidden) await refresh(); setTimeout(poll,2500);}
lock(); poll();
