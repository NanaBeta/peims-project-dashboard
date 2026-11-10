'use strict';
// Same-origin enterprise UI; no OAuth tokens, secrets or data in localStorage.
const state = { subject:'', csrf:'', projects:[], project:null, role:'viewer',
  page:'home', view:'board', tasks:[], summary:null, offset:0, limit:100,
  selected:null, month:new Date(new Date().getFullYear(),new Date().getMonth(),1) };
const $ = (id) => document.getElementById(id);
const labelStatus = {todo:'To do',in_progress:'In progress',blocked:'Blocked',done:'Done'};
const allowedStatus = ['todo','in_progress','blocked','done'];
function node(tag,cls,txt) { const el=document.createElement(tag);if(cls)el.className=cls;if(txt!==undefined)el.textContent=String(txt);return el; }
function message(text,isError=false){const box=$('notice');box.textContent=text;box.classList.toggle('error',isError);box.hidden=false;window.scrollTo({top:0,behavior:'smooth'});}
function clearMessage(){$('notice').hidden=true;}
function pretty(date){if(!date)return '—'; const d=new Date(date+'T12:00:00Z');return new Intl.DateTimeFormat(undefined,{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(d);}
function today(){ const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
const projectApi=()=>`/console/api/projects/${encodeURIComponent(state.project)}`;
const taskApi=()=>`${projectApi()}/tasks`;
async function api(url, options={}){
  const method = options.method||'GET';
  const headers = {'Accept':'application/json'};
  if(method!=='GET') {headers['Content-Type']='application/json';headers['X-PEIMS-CSRF']=state.csrf;}
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options,headers:{...headers,...(options.headers||{})}});
  if(response.status===401){$('app').hidden=true;$('login').hidden=false;throw new Error('Your session expired. Sign in again.');}
  if(!response.ok){let data={};try{data=await response.json();}catch{};
    const detail=typeof data.detail==='string'?data.detail: 'Request rejected by the server';
    if(response.status===409) throw new Error('Another user updated this record. Refresh before trying again.');
    throw new Error(`${detail} (${response.status})`);
  }
  return response.status===204?null:response.json();
}
async function init(){
  try {
    const response=await fetch('/console/api/session',{credentials:'same-origin',cache:'no-store'});
    if(response.status===401){$('app').hidden=true;$('login').hidden=false;return;}
    if(!response.ok)throw new Error('Enterprise sign-in is not available');
    const data=await response.json();
    state.subject=data.subject;state.csrf=data.csrf;state.projects=data.projects;
    $('login').hidden=true;$('app').hidden=false;
    const picker=$('projectPicker');picker.replaceChildren();
    for(const p of data.projects)picker.add(new Option(p.title,p.id));
    if(!data.projects.length){
      $('newTask').disabled=true;showPage('home');$('stats').replaceChildren();$('attention').replaceChildren(node('div','empty','No project is assigned to this account. Ask a project manager for authorized access.'));return;
    }
    state.project=data.projects[0].id;
    await reloadProject();
  }catch(err){$('app').hidden=true;$('login').hidden=false;message(err.message,true);}
}
async function reloadProject(){
  clearMessage();state.selected=null;state.offset=0;state.role=state.projects.find(p=>p.id===state.project)?.role||'viewer';
  $('newTask').disabled=state.role==='viewer';
  $('projectPicker').value=state.project;
  await refreshData();showPage(state.page);
}
async function refreshData(){
  if(!state.project)return;
  try{
    const [summary,tasks]=await Promise.all([
      api(`${projectApi()}/summary`),
      api(`${taskApi()}?limit=${state.limit}&offset=${state.offset}`),
    ]);
    state.summary=summary;state.tasks=tasks;
    render();
  }catch(err){message(err.message,true);}
}
function showPage(page){state.page=page;
  $('homePage').hidden=page!=='home';$('tasksPage').hidden=page!=='tasks';
  $('topTitle').textContent=page==='home'?'Project overview':'Tasks & schedule';
  $('topEyebrow').textContent=page==='home'?'PROJECT WORKSPACE':'WORK MANAGEMENT';
  document.querySelectorAll('.nav-link').forEach(b=>b.classList.toggle('selected',b.dataset.page===page));
  render();
}
function render(){if(!state.summary)return;
  const stats=[['Total tasks',state.summary.total],['Open tasks',state.summary.open],['Past due',state.summary.overdue],['Milestones',state.summary.milestones]];
  const holder=$('stats');holder.replaceChildren();
  for(const [name,value] of stats){const block=node('div','stat');block.append(node('small','',name),node('strong','',value));holder.append(block);}
  $('heroOpen').textContent=state.summary.open;
  $('heroSubtitle').textContent=`${state.projects.find(p=>p.id===state.project)?.title||'Project'} · only approved project members can access these records.`;
  const attention=state.tasks.filter(t=>t.status==='blocked'||t.status==='in_progress').slice(0,5);
  const list=$('attention');list.replaceChildren();
  if(!attention.length)list.append(node('div','empty','No active or blocked tasks on this page.'));
  for(const task of attention)list.append(taskLine(task));
  renderTasks();
}
function taskLine(task){const line=node('button','list-row');line.type='button';const body=node('span','body');body.append(node('strong','',task.title),node('small','',`${task.reference} · Due ${pretty(task.due_date)} · ${task.assigned_sub||'Unassigned'}`));line.append(node('span','pill '+task.status,labelStatus[task.status]),body,node('span','','›'));line.onclick=()=>openDetail(task.id);return line;}
function visibleTasks(){const query=$('taskSearch').value.trim().toLowerCase();const status=$('statusFilter').value;
  return state.tasks.filter(t=>(!status||status===t.status)&&(!query||`${t.title} ${t.reference} ${t.assigned_sub||''}`.toLowerCase().includes(query)));
}
function renderTasks(){const tasks=visibleTasks(),content=$('taskContent');content.replaceChildren();
  $('pageInfo').textContent=`${state.summary?.total||0} project tasks · ${state.tasks.length} records on this page`;
  $('pagingLabel').textContent=state.tasks.length?`Records ${state.offset+1}–${state.offset+state.tasks.length}`:'No tasks on this page';
  $('prevPage').disabled=state.offset===0;$('nextPage').disabled=state.tasks.length<state.limit;
  document.querySelectorAll('.view-tab').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));
  if(state.view==='board')drawBoard(content,tasks);
  if(state.view==='list')drawList(content,tasks);
  if(state.view==='timeline')drawTimeline(content,tasks);
  if(state.view==='calendar')drawCalendar(content,tasks);
}
function drawBoard(content,tasks){const board=node('div','kanban');for(const status of allowedStatus){const group=node('section','kanban-col');const items=tasks.filter(t=>t.status===status);const title=node('div','kanban-head');title.append(node('span','',labelStatus[status]),node('span','',items.length));group.append(title);for(const t of items){const card=node('button','task-card');card.type='button';card.append(node('span','ref',t.reference),node('strong','',t.title),node('small','',`${t.assigned_sub||'Unassigned'} · ${pretty(t.due_date)}`));const progress=node('div','progress'),fill=node('span');fill.style.width=`${Math.max(0,Math.min(100,Number(t.progress_pct)||0))}%`;progress.append(fill);card.append(progress);card.onclick=()=>openDetail(t.id);group.append(card);}board.append(group);}content.append(board);}
function drawList(content,tasks){const wrap=node('div','table-wrap'),table=node('table','data-table'),head=node('thead'),tr=node('tr');for(const h of ['Reference','Task','Owner','Status','Priority','Due date','Progress'])tr.append(node('th','',h));head.append(tr);table.append(head);const body=node('tbody');for(const task of tasks){const row=node('tr');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label',`Open ${task.title}`);for(const v of [task.reference,task.title,task.assigned_sub||'—',labelStatus[task.status],task.priority,pretty(task.due_date),`${task.progress_pct}%`])row.append(node('td','',v));row.onclick=()=>openDetail(task.id);row.onkeydown=e=>{if(e.key==='Enter')openDetail(task.id);};body.append(row);}table.append(body);wrap.append(table);content.append(wrap);if(!tasks.length)content.append(node('div','empty','No work items match these filters.'));}
function drawTimeline(content,tasks){if(!tasks.length){content.append(node('div','empty','No tasks to plot.'));return;}
  const ms=d=>Date.parse(`${d}T00:00:00Z`);const starts=tasks.map(t=>ms(t.start_date)),ends=tasks.map(t=>ms(t.due_date));const low=Math.min(...starts),high=Math.max(...ends)+86400000;const range=Math.max(86400000,high-low);
  const panel=node('div','timeline');panel.append(node('div','timeline-scale',`${pretty(new Date(low).toISOString().slice(0,10))} → ${pretty(new Date(high-86400000).toISOString().slice(0,10))} · planned dates`));
  for(const t of tasks){const row=node('div','timeline-row');row.append(node('div','timeline-name',t.title));const track=node('div','timeline-track');const bar=node('button','timeline-bar'),fill=node('span');bar.type='button';bar.style.left=`${100*(ms(t.start_date)-low)/range}%`;bar.style.width=`${Math.max(.7,100*(ms(t.due_date)+86400000-ms(t.start_date))/range)}%`;fill.style.width=`${t.progress_pct}%`;bar.title=`${t.title}: ${pretty(t.start_date)}–${pretty(t.due_date)}, ${t.progress_pct}%`;bar.setAttribute('aria-label',bar.title);bar.append(fill);bar.onclick=()=>openDetail(t.id);track.append(bar);row.append(track);panel.append(row);}content.append(panel);
}
function drawCalendar(content,tasks){const title=node('div','calendar-head');const dates=node('strong','',state.month.toLocaleString(undefined,{month:'long',year:'numeric'}));const prev=node('button','button subtle','←'),next=node('button','button subtle','→');prev.onclick=()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()-1,1);renderTasks();};next.onclick=()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()+1,1);renderTasks();};title.append(prev,dates,next);content.append(title);
  const grid=node('div','calendar-grid');for(const v of ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])grid.append(node('div','quiet',v));const year=state.month.getFullYear(),m=state.month.getMonth(),offset=(new Date(year,m,1).getDay()+6)%7,count=new Date(year,m+1,0).getDate();for(let i=0;i<offset;i++)grid.append(node('div','calendar-day blank'));
  for(let day=1;day<=count;day++){const d=node('div','calendar-day');d.append(node('span','date',day));const date=`${year}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;for(const t of tasks.filter(t=>t.due_date===date).slice(0,4)){const b=node('button','calendar-task',t.title);b.title=t.title;b.onclick=()=>openDetail(t.id);d.append(b);}grid.append(d);}content.append(grid);
}
async function openDetail(id){try{const t=await api(`${taskApi()}/${encodeURIComponent(id)}`);state.selected=t;const d=$('detailDialog');$('detailHeading').textContent=t.title;$('detailReference').textContent=`${t.reference} · version ${t.version}`;
  for(const [field,value] of Object.entries({status:t.status,priority:t.priority,progress_pct:t.progress_pct,due_date:t.due_date}))$('editForm').elements.namedItem(field).value=value;
  $('taskMeta').textContent=`${t.kind} · ${t.assigned_sub||'Unassigned'} · Planned ${pretty(t.start_date)} to ${pretty(t.due_date)}`;
  $('taskDescription').textContent=t.description||'No additional description.';
  $('saveTask').disabled=state.role==='viewer';$('commentForm').querySelector('button').disabled=state.role==='viewer';$('timeForm').querySelector('button').disabled=state.role==='viewer';$('depForm').querySelector('button').disabled=state.role==='viewer';
  $('timeDate').value=today();$('commentText').value='';$('timeHours').value='';
  const picker=$('predecessorChoice');picker.replaceChildren(new Option('Choose predecessor',''));
  for(const candidate of state.tasks.filter(x=>x.id!==id))picker.add(new Option(`${candidate.reference} · ${candidate.title}`,candidate.id));
  d.showModal();await refreshDetail();
 }catch(err){message(err.message,true);}}
async function refreshDetail(){if(!state.selected)return;const id=encodeURIComponent(state.selected.id),root=`${taskApi()}/${id}`;try{const [comments,time,deps]=await Promise.all([api(root+'/comments'),api(root+'/time'),api(root+'/predecessors')]);
  const c=$('comments');c.replaceChildren();for(const x of comments){const div=node('div','discussion-item');div.append(node('small','',`${x.author_sub} · ${pretty(x.created_at.slice(0,10))}`),node('span','',x.body));c.append(div);}if(!comments.length)c.append(node('div','quiet','No comments yet.'));
  const tl=$('timeEntries');tl.replaceChildren();for(const x of time){const div=node('div','discussion-item');div.append(node('small','',`${x.actor_sub} · ${pretty(x.work_date)}`),node('span','',`${x.hours} hours · ${x.note||'Time logged'}`));tl.append(div);}if(!time.length)tl.append(node('div','quiet','No time entries yet.'));
  const dp=$('predecessors');dp.replaceChildren();for(const x of deps){const div=node('div','discussion-item'),b=node('button','button subtle','Remove');b.type='button';b.disabled=state.role==='viewer';b.onclick=async()=>{try{await api(root+'/predecessors/'+encodeURIComponent(x.predecessor_id),{method:'DELETE'});await refreshDetail();}catch(err){message(err.message,true);}};div.append(node('span','',state.tasks.find(t=>t.id===x.predecessor_id)?.title||x.predecessor_id),node('span','','  '),b);dp.append(div);}if(!deps.length)dp.append(node('div','quiet','No predecessors linked.'));
 }catch(err){message(err.message,true);}}
async function submitJson(form,url,method,build){const btn=form.querySelector('[type=submit]');btn.disabled=true;try{await api(url,{method,body:JSON.stringify(build(new FormData(form)))});await refreshData();if(state.selected && $('detailDialog').open){state.selected=await api(`${taskApi()}/${encodeURIComponent(state.selected.id)}`);$('detailReference').textContent=`${state.selected.reference} · version ${state.selected.version}`;await refreshDetail();}else $('taskDialog').close();message('Changes saved to the project database.');}catch(err){message(err.message,true);}finally{btn.disabled=false;}}
function formText(form,key){return String(form.get(key)||'').trim();}
function bind(){
  document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>showPage(b.dataset.page)));
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;renderTasks();}));
  document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',() => $(b.dataset.close).close()));
  $('refresh').onclick=refreshData;$('openTasks').onclick=() =>showPage('tasks');$('allTasks').onclick=() =>showPage('tasks');
  $('projectPicker').onchange=async(e)=>{state.project=e.target.value;await reloadProject();};
  $('taskSearch').oninput=renderTasks;$('statusFilter').onchange=renderTasks;
  $('newTask').onclick=()=>{const f=$('taskForm');f.reset();f.elements.namedItem('start_date').value=today();f.elements.namedItem('due_date').value=today();const parent=$('parentTask');parent.replaceChildren(new Option('None',''));for(const t of state.tasks.filter(x=>x.kind==='task'))parent.add(new Option(`${t.reference} · ${t.title}`,t.id));$('parentTask').disabled=true;f.elements.namedItem('estimate_hours').disabled=false;$('taskDialog').showModal();};
  $('taskForm').elements.namedItem('kind').onchange=e=>{const isM=e.target.value==='milestone';$('taskForm').elements.namedItem('estimate_hours').disabled=isM;$('parentTask').disabled=e.target.value!=='subtask';};
  $('prevPage').onclick=async()=>{state.offset=Math.max(0,state.offset-state.limit);await refreshData();};
  $('nextPage').onclick=async()=>{state.offset+=state.limit;await refreshData();};
  $('logout').onclick=async()=>{try{await api('/console/api/logout',{method:'POST',body:'{}'});location.replace('/console/');}catch(err){message(err.message,true);}};
  $('taskForm').onsubmit=async e=>{e.preventDefault();const f=e.target;await submitJson(f,taskApi(),'POST',data=>{const kind=formText(data,'kind'),start=formText(data,'start_date');return {reference:formText(data,'reference'),title:formText(data,'title'),kind,parent_id:kind==='subtask'?formText(data,'parent_id'):null,
    start_date:start,due_date:kind==='milestone'?start:formText(data,'due_date'),priority:formText(data,'priority'),status:'todo',estimate_hours:kind==='milestone'?0:Number(formText(data,'estimate_hours')||0),progress_pct:0,assigned_sub:formText(data,'assigned_sub')||null,description:formText(data,'description')};});};
  $('editForm').onsubmit=async e=>{e.preventDefault();const t=state.selected;if(!t)return;await submitJson(e.target,`${taskApi()}/${encodeURIComponent(t.id)}`,'PATCH',data=>({expected_version:t.version,status:formText(data,'status'),priority:formText(data,'priority'),progress_pct:formText(data,'status')==='done'?100:Number(formText(data,'progress_pct')),due_date:formText(data,'due_date')}));};
  $('commentForm').onsubmit=async e=>{e.preventDefault();if(!state.selected)return;await submitJson(e.target,`${taskApi()}/${encodeURIComponent(state.selected.id)}/comments`,'POST',data=>({body:formText(data,'body')}));$('commentText').value='';};
  $('timeForm').onsubmit=async e=>{e.preventDefault();if(!state.selected)return;await submitJson(e.target,`${taskApi()}/${encodeURIComponent(state.selected.id)}/time`,'POST',data=>({work_date:formText(data,'work_date'),hours:Number(formText(data,'hours'))}));$('timeHours').value='';};
  $('depForm').onsubmit=async e=>{e.preventDefault();if(!state.selected)return;await submitJson(e.target,`${taskApi()}/${encodeURIComponent(state.selected.id)}/predecessors`,'POST',data=>({predecessor_id:formText(data,'predecessor_id')}));};
}
bind();init();
