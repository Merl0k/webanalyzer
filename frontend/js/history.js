const API_BASE = '/api/v1';
const PAGE_SIZE = 15;
let currentOffset = 0;
let totalItems = 0;
let selectedCompareIds = new Set();
let compareChart = null;
let allTags = [];
let activeTagId = null;
let openedDetailId = null;

const SENT_LABEL = { positive: 'Позитивна', negative: 'Негативна', neutral: 'Нейтральна', mixed: 'Змішана' };
const SENT_PILL  = { positive: 'pill-pos',  negative: 'pill-neg',  neutral: 'pill-neu',   mixed: 'pill-mix' };

function setStatus(state, text) {
  document.getElementById('statusDot').className = 'dot ' + state;
  document.getElementById('statusText').textContent = text;
}

async function loadHistory(offset = 0) {
  currentOffset = offset;
  setStatus('loading', 'Завантаження...');

  document.getElementById('historyArea').innerHTML =
    '<div style="display:flex;flex-direction:column;gap:.5rem">' +
    [1,2,3,4,5].map(() => '<div class="skeleton" style="height:64px"></div>').join('') +
    '</div>';

  try {
    const params = new URLSearchParams({
      limit: PAGE_SIZE,
      offset: offset
    });

    if (activeTagId) {
      params.set('tag_id', activeTagId);
    }

    const resp = await fetch(`${API_BASE}/history?${params.toString()}`, {
      credentials: 'include'
    });

    const rows = await resp.json();

    if (!resp.ok) {
      throw new Error(rows.error || 'Не вдалося завантажити історію');
    }

    if (!rows.length && offset === 0) {
      setStatus('', activeTagId ? 'За цим тегом записів немає' : 'Записів немає');

      document.getElementById('historyArea').innerHTML = `
        <div class="empty">
          <i class="ti ti-clock"></i>
          <p>
            ${activeTagId
              ? 'За вибраним тегом ще немає збережених запитів.'
              : 'Ще немає збережених запитів.<br>Зробіть перший пошук на <a href="index.html" style="color:var(--accent)">головній сторінці</a>.'
            }
          </p>
        </div>`;

      document.getElementById('pager').innerHTML = '';
      updateComparePanel();
      return;
    }

    setStatus('done', `Показано ${offset + 1}–${offset + rows.length}`);

    document.getElementById('historyArea').innerHTML = rows.map((r, i) => `
      <div class="history-item compare-history-item anim-${Math.min(i+1,5)}" onclick="openDetail(${r.id})" style="margin-bottom:.4rem">
        <label class="compare-check-wrap" onclick="event.stopPropagation()" title="Обрати для порівняння">
          <input
            type="checkbox"
            class="compare-check"
            data-id="${r.id}"
            onchange="toggleCompareSelection(event, ${r.id})"
            ${selectedCompareIds.has(r.id) ? 'checked' : ''}
          />
          <span></span>
        </label>

        <div style="flex:1;min-width:0">
          <div class="hist-query">
            ${escHtml(r.query)}
            <span>${r.created_at} · ${r.sources_cnt} джерел</span>
          </div>
        </div>

        <span class="pill ${SENT_PILL[r.overall] || 'pill-neu'} hist-badge" style="font-size:11px">
          ${SENT_LABEL[r.overall] || r.overall}
        </span>

        <button class="btn btn-danger" onclick="deleteItem(event, ${r.id})" style="padding:.3rem .5rem;font-size:13px" title="Видалити">
          <i class="ti ti-trash"></i>
        </button>
      </div>`
    ).join('');

    updateComparePanel();

    // pager
    const pager = document.getElementById('pager');
    pager.innerHTML = '';

    if (offset > 0) {
      const prev = document.createElement('button');
      prev.className = 'btn btn-ghost';
      prev.innerHTML = '<i class="ti ti-chevron-left"></i> Назад';
      prev.onclick = () => loadHistory(Math.max(0, offset - PAGE_SIZE));
      pager.appendChild(prev);
    }

    if (rows.length === PAGE_SIZE) {
      const next = document.createElement('button');
      next.className = 'btn btn-ghost';
      next.innerHTML = 'Далі <i class="ti ti-chevron-right"></i>';
      next.onclick = () => loadHistory(offset + PAGE_SIZE);
      pager.appendChild(next);
    }

  } catch (err) {
    setStatus('error', 'Помилка: ' + err.message);
  }
}

