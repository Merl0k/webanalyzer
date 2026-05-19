/* app.js — WebAnalyzer v3 main page */
const API = '/api/v1';

const EXAMPLES = [
  'Штучний інтелект 2025','Кліматичні зміни наслідки',
  'Квантові комп\'ютери','Python vs JavaScript 2025',
  'Космічні місії NASA','Електромобілі тенденції',
];
const STEPS = [
  {icon:'ti-world-search',   label:'Пошук в інтернеті'},
  {icon:'ti-download',       label:'Завантаження сторінок'},
  {icon:'ti-vector-triangle',label:'Семантичні вектори'},
  {icon:'ti-hierarchy',      label:'Ранжування (ChromaDB)'},
  {icon:'ti-brain',          label:'AI аналіз'},
  {icon:'ti-check',          label:'Готово'},
];

let currentDepth = 'standard';
let currentLang = localStorage.getItem('analysisLang') || 'auto';
let resultSentimentChart = null;

/* ── INIT ─────────────────────────────────────────────────────────── */
(function init(){
  // example tags
  const tagsEl = document.getElementById('exampleTags');
  EXAMPLES.forEach(ex=>{
    const btn = document.createElement('button');
    btn.className='tag'; btn.textContent=ex;
    btn.onclick=()=>{ document.getElementById('queryInput').value=ex; runSearch(); };
    tagsEl.appendChild(btn);
  });
  document.getElementById('queryInput').addEventListener('keydown', e=>{ if(e.key==='Enter') runSearch(); });
  const langSelect = document.getElementById('langSelect');

  if (langSelect) {
    langSelect.value = currentLang;
    langSelect.addEventListener('change', () => {
      currentLang = langSelect.value || 'auto';
      localStorage.setItem('analysisLang', currentLang);
    });
  }
})();

/* ── DEPTH ────────────────────────────────────────────────────────── */
function setDepth(d){
  currentDepth = d;
  document.querySelectorAll('.depth-btn').forEach(b=>b.classList.toggle('active', b.dataset.depth===d));
}

/* ── STATUS ───────────────────────────────────────────────────────── */
function setStatus(state, text){
  document.getElementById('statusDot').className = 'dot '+state;
  document.getElementById('statusText').textContent = text;
}

/* ── PIPELINE UI ──────────────────────────────────────────────────── */
function showPipelineProgress(){
  const html = `
    <div class="card pipeline-card" id="pipelineCard">
      <div class="pipeline-title"><i class="ti ti-settings-automation"></i> AI Search Pipeline</div>
      <div class="pipeline-steps" id="pipelineSteps">
        ${STEPS.map((s,i)=>`
          <div class="pipe-step" id="pstep${i}">
            <div class="pipe-icon idle"><i class="ti ${s.icon}"></i></div>
            <span class="pipe-label">${s.label}</span>
          </div>`).join('')}
      </div>
      <div class="pipe-bar-wrap"><div class="pipe-bar" id="pipeBar" style="width:0%"></div></div>
    </div>`;
  document.getElementById('resultsArea').innerHTML = html;
}

function updatePipelineStep(step, total){
  STEPS.forEach((_,i)=>{
    const el = document.getElementById('pstep'+i);
    if(!el) return;
    const icon = el.querySelector('.pipe-icon');
    if(i < step-1)      icon.className='pipe-icon done';
    else if(i===step-1) icon.className='pipe-icon active';
    else                icon.className='pipe-icon idle';
  });
  const pct = Math.round((step/total)*100);
  const bar = document.getElementById('pipeBar');
  if(bar) bar.style.width = pct+'%';
}

/* ── SEARCH ───────────────────────────────────────────────────────── */
async function runSearch(){
  const query = document.getElementById('queryInput').value.trim();
  if(!query){ setStatus('error','Введіть запит'); return; }

  const user = getUser();
  if(!user){ setStatus('error','Увійдіть у профіль щоб аналізувати'); return; }

  setStatus('loading','Запуск аналізу…');
  document.getElementById('searchBtn').disabled = true;
  showPipelineProgress();

  try {
    const resp = await fetch(API+'/analyze', {
      method:'POST', credentials:'include',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({query, depth: currentDepth, lang: currentLang})
    });
    const json = await resp.json();
    if(!resp.ok){
      setStatus('error', json.error || 'Помилка сервера');
      document.getElementById('resultsArea').innerHTML='';
      return;
    }
    if(json.task_id){
      await streamTask(json.task_id);
    } else {
      // sync result
      setStatus('done', `Знайдено ${json.sources?.length||0} джерел · аналіз завершено`);
      renderResult(json);
    }
  } catch(e){
    setStatus('error','Помилка: '+e.message);
  } finally {
    document.getElementById('searchBtn').disabled = false;
  }
}

