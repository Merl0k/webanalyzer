const WA_API = '/api/v1';

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('wa_user') || 'null');
  } catch (e) {
    return null;
  }
}

function setAuthHidden(el, hidden) {
  if (!el) return;

  el.classList.toggle('nav-auth-hidden', hidden);

  if (hidden) {
    el.style.display = 'none';
  } else {
    el.style.display = '';
  }
}

function ensureAuthControls() {
  const navUser = document.getElementById('navUser');

  if (!navUser) {
    return {};
  }

  // Remove accidental duplicates
  Array.from(document.querySelectorAll('#loginBtn')).slice(1).forEach(el => el.remove());
  Array.from(document.querySelectorAll('#logoutBtn')).slice(1).forEach(el => el.remove());

  let emailEl = document.getElementById('navEmail');

  if (!emailEl) {
    emailEl = document.createElement('span');
    emailEl.id = 'navEmail';
    emailEl.style.fontSize = '12px';
    emailEl.style.color = 'var(--text-3)';
    emailEl.style.fontFamily = "'DM Mono', monospace";
    emailEl.style.display = 'none';
    navUser.prepend(emailEl);
  }

  let logoutBtn = document.getElementById('logoutBtn');

  if (!logoutBtn) {
    logoutBtn = document.createElement('button');
    logoutBtn.id = 'logoutBtn';
    logoutBtn.type = 'button';
    logoutBtn.className = 'btn btn-ghost nav-auth-btn';
    logoutBtn.innerHTML = `<i class="ti ti-logout"></i><span>Вийти</span>`;
    logoutBtn.onclick = logout;
    navUser.appendChild(logoutBtn);
  }

  let loginBtn = document.getElementById('loginBtn');

  if (!loginBtn) {
    loginBtn = document.createElement('a');
    loginBtn.id = 'loginBtn';
    loginBtn.href = 'auth.html';
    loginBtn.className = 'btn btn-ghost nav-auth-btn';
    loginBtn.innerHTML = `<i class="ti ti-login"></i><span>Увійти</span>`;
    navUser.appendChild(loginBtn);
  }

  logoutBtn.classList.add('nav-auth-btn');
  loginBtn.classList.add('nav-auth-btn');

  return {
    emailEl,
    logoutBtn,
    loginBtn
  };
}

function renderAuthState(user) {
  const { emailEl, logoutBtn, loginBtn } = ensureAuthControls();

  if (user) {
    if (emailEl) {
      emailEl.textContent = user.email || '';
      emailEl.style.display = '';
    }

    setAuthHidden(logoutBtn, false);
    setAuthHidden(loginBtn, true);
  } else {
    if (emailEl) {
      emailEl.textContent = '';
      emailEl.style.display = 'none';
    }

    setAuthHidden(logoutBtn, true);
    setAuthHidden(loginBtn, false);
  }
}

async function verifyAuth() {
  const user = getUser();

  renderAuthState(user);

  if (!user) {
    return;
  }

  try {
    const resp = await fetch(WA_API + '/auth/me', {
      credentials: 'include'
    });

    if (!resp.ok) {
      localStorage.removeItem('wa_user');
      renderAuthState(null);
      return;
    }

    const freshUser = await resp.json();

    if (freshUser && freshUser.email) {
      localStorage.setItem('wa_user', JSON.stringify(freshUser));
      renderAuthState(freshUser);
    }

  } catch (e) {
    // Якщо backend недоступний, не ламаємо UI одразу.
  }
}

async function logout() {
  try {
    await fetch(WA_API + '/auth/logout', {
      method: 'POST',
      credentials: 'include'
    });
  } catch (e) {}

  localStorage.removeItem('wa_user');
  renderAuthState(null);
  location.href = 'auth.html';
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', verifyAuth);
} else {
  verifyAuth();
}