async function openDetail(id) {
  openedDetailId = id;

  const backdrop = document.getElementById('modalBackdrop');
  backdrop.style.display = 'flex';
  backdrop.className = 'modal-backdrop';

  document.getElementById('modalBox').innerHTML = `
    <div class="modal-head">
      <h3>Деталі запиту #${id}</h3>
      <button class="btn btn-ghost" onclick="closeModal()" style="padding:.3rem .6rem">
        <i class="ti ti-x"></i>
      </button>
    </div>

    <div class="modal-body">
      <div class="skeleton" style="height:100px"></div>
      <div class="skeleton" style="height:80px"></div>
      <div class="skeleton" style="height:120px"></div>
    </div>`;

  try {
    const resp = await fetch(`${API_BASE}/history/${id}`, {
      credentials: 'include'
    });

    const r = await resp.json();

    if (!resp.ok) {
      throw new Error(r.error || 'Не вдалося завантажити деталі');
    }

    const sent = r.sentiment || {};
    const pos  = Math.round((sent.positive || 0) * 100);
    const neg  = Math.round((sent.negative || 0) * 100);
    const neu  = Math.round((sent.neutral  || 0) * 100);

    const facts = (r.key_facts || [])
      .map(f => `<li class="fact">${escHtml(f)}</li>`)
      .join('');

    const srcs = (r.sources || []).map(s => {
      let host = s.domain || '';

      if (!host && s.url) {
        try {
          host = new URL(s.url).hostname;
        } catch {}
      }

      return `
        <div class="source-item" onclick="window.open('${escAttr(s.url)}','_blank')">
          <div class="source-favicon"><i class="ti ti-world"></i></div>
          <span class="source-domain">${escHtml(host)}</span>
          <span class="source-title">${escHtml(s.title || '')}</span>
          <i class="ti ti-external-link" style="font-size:12px;color:var(--text-3);flex-shrink:0"></i>
        </div>`;
    }).join('');

    const tagOptions = allTags.map(t => `
      <option value="${t.id}">${escHtml(t.name)}</option>
    `).join('');

    const resultTags = (r.tags || []).length
      ? (r.tags || []).map(t => `
          <span class="detail-tag" style="--tag-color:${escAttr(t.color || '#4fffb0')}">
            ${escHtml(t.name)}
            <button onclick="removeTagFromOpenedDetail(event, ${t.id})" title="Прибрати тег">
              <i class="ti ti-x"></i>
            </button>
          </span>
        `).join('')
      : '<span class="muted-small">Тегів ще немає</span>';

    document.getElementById('modalBox').innerHTML = `
      <div class="modal-head">
        <h3 style="max-width:80%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${escHtml(r.query)}
        </h3>

        <button class="btn btn-ghost" onclick="closeModal()" style="padding:.3rem .6rem">
          <i class="ti ti-x"></i>
        </button>
      </div>

      <div class="modal-body">

        <div class="card">
          <div class="card-head">
            <div class="card-icon icon-blue"><i class="ti ti-file-text"></i></div>
            <div><div class="card-title">Суммаризація</div></div>
          </div>

          <div class="card-body">
            <p style="font-size:13.5px;line-height:1.75;color:var(--text)">
              ${escHtml(r.summary || '')}
            </p>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div class="card-icon icon-amber"><i class="ti ti-mood-smile"></i></div>
            <div><div class="card-title">Тональність</div></div>
          </div>

          <div class="card-body">
            <span class="pill ${SENT_PILL[sent.overall] || 'pill-neu'}">
              ${SENT_LABEL[sent.overall] || sent.overall}
            </span>

            <div class="bar-group" style="margin-top:.75rem">
              <div class="bar-row">
                <span class="bar-lbl">Позитив</span>
                <div class="bar-track">
                  <div class="bar-fill" style="width:${pos}%;background:var(--accent)"></div>
                </div>
                <span class="bar-pct">${pos}%</span>
              </div>

              <div class="bar-row">
                <span class="bar-lbl">Негатив</span>
                <div class="bar-track">
                  <div class="bar-fill" style="width:${neg}%;background:var(--red)"></div>
                </div>
                <span class="bar-pct">${neg}%</span>
              </div>

              <div class="bar-row">
                <span class="bar-lbl">Нейтрал</span>
                <div class="bar-track">
                  <div class="bar-fill" style="width:${neu}%;background:var(--text-3)"></div>
                </div>
                <span class="bar-pct">${neu}%</span>
              </div>
            </div>
          </div>
        </div>

        ${facts ? `
          <div class="card">
            <div class="card-head">
              <div class="card-icon icon-green"><i class="ti ti-list-check"></i></div>
              <div><div class="card-title">Ключові факти</div></div>
            </div>

            <div class="card-body">
              <ul class="facts">${facts}</ul>
            </div>
          </div>
        ` : ''}

        ${srcs ? `
          <div class="card">
            <div class="card-head">
              <div class="card-icon icon-blue"><i class="ti ti-world"></i></div>
              <div><div class="card-title">Джерела</div></div>
            </div>

            <div class="card-body">
              <div class="source-list">${srcs}</div>
            </div>
          </div>
        ` : ''}

        <div class="detail-tags-box">
          <div class="detail-tags-head">
            <div>
              <i class="ti ti-tags"></i>
              <span>Теги результату</span>
            </div>

            <select class="tag-select" id="detailTagSelect">
              <option value="">Додати тег...</option>
              ${tagOptions}
            </select>

            <button class="btn btn-primary mini-btn" onclick="addSelectedTagToOpenedDetail()">
              <i class="ti ti-plus"></i> Додати
            </button>
          </div>

          <div class="detail-tags-list">
            ${resultTags}
          </div>
        </div>

        <div class="modal-actions">
          <div class="modal-actions-left">
            <button class="btn btn-ghost mini-btn" onclick="exportHistoryResult(${id},'json')">
              <i class="ti ti-file-type-json"></i> JSON
            </button>

            <button class="btn btn-ghost mini-btn" onclick="exportHistoryResult(${id},'markdown')">
              <i class="ti ti-markdown"></i> Markdown
            </button>

            <button class="btn btn-ghost mini-btn" onclick="exportHistoryResult(${id},'pdf')">
              <i class="ti ti-file-type-pdf"></i> PDF
            </button>

            <button class="btn btn-primary mini-btn" onclick="createHistoryShareLink(${id})">
              <i class="ti ti-share-3"></i> Поділитися
            </button>
          </div>

          <div class="modal-actions-right">
            <button class="btn btn-danger" onclick="deleteItem(null,${id},true)">
              <i class="ti ti-trash"></i> Видалити
            </button>

            <button class="btn btn-ghost" onclick="closeModal()">Закрити</button>
          </div>
        </div>

      </div>`;

  } catch (err) {
    document.getElementById('modalBox').innerHTML = `
      <div class="modal-head">
        <h3>Помилка</h3>
        <button class="btn btn-ghost" onclick="closeModal()" style="padding:.3rem .6rem">
          <i class="ti ti-x"></i>
        </button>
      </div>

      <div class="modal-body">
        <p style="color:var(--red)">${err.message}</p>
      </div>`;
  }
}

