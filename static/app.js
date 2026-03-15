// ═══════════════════════════════════════════
//  CONFIG — change base URL if needed
// ═══════════════════════════════════════════
const API_BASE = '/api';  // All API endpoints live under /api

// ═══════════════════════════════════════════
//  AUTH STATE
// ═══════════════════════════════════════════
function getToken()      { return localStorage.getItem('df_token'); }
function getCurrentUser(){ return JSON.parse(localStorage.getItem('df_user') || 'null'); }

function setSession(token, user) {
  localStorage.setItem('df_token', token);
  localStorage.setItem('df_user', JSON.stringify(user));
  // Also store in cookie so server-side Jinja2 templates can read it
  document.cookie = `df_token=${token}; path=/; SameSite=Lax; max-age=86400`;
}

function clearSession() {
  localStorage.removeItem('df_token');
  localStorage.removeItem('df_user');
  document.cookie = 'df_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
}

// ═══════════════════════════════════════════
//  API HELPERS
// ═══════════════════════════════════════════
async function _apiFetch(method, path, body = null, form = false) {
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!form)  headers['Content-Type'] = 'application/json';

  const opts = { method, headers };
  if (body) opts.body = form ? new URLSearchParams(body) : JSON.stringify(body);

  const r = await fetch(API_BASE + path, opts);
  const data = await r.json();
  if (!r.ok) {
    // FastAPI validation errors return detail as an array of objects
    const detail = data.detail;
    let msg;
    if (Array.isArray(detail)) {
      msg = detail.map(e => e.msg || JSON.stringify(e)).join(', ');
    } else {
      msg = detail || data.message || 'Request failed';
    }
    throw new Error(msg);
  }
  return data;
}

const apiGet   = (p)       => _apiFetch('GET',    p);
const apiPost  = (p, b, f) => _apiFetch('POST',   p, b, f);
const apiPatch = (p, b)    => _apiFetch('PATCH',  p, b);
const apiPut   = (p, b)    => _apiFetch('PUT',    p, b);
const apiDel   = (p)       => _apiFetch('DELETE', p);

