const WA_API = '/api/v1';

function getUser() { return JSON.parse(localStorage.getItem('wa_user')||'null'); }

async function logout() {
  try { await fetch(WA_API+'/auth/logout',{method:'POST',credentials:'include'}); } catch(e){}
  localStorage.removeItem('wa_user');
  location.href='auth.html';
}

(function(){
  const user = getUser();
  const emailEl   = document.getElementById('navEmail');
  const logoutBtn = document.getElementById('logoutBtn');
  const loginBtn  = document.getElementById('loginBtn');
  if(user){
    if(emailEl)  { emailEl.textContent=user.email; emailEl.style.display=''; }
    if(logoutBtn){ logoutBtn.style.display=''; }
    if(loginBtn) { loginBtn.style.display='none'; }
  } else {
    if(loginBtn) { loginBtn.style.display=''; }
    if(logoutBtn){ logoutBtn.style.display='none'; }
  }
})();