async function deleteItem(e, id, fromModal = false) {
  if (e) e.stopPropagation();
  if (!confirm('Видалити цей запис?')) return;
  await fetch(`${API_BASE}/history/${id}`, { method: 'DELETE', credentials:'include' });
  if (fromModal) closeModal();
  loadHistory(currentOffset);
}

function closeModal(e) {
  if (e && e.target !== document.getElementById('modalBackdrop')) return;
  document.getElementById('modalBackdrop').style.display = 'none';
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function escAttr(str) { return String(str||'').replace(/'/g,'%27'); }

function exportHistoryResult(id, fmt) {
  window.open(`${API_BASE}/history/${id}/export/${fmt}`, '_blank');
}

async function createHistoryShareLink(id) {
  try {
    const resp = await fetch(`${API_BASE}/history/${id}/share`, {
      method: 'POST',
      credentials: 'include'
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося створити посилання');
    }

    let path = data.url || `/share/${data.token}`;

    // Backend returns "/share/<token>", but API route is under "/api/v1".
    if (path.startsWith('/share/')) {
      path = API_BASE + path;
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

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

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

function toggleCompareSelection(event, id) {
  event.stopPropagation();

  const checked = event.target.checked;

  if (checked) {
    if (selectedCompareIds.size >= 3) {
      event.target.checked = false;
      setStatus('error', 'Можна обрати максимум 3 результати');
      return;
    }

    selectedCompareIds.add(id);
  } else {
    selectedCompareIds.delete(id);
  }

  updateComparePanel();
}

function updateComparePanel() {
  const panel = document.getElementById('comparePanel');
  const countText = document.getElementById('compareCountText');
  const compareBtn = document.getElementById('compareBtn');

  if (!panel || !countText || !compareBtn) {
    return;
  }

  const count = selectedCompareIds.size;

  panel.style.display = count > 0 ? 'flex' : 'none';
  countText.textContent = `Обрано ${count} результат${count === 1 ? '' : 'и'}`;

  compareBtn.disabled = count < 2 || count > 3;
}

function clearCompareSelection() {
  selectedCompareIds.clear();

  document.querySelectorAll('.compare-check').forEach(ch => {
    ch.checked = false;
  });

  const result = document.getElementById('compareResult');
  if (result) {
    result.style.display = 'none';
    result.innerHTML = '';
  }

  if (compareChart) {
    compareChart.destroy();
    compareChart = null;
  }

  updateComparePanel();
  setStatus('done', 'Вибір очищено');
}

async function compareSelected() {
  const ids = Array.from(selectedCompareIds);

  if (ids.length < 2 || ids.length > 3) {
    setStatus('error', 'Оберіть 2–3 результати для порівняння');
    return;
  }

  setStatus('loading', 'Порівняння результатів...');

  try {
    const resp = await fetch(`${API_BASE}/compare`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ ids })
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося порівняти результати');
    }

    renderCompareResult(data);
    setStatus('done', 'Порівняння готове');

    document.getElementById('compareResult')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });

  } catch (err) {
    setStatus('error', err.message);
    alert('Помилка порівняння: ' + err.message);
  }
}

function renderCompareResult(data) {
  const box = document.getElementById('compareResult');

  if (!box) {
    return;
  }

  const queries = data.queries || [];
  const sentiments = data.sentiments || [];
  const overalls = data.overalls || [];
  const sourcesCnt = data.sources_cnt || [];
  const keyFacts = data.key_facts || [];

  const cardsHtml = queries.map((query, index) => {
    const sent = sentiments[index] || {};
    const overall = overalls[index] || sent.overall || 'neutral';

    const pos = Math.round((Number(sent.positive) || 0) * 100);
    const neg = Math.round((Number(sent.negative) || 0) * 100);
    const neu = Math.round((Number(sent.neutral) || 0) * 100);

    const facts = (keyFacts[index] || [])
      .slice(0, 4)
      .map(f => `<li>${escHtml(f)}</li>`)
      .join('');

    return `
      <div class="compare-card">
        <div class="compare-card-head">
          <span class="compare-index">#${index + 1}</span>
          <span class="pill ${SENT_PILL[overall] || 'pill-neu'}">
            ${SENT_LABEL[overall] || overall}
          </span>
        </div>

        <h3>${escHtml(query)}</h3>

        <div class="compare-metrics">
          <div>
            <span>Позитив</span>
            <strong>${pos}%</strong>
          </div>
          <div>
            <span>Негатив</span>
            <strong>${neg}%</strong>
          </div>
          <div>
            <span>Нейтрал</span>
            <strong>${neu}%</strong>
          </div>
          <div>
            <span>Джерела</span>
            <strong>${sourcesCnt[index] || 0}</strong>
          </div>
        </div>

        ${facts ? `<ul class="compare-facts">${facts}</ul>` : ''}
      </div>
    `;
  }).join('');

  box.style.display = 'block';
  box.innerHTML = `
    <div class="card compare-main-card">
      <div class="card-head">
        <div class="card-icon icon-blue"><i class="ti ti-git-compare"></i></div>
        <div>
          <div class="card-title">Порівняння результатів</div>
          <div class="card-sub">${queries.length} обрані аналізи</div>
        </div>
      </div>

      <div class="card-body">
        <div class="compare-chart-wrap">
          <canvas id="compareChart"></canvas>
        </div>

        <div class="compare-grid">
          ${cardsHtml}
        </div>
      </div>
    </div>
  `;

  renderCompareChart(data);
}

function renderCompareChart(data) {
  const canvas = document.getElementById('compareChart');

  if (!canvas || typeof Chart === 'undefined') {
    return;
  }

  if (compareChart) {
    compareChart.destroy();
  }

  const queries = data.queries || [];
  const sentiments = data.sentiments || [];
  const sourcesCnt = data.sources_cnt || [];

  const labels = queries.map((q, i) => {
    const text = String(q || `Запит ${i + 1}`);
    return text.length > 22 ? text.slice(0, 22) + '…' : text;
  });

  compareChart = new Chart(canvas, {
    type: 'radar',
    data: {
      labels: ['Позитив', 'Негатив', 'Нейтрал', 'Джерела'],
      datasets: sentiments.map((sent, i) => {
        const pos = Math.round((Number(sent.positive) || 0) * 100);
        const neg = Math.round((Number(sent.negative) || 0) * 100);
        const neu = Math.round((Number(sent.neutral) || 0) * 100);

        const maxSources = Math.max(...sourcesCnt, 1);
        const sourceScore = Math.round(((Number(sourcesCnt[i]) || 0) / maxSources) * 100);

        return {
          label: labels[i],
          data: [pos, neg, neu, sourceScore],
          borderWidth: 2,
          pointRadius: 3,
          fill: true
        };
      })
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 20,
            backdropColor: 'transparent',
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-3').trim()
          },
          grid: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--border').trim()
          },
          angleLines: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--border').trim()
          },
          pointLabels: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-2').trim(),
            font: {
              size: 12
            }
          }
        }
      },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-2').trim(),
            boxWidth: 10,
            boxHeight: 10,
            padding: 14
          }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${context.raw}%`;
            }
          }
        }
      }
    }
  });
}

async function loadTags() {
  try {
    const resp = await fetch(`${API_BASE}/tags`, {
      credentials: 'include'
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося завантажити теги');
    }

    allTags = Array.isArray(data) ? data : [];
    renderTagFilters();

  } catch (err) {
    console.warn('Tags load failed:', err);
  }
}

function renderTagFilters() {
  const box = document.getElementById('tagFilterList');

  if (!box) {
    return;
  }

  const allActive = activeTagId === null ? 'active' : '';

  box.innerHTML = `
    <button class="tag-filter ${allActive}" onclick="setTagFilter(null)">
      Усі
    </button>

    ${allTags.map(tag => `
      <button
        class="tag-filter ${Number(activeTagId) === Number(tag.id) ? 'active' : ''}"
        style="--tag-color:${escAttr(tag.color || '#4fffb0')}"
        onclick="setTagFilter(${tag.id})"
      >
        <span></span>
        ${escHtml(tag.name)}
      </button>
    `).join('')}
  `;
}

function setTagFilter(tagId) {
  activeTagId = tagId;
  currentOffset = 0;

  renderTagFilters();
  loadHistory();

  setStatus('done', tagId ? 'Фільтр за тегом застосовано' : 'Показано всі результати');
}

async function createTagFromInput() {
  const nameInput = document.getElementById('newTagName');
  const colorInput = document.getElementById('newTagColor');

  const name = (nameInput?.value || '').trim();
  const color = colorInput?.value || '#4fffb0';

  if (!name) {
    setStatus('error', 'Введіть назву тегу');
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/tags`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name, color })
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося створити тег');
    }

    if (nameInput) {
      nameInput.value = '';
    }

    await loadTags();

    setStatus('done', 'Тег створено');

  } catch (err) {
    setStatus('error', err.message);
    alert('Помилка створення тегу: ' + err.message);
  }
}