// ═══════════════════════════════════════════
//  TOAST
// ═══════════════════════════════════════════
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  el.innerHTML = `<span style="font-size:.9rem">${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ═══════════════════════════════════════════
//  AUTH ACTIONS
// ═══════════════════════════════════════════
async function doLogin() {
  const u = document.getElementById('login-username').value.trim();
  const p = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';
  if (!u || !p) { errEl.textContent = 'Please fill all fields.'; return; }

  try {
    const data = await apiPost('/auth/login', { username: u, password: p }, true);
    const token = data.data.access_token;

    // Save token FIRST so the next request carries the Authorization header
    localStorage.setItem('df_token', token);

    const userResp = await apiGet('/users/me');
    setSession(token, userResp.data);

    closeModal('login-modal');
    toast(`Welcome back, ${userResp.data.username}!`, 'success');
    updateAuthUI();

    // Redirect: if we were on a protected page, stay; otherwise reload
    const path = window.location.pathname;
    if (path === '/profile' || path === '/admin') {
      setTimeout(() => window.dispatchEvent(new Event('authReady')), 0);
    } else {
      location.reload();
    }
  } catch(e) {
    errEl.textContent = e.message;
  }
}

async function doRegister() {
  const fn = document.getElementById('reg-first').value.trim();
  const ln = document.getElementById('reg-last').value.trim();
  const em = document.getElementById('reg-email').value.trim();
  const un = document.getElementById('reg-username').value.trim();
  const pw = document.getElementById('reg-password').value;
  const errEl = document.getElementById('reg-error');
  const okEl  = document.getElementById('reg-success');
  errEl.textContent = '';
  okEl.textContent  = '';

  if (!fn || !ln || !em || !un || !pw) { errEl.textContent = 'All fields required.'; return; }
  try {
    await apiPost('/auth/register', { first_name: fn, last_name: ln, email: em, username: un, password: pw });
    okEl.textContent = 'Account created! Signing you in…';
    // Auto-login
    const loginData = await apiPost('/auth/login', { username: un, password: pw }, true);
    const token = loginData.data.access_token;

    // Save token FIRST so the next request carries the Authorization header
    localStorage.setItem('df_token', token);

    const userResp = await apiGet('/users/me');
    setSession(token, userResp.data);
    closeModal('register-modal');
    toast(`Welcome to DevForum, ${un}!`, 'success');
    updateAuthUI();
    location.reload();
  } catch(e) {
    errEl.textContent = e.message;
  }
}

function logout() {
  clearSession();
  updateAuthUI();
  toast('Signed out.', 'info');
  window.location = '/';
}

// ═══════════════════════════════════════════
//  AUTH UI UPDATE
// ═══════════════════════════════════════════
function updateAuthUI() {
  const user    = getCurrentUser();
  const isAdmin = user && user.role_id === 1;

  // Show/hide auth-gated nav items
  document.querySelectorAll('.auth-only').forEach(el => {
    el.style.display = user ? '' : 'none';
  });
  document.querySelectorAll('.guest-only').forEach(el => {
    el.style.display = user ? 'none' : '';
  });
  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = isAdmin ? '' : 'none';
  });

  // Header user info
  const infoEl   = document.getElementById('user-info');
  const logoutEl = document.getElementById('logout-btn');
  if (user && infoEl) {
    const initials = ((user.first_name||'?')[0] + (user.last_name||'?')[0]).toUpperCase();
    infoEl.innerHTML = `
      <div class="avatar">${initials}</div>
      <span>${escHtml(user.username)}</span>
      ${isAdmin ? '<span class="badge-admin">admin</span>' : ''}`;
    infoEl.style.display = 'flex';
    if (logoutEl) logoutEl.style.display = '';
  }

  // New topic button (topics page)
  const newTopicBtn = document.getElementById('new-topic-btn');
  if (newTopicBtn) newTopicBtn.style.display = user ? 'inline-flex' : 'none';

  // Mark active nav link
  const path = window.location.pathname;
  document.querySelectorAll('.nav-btn').forEach(a => {
    const href = a.getAttribute('href');
    a.classList.toggle('active',
      href === path || (href === '/topics' && path.startsWith('/topics'))
    );
  });
}

// ═══════════════════════════════════════════
//  TOPIC MODAL (create / edit)
// ═══════════════════════════════════════════
function openCreateTopic() {
  if (!getCurrentUser()) { openModal('login-modal'); return; }
  document.getElementById('topic-modal-title').textContent = 'New Topic';
  document.getElementById('topic-edit-id').value      = '';
  document.getElementById('topic-title-input').value  = '';
  document.getElementById('topic-content-input').value= '';
  document.getElementById('topic-private-check').checked = false;
  document.getElementById('topic-error').textContent  = '';
  openModal('topic-modal');
}

function openEditTopic(id, title, content, isPrivate) {
  document.getElementById('topic-modal-title').textContent = 'Edit Topic';
  document.getElementById('topic-edit-id').value      = id;
  document.getElementById('topic-title-input').value  = title;
  document.getElementById('topic-content-input').value= content;
  document.getElementById('topic-private-check').checked = !!isPrivate;
  document.getElementById('topic-error').textContent  = '';
  openModal('topic-modal');
}

// Default submitTopic used on topics list page (overridden on detail page)
async function submitTopic() {
  const editId  = document.getElementById('topic-edit-id').value;
  const title   = document.getElementById('topic-title-input').value.trim();
  const content = document.getElementById('topic-content-input').value.trim();
  const isPriv  = document.getElementById('topic-private-check').checked;
  const errEl   = document.getElementById('topic-error');
  errEl.textContent = '';
  if (title.length < 16 || title.length > 128) { errEl.textContent = 'Title: 16–128 chars.'; return; }
  if (content.length < 32) { errEl.textContent = 'Content: min 32 chars.'; return; }
  try {
    if (editId) {
      await apiPatch(`/topics/${editId}`, { title, content, is_private: isPriv });
      toast('Topic updated!', 'success');
      closeModal('topic-modal');
      location.reload();
    } else {
      const d = await apiPost('/topics/', { title, content, is_private: isPriv });
      toast('Topic created!', 'success');
      closeModal('topic-modal');
      window.location = `/topics/${d.data.topic_id}`;
    }
  } catch(e) { errEl.textContent = e.message; }
}

// ═══════════════════════════════════════════
//  MODAL HELPERS
// ═══════════════════════════════════════════
function openModal(id)  { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }
function overlayClose(e, id) {
  if (e.target.classList.contains('modal-overlay')) closeModal(id);
}
function switchModal(from, to) { closeModal(from); openModal(to); }

document.addEventListener('keydown', e => {
  if (e.key === 'Escape')
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
});

// ═══════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════
function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(d) {
  if (!d) return '';
  const dt   = new Date(d);
  const diff = (Date.now() - dt) / 1000;
  if (diff < 60)     return 'just now';
  if (diff < 3600)   return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff/3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff/86400)}d ago`;
  return dt.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}


