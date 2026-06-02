const API_BASE = '/api/v1';

const SENT_LABELS = {
  positive: 'Позитивна',
  negative: 'Негативна',
  neutral: 'Нейтральна',
  mixed: 'Змішана'
};

const SENT_COLORS = {
  positive: 'var(--accent)',
  negative: 'var(--red)',
  neutral: 'var(--text-3)',
  mixed: 'var(--amber)'
};

let statsSentimentChart = null;

async function loadStats() {
  try {
    const resp = await fetch(`${API_BASE}/stats`, {
      credentials: 'include'
    });

    const s = await resp.json();

    if (!resp.ok) {
      throw new Error(s.error || 'Не вдалося завантажити статистику');
    }

    renderStats(s);

  } catch (err) {
    document.getElementById('statsArea').innerHTML = `
      <div class="empty">
        <i class="ti ti-alert-circle"></i>
        <p>Помилка завантаження: ${escHtml(err.message)}</p>
        <p style="font-size:13px;color:var(--text-3);margin-top:.5rem">
          Якщо ви не увійшли в акаунт, спочатку авторизуйтесь.
        </p>
        <a href="auth.html" class="btn btn-primary" style="margin-top:1rem;text-decoration:none">
          <i class="ti ti-login"></i> Увійти
        </a>
      </div>`;
  }
}

function renderStats(s) {
  const avgSent = s.avg_sentiment || {};

  const posAvg = Math.round((avgSent.pos || 0) * 100);
  const negAvg = Math.round((avgSent.neg || 0) * 100);

  const sentDist = s.sentiment_dist || [];

  const daily = s.daily || [];
  const maxDay = Math.max(...daily.map(d => d.cnt), 1);

  const dayBars = daily.map(d => {
    const pct = Math.round(d.cnt / maxDay * 100);
    const label = d.day ? d.day.slice(5) : '';

    return `
      <div class="chart-bar-wrap">
        <div class="chart-bar" style="height:${Math.max(pct, 3)}%"></div>
        <div class="chart-lbl">${escHtml(label)}</div>
      </div>`;
  }).join('');

  const topQ = (s.top_queries || []).map(q => `
    <div class="top-query">
      <span class="top-query-text">${escHtml(q.query)}</span>
      <span class="top-query-cnt">${q.cnt}×</span>
    </div>
  `).join('');

  document.getElementById('statsArea').innerHTML = `

    <div class="stat-grid anim-1" style="margin-bottom:1rem">
      <div class="stat-card">
        <div class="stat-val">${s.total || 0}</div>
        <div class="stat-lbl">Всього запитів</div>
      </div>

      <div class="stat-card">
        <div class="stat-val">${s.avg_sources || 0}</div>
        <div class="stat-lbl">Сер. джерел</div>
      </div>

      <div class="stat-card">
        <div class="stat-val" style="font-size:22px">${posAvg}%</div>
        <div class="stat-lbl">Середній позитив</div>
      </div>

      <div class="stat-card">
        <div class="stat-val" style="color:var(--red);font-size:22px">${negAvg}%</div>
        <div class="stat-lbl">Середній негатив</div>
      </div>
    </div>

    ${daily.length ? `
      <div class="card anim-2" style="margin-bottom:1rem">
        <div class="card-head">
          <div class="card-icon icon-blue"><i class="ti ti-chart-bar"></i></div>
          <div>
            <div class="card-title">Активність за 14 днів</div>
            <div class="card-sub">запитів на день</div>
          </div>
        </div>

        <div class="card-body">
          <div class="chart-bars">${dayBars}</div>
        </div>
      </div>
    ` : ''}

    ${sentDist.length ? `
      <div class="card anim-3" style="margin-bottom:1rem">
        <div class="card-head">
          <div class="card-icon icon-amber"><i class="ti ti-chart-donut"></i></div>
          <div>
            <div class="card-title">Розподіл тональності</div>
            <div class="card-sub">по всіх запитах</div>
          </div>
        </div>

        <div class="card-body">
          <div class="stats-donut-wrap">
            <canvas id="sentimentChartCanvas"></canvas>
          </div>
        </div>
      </div>
    ` : ''}

    ${topQ ? `
      <div class="card anim-4">
        <div class="card-head">
          <div class="card-icon icon-green"><i class="ti ti-star"></i></div>
          <div>
            <div class="card-title">Популярні запити</div>
            <div class="card-sub">топ-10</div>
          </div>
        </div>

        <div class="card-body">${topQ}</div>
      </div>
    ` : ''}

    ${!s.total ? `
      <div class="empty anim-2">
        <i class="ti ti-chart-bar"></i>
        <p>
          Статистика з'явиться після перших пошуків.<br>
          <a href="index.html" style="color:var(--accent)">Перейти до пошуку →</a>
        </p>
      </div>
    ` : ''}
  `;

  if (sentDist.length) {
    renderSentimentDonut(sentDist);
  }
}

function renderSentimentDonut(items) {
  const canvas = document.getElementById('sentimentChartCanvas');

  if (!canvas || typeof Chart === 'undefined') {
    return;
  }

  const labels = items.map(item => SENT_LABELS[item.overall] || item.overall);
  const values = items.map(item => item.cnt);
  const colors = items.map(item => resolveColor(SENT_COLORS[item.overall] || 'var(--text-3)'));

  if (statsSentimentChart && typeof statsSentimentChart.destroy === 'function') {
    statsSentimentChart.destroy();
  }

  statsSentimentChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 0,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '66%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: getComputedStyle(document.documentElement)
              .getPropertyValue('--text')
              .trim() || '#fff',
            boxWidth: 10,
            boxHeight: 10,
            padding: 14
          }
        },
        tooltip: {
          enabled: true
        }
      }
    }
  });
}

function resolveColor(value) {
  if (typeof value !== 'string') {
    return value;
  }

  const trimmed = value.trim();

  if (!trimmed.startsWith('var(')) {
    return trimmed;
  }

  const name = trimmed.slice(4, -1).trim();

  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim() || trimmed;
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

loadStats();