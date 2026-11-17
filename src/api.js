const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '') + '/api/v1';
const TOKEN_KEY = 'lighting_panel_access_token';
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);
async function request(path, options = {}) {
  const token = getToken();
  const response = await fetch(API_BASE + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}), ...options.headers },
  });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) clearToken();
    throw new Error(data.detail || 'Request failed (' + response.status + ')');
  }
  return data;
}
export async function login(email, password) {
  const data = await request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
  return data.user;
}
export const currentUser = () => request('/auth/me');
export const logout = async () => { try { await request('/auth/logout', { method: 'POST' }); } finally { clearToken(); } };
export const listUsers = () => request('/admin/users');
export const createUser = (payload) => request('/admin/users', { method: 'POST', body: JSON.stringify(payload) });
export const setUserStatus = (id, active) => request('/admin/users/' + id + '/status?is_active=' + active, { method: 'PATCH' });
export const listAudit = () => request('/admin/audit');
export const apiHealth = () => request('/health');

export const listNodes = () => request('/admin/nodes');
export const createNode = (payload) => request('/admin/nodes', { method: 'POST', body: JSON.stringify(payload) });
export const setNodeStatus = (id, enabled) => request('/admin/nodes/' + id + '/status?is_enabled=' + enabled, { method: 'PATCH' });

export const listServers = () => request('/admin/servers');
export const createGameServer = (payload) => request('/admin/servers', { method: 'POST', body: JSON.stringify(payload) });
export const controlServer = (id, action) => request('/admin/servers/' + id + '/action', { method: 'POST', body: JSON.stringify({action}) });