// ═══════════════════════════════════════════
//  NOTIFICATIONS (invitations)
// ═══════════════════════════════════════════
async function loadNotifications() {
  if (!getCurrentUser()) return;
  try {
    // status=0 means pending
    const d    = await apiGet('/invitations/?status=0&per_page=20');
    const list = d.data.invitations || [];
    const badge = document.getElementById('notif-badge');
    const wrap  = document.getElementById('notif-wrap');
    if (badge) {
      badge.textContent = list.length;
      badge.style.display = list.length ? 'flex' : 'none';
    }
    if (wrap) wrap.style.display = '';

    const el = document.getElementById('notif-list');
    if (!el) return;
    if (!list.length) {
      el.innerHTML = '<div style="padding:1.25rem;text-align:center;font-size:.83rem;color:var(--text3)">No pending invitations 🎉</div>';
      return;
    }
    el.innerHTML = list.map(inv => `
      <div class="notif-item" id="notif-${inv.invitation_id}">
        <div class="notif-topic">📩 ${escHtml(inv.topic_title)}</div>
        <div class="notif-meta">Invited by <strong>${escHtml(inv.invited_by_username)}</strong></div>
        <div class="notif-btns">
          <button class="btn btn-green btn-sm" onclick="respondInvite(${inv.invitation_id},1)">✓ Accept</button>
          <button class="btn btn-danger btn-sm" onclick="respondInvite(${inv.invitation_id},2)">✕ Decline</button>
          <a class="btn btn-ghost btn-sm" href="/topics/${inv.topic_id}">View topic</a>
        </div>
      </div>`).join('');
  } catch(e) { /* silently ignore if user not authed yet */ }
}

async function respondInvite(invitationId, status) {
  try {
    await apiPatch('/invitations/' + invitationId, { invitation_status: status });
    toast(status === 1 ? 'Invitation accepted! You can now access the topic.' : 'Invitation declined.', status === 1 ? 'success' : 'info');
    loadNotifications();
  } catch(e) { toast(e.message, 'error'); }
}

function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  const isOpen = panel.style.display !== 'none';
  panel.style.display = isOpen ? 'none' : 'block';
  if (!isOpen) loadNotifications(); // refresh on open
}

// Close notif panel on outside click
document.addEventListener('click', e => {
  const wrap = document.getElementById('notif-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const panel = document.getElementById('notif-panel');
    if (panel) panel.style.display = 'none';
  }
});

// ═══════════════════════════════════════════
//  INIT — runs on every page
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  updateAuthUI();
  loadNotifications();
  // Defer authReady by one tick so inline <script> blocks in extra_scripts
  // have time to register their listeners before the event fires
  setTimeout(() => window.dispatchEvent(new Event('authReady')), 0);
});