async function streamTask(taskId){
  return new Promise(resolve=>{
    const es = new EventSource(API+'/stream/'+taskId);
    es.onmessage = e=>{
      try {
        const msg = JSON.parse(e.data);
        if(msg.error){ setStatus('error', msg.error); es.close(); resolve(); return; }
        if(msg.step && msg.total){
          updatePipelineStep(msg.step, msg.total);
          setStatus('loading', msg.message || `Крок ${msg.step}/${msg.total}…`);
        }
        if(msg.done && msg.result){
          es.close();
          setStatus('done',`Знайдено ${msg.result.sources?.length||0} джерел · аналіз завершено`);
          renderResult(msg.result);
          resolve();
        }
      } catch(e){}
    };
    es.onerror = ()=>{ es.close(); pollTask(taskId).then(resolve); };
    setTimeout(()=>{ es.close(); pollTask(taskId).then(resolve); }, 180000);
  });
}

async function pollTask(taskId){
  for(let i=0;i<60;i++){
    await new Promise(r=>setTimeout(r,2000));
    try{
      const r = await fetch(API+'/task/'+taskId, {credentials:'include'});
      const d = await r.json();
      if(d.status==='done'){ renderResult(d.result); setStatus('done','Готово'); return; }
      if(d.status==='error'){ setStatus('error', d.error||'Помилка'); return; }
    } catch(e){}
  }
  setStatus('error','Таймаут');
}

/* ── RENDER RESULT ────────────────────────────────────────────────── */
function renderResult(data){
  const sent    = data.sentiment || {};
  const pos     = (sent.positive || 0); const neg = (sent.negative || 0); const neu = (sent.neutral || 0);
  const overall = data.overall || 'neutral';
  const pillClass = {positive:'pill-pos', negative:'pill-neg', neutral:'pill-neu', mixed:'pill-mix'}[overall] || 'pill-neu';
  const pillLabel = {positive:'Позитивна', negative:'Негативна', neutral:'Нейтральна', mixed:'Змішана'}[overall] || overall;

  const factsHtml = (data.key_facts||[]).map(f=>`<li class="fact">${f}</li>`).join('');
  const sourcesHtml = (data.sources||[]).map((s,i)=>`
    <a class="source-item stagger-item" href="${s.url}" target="_blank" rel="noopener" style="animation-delay:${i*0.05}s">
      <div class="source-favicon"><i class="ti ti-world"></i></div>
      <span class="source-domain">${s.domain||''}</span>
      <span class="source-title">${s.title||s.url}</span>
      <i class="ti ti-external-link" style="flex-shrink:0;font-size:13px;color:var(--text-3)"></i>
    </a>`).join('');

  const exportId = data.id ? `
    <div class="export-btns">
      <button class="btn btn-ghost mini-btn" onclick="exportResult(${data.id},'json')">
        <i class="ti ti-file-type-json"></i> JSON
      </button>

      <button class="btn btn-ghost mini-btn" onclick="exportResult(${data.id},'markdown')">
        <i class="ti ti-markdown"></i> Markdown
      </button>

      <button class="btn btn-ghost mini-btn" onclick="exportResult(${data.id},'pdf')">
        <i class="ti ti-file-type-pdf"></i> PDF
      </button>

      <button class="btn btn-primary mini-btn" onclick="createShareLink(${data.id})">
        <i class="ti ti-share-3"></i> Поділитися
      </button>
    </div>` : '';

  document.getElementById('resultsArea').innerHTML = `
    <div style="display:flex;flex-direction:column;gap:1rem">

      <!-- Summary -->
      <div class="card anim-1">
        <div class="card-head">
          <div class="card-icon icon-blue"><i class="ti ti-file-description"></i></div>
          <div><div class="card-title">Резюме</div><div class="card-sub">${data.depth||'standard'} · ${data.lang||currentLang||'auto'} · ${data.sources_cnt||data.sources?.length||0} джерел</div></div>
          <span class="pill ${pillClass}" style="margin-left:auto">${pillLabel}</span>
        </div>
        <div class="card-body">
          <div id="summaryText" style="font-size:14px;line-height:1.75;color:var(--text-2)"></div>
          ${exportId}
        </div>
      </div>

            <!-- Sentiment -->
      <div class="card anim-2">
        <div class="card-head">
          <div class="card-icon icon-amber"><i class="ti ti-chart-donut"></i></div>
          <div>
            <div class="card-title">Тональність</div>
            <div class="card-sub">AI-оцінка емоційного забарвлення</div>
          </div>
        </div>

        <div class="card-body">
          <div class="sentiment-layout">
            <div class="donut-wrap">
              <canvas id="resultSentimentChart"></canvas>

              <div class="donut-center">
                <strong>${Math.round(Math.max(pos, neg, neu) * 100)}%</strong>
                <span>${pillLabel}</span>
              </div>
            </div>

            <div class="sentiment-details">
              <div class="sentiment-row">
                <span class="sentiment-dot sentiment-pos"></span>
                <span>Позитивна</span>
                <strong>${Math.round(pos * 100)}%</strong>
              </div>

              <div class="sentiment-row">
                <span class="sentiment-dot sentiment-neg"></span>
                <span>Негативна</span>
                <strong>${Math.round(neg * 100)}%</strong>
              </div>

              <div class="sentiment-row">
                <span class="sentiment-dot sentiment-neu"></span>
                <span>Нейтральна</span>
                <strong>${Math.round(neu * 100)}%</strong>
              </div>

              ${sent.explanation ? `<p class="sentiment-explain">${sent.explanation}</p>` : ''}
            </div>
          </div>
        </div>
      </div>

      <!-- Facts -->
      <div class="card anim-3">
        <div class="card-head">
          <div class="card-icon icon-green"><i class="ti ti-list-check"></i></div>
          <div><div class="card-title">Ключові факти</div><div class="card-sub">${(data.key_facts||[]).length} пунктів</div></div>
        </div>
        <div class="card-body"><ul class="facts">${factsHtml}</ul></div>
      </div>

      <!-- Sources -->
      <div class="card anim-4">
        <div class="card-head">
          <div class="card-icon icon-blue"><i class="ti ti-books"></i></div>
          <div><div class="card-title">Джерела</div><div class="card-sub">${(data.sources||[]).length} посилань</div></div>
        </div>
        <div class="card-body"><div class="source-list">${sourcesHtml}</div></div>
      </div>

    </div>`;

    // typewriter for summary
  typewriter(document.getElementById('summaryText'), data.summary || '');

  // render donut chart after result HTML is inserted
  renderSentimentDonut(sent);
}

