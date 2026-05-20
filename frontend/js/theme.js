(function(){
  const THEMES = [
    {
      id: 'dark',
      name: 'Neon Dark',
      hint: 'чорно-зелена',
      colors: ['#080b0d', '#4fffb0']
    },
    {
      id: 'light',
      name: 'Porcelain',
      hint: 'світла спокійна',
      colors: ['#f7f4ee', '#2f6f8f']
    },
    {
      id: 'cyberpunk',
      name: 'Cyber Rose',
      hint: 'рожево-синя',
      colors: ['#070817', '#ff4da6']
    },
    {
      id: 'ocean',
      name: 'Ocean Mint',
      hint: 'зелено-синя',
      colors: ['#04131d', '#2dd4bf']
    },
    {
      id: 'aurora',
      name: 'Aurora',
      hint: 'лісово-зелена',
      colors: ['#07130d', '#8ee88e']
    },
    {
      id: 'violet',
      name: 'Violet',
      hint: 'фіолетова',
      colors: ['#0f0b1d', '#a78bfa']
    },
    {
      id: 'graphite',
      name: 'Graphite',
      hint: 'графітово-блакитна',
      colors: ['#070a0f', '#38bdf8']
    },
    {
      id: 'mocha',
      name: 'Mocha',
      hint: 'тепла кавова',
      colors: ['#130f0c', '#d6a85f']
    }
  ];

  const THEME_IDS = THEMES.map(t => t.id);
  const THEME_MAP = Object.fromEntries(THEMES.map(t => [t.id, t]));

  let current = localStorage.getItem('wa_theme') || 'dark';

  if (!THEME_IDS.includes(current)) {
    current = 'dark';
  }

  document.documentElement.setAttribute('data-theme', current);

  function getThemeLabel(id){
    return THEME_MAP[id]?.name || id || 'Theme';
  }

  function applyTheme(name, options = {}){
    const next = THEME_IDS.includes(name) ? name : 'dark';

    current = next;

    document.documentElement.setAttribute('data-theme', current);
    localStorage.setItem('wa_theme', current);

    updateThemeUi();

    if (!options.silent) {
      try {
        fetch('/api/v1/profile/theme', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ theme: current })
        });
      } catch(e) {}
    }
  }

  function buildThemePicker(){
    let trigger = document.getElementById('themeToggle');

    const nav = document.querySelector('.nav');

    if (!trigger && nav) {
      const holder = document.createElement('div');
      holder.className = 'theme-picker nav-theme-picker';

      trigger = document.createElement('button');
      trigger.id = 'themeToggle';
      trigger.type = 'button';

      holder.appendChild(trigger);
      nav.appendChild(holder);
    }

    if (!trigger) {
      return;
    }

    let picker = trigger.closest('.theme-picker');

    if (!picker) {
      picker = document.createElement('div');
      picker.className = 'theme-picker';

      trigger.parentNode.insertBefore(picker, trigger);
      picker.appendChild(trigger);
    }

    trigger.type = 'button';
    trigger.className = 'theme-trigger';
    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.title = 'Змінити тему інтерфейсу';

    trigger.innerHTML = `
      <i class="ti ti-palette"></i>
      <span class="theme-trigger-text">Тема</span>
      <span class="theme-trigger-current" id="themeCurrentLabel">${getThemeLabel(current)}</span>
      <i class="ti ti-chevron-down theme-trigger-arrow"></i>
    `;

    let menu = picker.querySelector('.theme-menu');

    if (!menu) {
      menu = document.createElement('div');
      menu.className = 'theme-menu';
      menu.id = 'themeMenu';

      picker.appendChild(menu);
    }

    menu.innerHTML = `
      <div class="theme-menu-head">
        <div>
          <strong>Тема сайту</strong>
          <span>обери стиль інтерфейсу</span>
        </div>
      </div>

      <div class="theme-grid">
        ${THEMES.map(theme => `
          <button
            class="theme-choice"
            type="button"
            data-theme="${theme.id}"
            title="${theme.name} · ${theme.hint}"
            style="--swatch-a:${theme.colors[0]};--swatch-b:${theme.colors[1]}"
          >
            <span class="theme-swatch">
              <span></span>
            </span>

            <span class="theme-choice-name">${theme.name}</span>
          </button>
        `).join('')}
      </div>
    `;

    trigger.addEventListener('click', event => {
      event.stopPropagation();

      const isOpen = picker.classList.toggle('open');
      trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    menu.addEventListener('click', event => {
      const btn = event.target.closest('.theme-choice');

      if (!btn) {
        return;
      }

      applyTheme(btn.dataset.theme);

      picker.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
    });
  }

  function updateThemeUi(){
    const label = document.getElementById('themeCurrentLabel');

    if (label) {
      label.textContent = getThemeLabel(current);
    }

    document.querySelectorAll('.theme-choice').forEach(btn => {
      const isActive = btn.dataset.theme === current;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === current);
    });

    const currentName = document.getElementById('currentThemeName');

    if (currentName) {
      currentName.textContent = getThemeLabel(current);
    }
  }

  document.addEventListener('click', event => {
    const picker = event.target.closest('.theme-picker');

    document.querySelectorAll('.theme-picker.open').forEach(openPicker => {
      if (openPicker !== picker) {
        openPicker.classList.remove('open');

        const trigger = openPicker.querySelector('.theme-trigger');
        trigger?.setAttribute('aria-expanded', 'false');
      }
    });
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') {
      return;
    }

    document.querySelectorAll('.theme-picker.open').forEach(openPicker => {
      openPicker.classList.remove('open');

      const trigger = openPicker.querySelector('.theme-trigger');
      trigger?.setAttribute('aria-expanded', 'false');
    });
  });

  // Ripple effect for buttons
  document.addEventListener('click', e => {
    const btn = e.target.closest('.btn');

    if (!btn || btn.disabled) {
      return;
    }

    const r = btn.getBoundingClientRect();

    btn.style.setProperty('--rx', ((e.clientX - r.left) / r.width * 100) + '%');
    btn.style.setProperty('--ry', ((e.clientY - r.top) / r.height * 100) + '%');

    btn.classList.add('rippling');

    setTimeout(() => btn.classList.remove('rippling'), 400);
  });

  buildThemePicker();
  updateThemeUi();

  window.WA_THEME = {
    list: THEMES,
    apply: applyTheme,
    current: () => current,
    label: getThemeLabel
  };

  window._wa_applyTheme = applyTheme;
})();