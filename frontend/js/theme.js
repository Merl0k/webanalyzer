(function(){
  const THEMES = ['dark','light','cyberpunk','ocean','sunset'];
  let current = localStorage.getItem('wa_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', current);

  // Theme toggle button (cycles through themes)
  function applyTheme(name){
    current = name || 'dark';
    document.documentElement.setAttribute('data-theme', current);
    localStorage.setItem('wa_theme', current);
    // notify backend (if logged in) — ignore errors
    try{ fetch('/api/v1/profile/theme', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({theme: current})}); }catch(e){}
  }

  document.getElementById('themeToggle')?.addEventListener('click', ()=>{
    const idx = THEMES.indexOf(current);
    const next = THEMES[(idx+1)%THEMES.length];
    applyTheme(next);
  });

  // Ripple effect for buttons
  document.addEventListener('click', e=>{
    const btn = e.target.closest('.btn');
    if(!btn || btn.disabled) return;
    const r = btn.getBoundingClientRect();
    btn.style.setProperty('--rx', ((e.clientX-r.left)/r.width*100)+'%');
    btn.style.setProperty('--ry', ((e.clientY-r.top)/r.height*100)+'%');
    btn.classList.add('rippling');
    setTimeout(()=>btn.classList.remove('rippling'), 400);
  });
  
  // expose for debugging
  window._wa_applyTheme = applyTheme;
})();