async function addSelectedTagToOpenedDetail() {
  if (!openedDetailId) {
    setStatus('error', 'Результат не відкрито');
    return;
  }

  const select = document.getElementById('detailTagSelect');
  const tagId = select?.value;

  if (!tagId) {
    setStatus('error', 'Оберіть тег');
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/history/${openedDetailId}/tags/${tagId}`, {
      method: 'POST',
      credentials: 'include'
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося додати тег');
    }

    setStatus('done', 'Тег додано');

    await openDetail(openedDetailId);
    await loadHistory();

  } catch (err) {
    setStatus('error', err.message);
    alert('Помилка додавання тегу: ' + err.message);
  }
}

async function removeTagFromOpenedDetail(event, tagId) {
  event.stopPropagation();

  if (!openedDetailId) {
    setStatus('error', 'Результат не відкрито');
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/history/${openedDetailId}/tags/${tagId}`, {
      method: 'DELETE',
      credentials: 'include'
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || 'Не вдалося прибрати тег');
    }

    setStatus('done', 'Тег прибрано');

    await openDetail(openedDetailId);
    await loadHistory();

  } catch (err) {
    setStatus('error', err.message);
    alert('Помилка видалення тегу: ' + err.message);
  }
}

// boot
// boot
(async function bootHistoryPage() {
  await loadTags();
  await loadHistory();
})();
