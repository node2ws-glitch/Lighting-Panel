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
export const changePassword = (payload) => request('/auth/password', { method: 'POST', body: JSON.stringify(payload) });
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
export const rotateNodeToken = (id) => request('/admin/nodes/' + id + '/token', { method: 'POST' });

export const listServers = () => request('/admin/servers');
export const createGameServer = (payload) => request('/admin/servers', { method: 'POST', body: JSON.stringify(payload) });
export const controlServer = (id, action) => request('/admin/servers/' + id + '/action', { method: 'POST', body: JSON.stringify({action}) });

export const sendConsoleCommand = (id, command) => request('/admin/servers/' + id + '/console', { method: 'POST', body: JSON.stringify({command}) });
export const requestConsoleLogs = (id) => request('/admin/servers/' + id + '/console/logs', { method: 'POST' });
export const operateServerFiles = (id, payload) => request('/admin/servers/' + id + '/files', { method: 'POST', body: JSON.stringify(payload) });
export const listServerTasks = (id) => request('/admin/servers/' + id + '/tasks');

export const getServerTask = (serverId, taskId) => request('/admin/servers/' + serverId + '/tasks/' + taskId);

export const minecraftAction = (id, payload) => request('/admin/servers/' + id + '/minecraft/action', { method: 'POST', body: JSON.stringify(payload) });

export const manageServerBackups = (id, payload) => request('/admin/servers/' + id + '/backups', { method: 'POST', body: JSON.stringify(payload) });
export const upgradeServerVersion = (id, version) => request('/admin/servers/' + id + '/version', { method: 'POST', body: JSON.stringify({version}) });

export const getServerAccess = (id) => request('/admin/servers/' + id + '/access');
export const listServerMembers = (id) => request('/admin/servers/' + id + '/members');
export const addServerMember = (id, payload) => request('/admin/servers/' + id + '/members', { method: 'POST', body: JSON.stringify(payload) });
export const removeServerMember = (id, memberId) => request('/admin/servers/' + id + '/members/' + memberId, { method: 'DELETE' });

export const getBillingSummary = () => request('/billing/me');
export const startBillingCheckout = () => request('/billing/checkout', { method: 'POST' });
export const openBillingPortal = () => request('/billing/portal', { method: 'POST' });
export const getOperationalMetrics = () => request('/admin/metrics');

export const listBackupSchedules = (id) => request('/admin/servers/' + id + '/backup-schedules');
export const createBackupSchedule = (id, payload) => request('/admin/servers/' + id + '/backup-schedules', { method: 'POST', body: JSON.stringify(payload) });
export const updateBackupSchedule = (id, scheduleId, payload) => request('/admin/servers/' + id + '/backup-schedules/' + scheduleId, { method: 'PATCH', body: JSON.stringify(payload) });
export const deleteBackupSchedule = (id, scheduleId) => request('/admin/servers/' + id + '/backup-schedules/' + scheduleId, { method: 'DELETE' });

export const manageServerMods = (id, payload) => request('/admin/servers/' + id + '/mods', { method: 'POST', body: JSON.stringify(payload) });