function typewriter(el, text, speed=12){
  let i=0;
  function tick(){
    if(i<=text.length){ el.textContent=text.slice(0,i); i++; setTimeout(tick,speed); }
  }
  tick();
}
function renderSentimentDonut(sentiment){
  const canvas = document.getElementById('resultSentimentChart');

  if (!canvas || typeof Chart === 'undefined') {
    return;
  }

  const positive = Math.round((Number(sentiment.positive) || 0) * 100);
  const negative = Math.round((Number(sentiment.negative) || 0) * 100);
  const neutral = Math.round((Number(sentiment.neutral) || 0) * 100);

  if (resultSentimentChart) {
    resultSentimentChart.destroy();
  }

  resultSentimentChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: ['Позитивна', 'Негативна', 'Нейтральна'],
      datasets: [{
        data: [positive, negative, neutral],
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-2').trim(),
            boxWidth: 10,
            boxHeight: 10,
            padding: 14,
            font: {
              size: 12
            }
          }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.label}: ${context.raw}%`;
            }
          }
        }
      }
    }
  });
}
function exportResult(id, fmt){
  window.open(API+'/history/'+id+'/export/'+fmt, '_blank');
}

async function createShareLink(id){
  try {
    const resp = await fetch(API + '/history/' + id + '/share', {
      method: 'POST',
      credentials: 'include'
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося створити посилання');
    }

    let path = data.url || ('/share/' + data.token);

    // Backend returns "/share/<token>", but API route is under "/api/v1".
    if (path.startsWith('/share/')) {
      path = API + path;
    }

    const fullUrl = window.location.origin + path;

    await copyText(fullUrl);

    setStatus('done', 'Публічне посилання скопійовано');

    alert('Публічне посилання скопійовано:\n' + fullUrl);

  } catch (e) {
    setStatus('error', e.message);
    alert('Помилка: ' + e.message);
  }
}

async function copyText(text){
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  // Fallback for localhost / older browser permissions
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();

  try {
    document.execCommand('copy');
  } finally {
    document.body.removeChild(ta);
  }
}