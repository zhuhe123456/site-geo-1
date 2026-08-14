const ADMIN_HEADER = 'X-Token-Admin-Key';
const ADMIN_STORAGE_KEY = 'geo-token-admin-key';
let adminKey = '';
let toastTimer = null;
let currentTokens = [];

const $ = id => document.getElementById(id);

function generateRandomToken() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  const base64 = btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
  return `geo_${base64}`;
}

function toast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2600);
}

async function readPayload(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.success) throw new Error(payload.message || `请求失败 (${response.status})`);
  return payload;
}

async function adminFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set(ADMIN_HEADER, adminKey);
  if (options.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) lockWorkspace('管理员密钥已失效，请重新验证。');
  return readPayload(response);
}

function lockWorkspace(message = '') {
  adminKey = '';
  sessionStorage.removeItem(ADMIN_STORAGE_KEY);
  $('workspace').hidden = true;
  $('login-panel').hidden = false;
  $('connection-badge').textContent = '未连接';
  $('connection-badge').className = 'badge neutral';
  $('login-message').textContent = message;
}

function unlockWorkspace(key) {
  adminKey = key;
  sessionStorage.setItem(ADMIN_STORAGE_KEY, key);
  $('login-panel').hidden = true;
  $('workspace').hidden = false;
  $('connection-badge').textContent = '已连接';
  $('connection-badge').className = 'badge success';
}

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  }).format(date);
}

function renderTokens(tokens) {
  currentTokens = tokens;
  $('total-count').textContent = tokens.length;
  $('enabled-count').textContent = tokens.filter(item => item.enabled).length;
  const lastUsed = tokens.map(item => item.last_used_at).filter(Boolean).sort().at(-1);
  $('recent-use').textContent = lastUsed ? formatTime(lastUsed) : '暂无';
  $('empty-state').hidden = tokens.length > 0;
  $('token-list').replaceChildren(...tokens.map(token => {
    const row = document.createElement('tr');
    const cells = [
      token.name,
      token.token_hint,
      token.enabled ? '运行中' : '已暂停',
      '',
      String(token.usage_count || 0),
      formatTime(token.created_at),
      formatTime(token.last_used_at)
    ];
    cells.forEach((text, index) => {
      const cell = document.createElement('td');
      if (index === 0) {
        const link = document.createElement('button');
        link.className = 'token-log-link';
        link.type = 'button';
        link.textContent = token.name;
        link.addEventListener('click', () => openTokenLogs(token).catch(error => toast(error.message)));
        const hint = document.createElement('span');
        hint.className = 'token-log-hint';
        hint.textContent = `查看 ${token.usage_count || 0} 条调用日志`;
        cell.append(link, hint);
      } else if (index === 1) {
        cell.className = 'token-hint';
        const secret = document.createElement('div');
        secret.className = 'token-secret';
        const value = document.createElement('code');
        value.textContent = token.token ? token.token_hint : '旧 Token 无明文';
        secret.appendChild(value);
        if (token.token) {
          const actions = document.createElement('div');
          actions.className = 'token-secret-actions';
          const reveal = document.createElement('button');
          reveal.className = 'small-button';
          reveal.textContent = '显示';
          let visible = false;
          reveal.addEventListener('click', () => {
            visible = !visible;
            value.textContent = visible ? token.token : token.token_hint;
            reveal.textContent = visible ? '隐藏' : '显示';
          });
          const copy = document.createElement('button');
          copy.className = 'small-button';
          copy.textContent = '复制';
          copy.addEventListener('click', async () => {
            await navigator.clipboard.writeText(token.token);
            toast('Token 已复制');
          });
          actions.append(reveal, copy);
          secret.appendChild(actions);
        } else {
          const legacy = document.createElement('span');
          legacy.className = 'legacy-token';
          legacy.textContent = token.token_hint;
          secret.appendChild(legacy);
        }
        cell.appendChild(secret);
      } else if (index === 2) {
        const pill = document.createElement('span');
        pill.className = `status-pill ${token.enabled ? 'on' : 'off'}`;
        pill.textContent = text;
        cell.appendChild(pill);
      } else if (index === 3) {
        cell.className = 'quota-cell';
        const value = document.createElement('span');
        value.className = 'quota-value';
        value.textContent = token.max_calls === null
          ? `${token.used_calls} / 不限`
          : `${token.used_calls} / ${token.max_calls}`;
        const actions = document.createElement('div');
        actions.className = 'quota-actions';
        const configure = document.createElement('button');
        configure.className = 'small-button';
        configure.type = 'button';
        configure.textContent = '设置';
        configure.addEventListener('click', () => configureTokenLimit(token).catch(error => toast(error.message)));
        const reset = document.createElement('button');
        reset.className = 'small-button';
        reset.type = 'button';
        reset.textContent = '清零';
        reset.disabled = token.used_calls === 0;
        reset.addEventListener('click', () => resetTokenUsage(token).catch(error => toast(error.message)));
        actions.append(configure, reset);
        cell.append(value, actions);
      } else {
        cell.textContent = text;
      }
      row.appendChild(cell);
    });
    const actionCell = document.createElement('td');
    actionCell.className = 'actions';
    const toggle = document.createElement('button');
    toggle.className = 'small-button';
    toggle.textContent = token.enabled ? '暂停' : '恢复';
    toggle.addEventListener('click', () => setEnabled(token.id, !token.enabled).catch(error => toast(error.message)));
    const remove = document.createElement('button');
    remove.className = 'small-button danger';
    remove.textContent = '删除';
    remove.addEventListener('click', () => deleteToken(token));
    actionCell.append(toggle, remove);
    row.appendChild(actionCell);
    return row;
  }));
  syncLogTokenFilter();
}

async function loadTokens() {
  const payload = await adminFetch('/api/v1/admin/tokens');
  renderTokens(payload.data || []);
}

function syncLogTokenFilter() {
  const select = $('log-token-filter');
  const selected = select.value;
  select.replaceChildren(new Option('全部 Token', ''), ...currentTokens.map(token => (
    new Option(`${token.name} (${token.token_hint})`, String(token.id))
  )));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function outcomeLabel(outcome) {
  return {
    valid: '成功', missing: '缺少', invalid: '无效', disabled: '已暂停',
    'quota-exceeded': '次数用完',
    'protection-disabled': '未启用'
  }[outcome] || outcome;
}

function showLogDetail(log) {
  $('log-detail').textContent = JSON.stringify({
    request_id: log.request_id,
    time: log.created_at,
    token: { id: log.token_id, name: log.token_name, hint: log.token_hint },
    authentication: {
      outcome: log.auth_outcome,
      source: log.auth_source,
      transport: log.credential_transport
    },
    request: {
      method: log.method,
      path: log.path,
      route_name: log.route_name,
      query_string: log.query_string,
      content_type: log.content_type,
      request_bytes: log.request_bytes,
      client_ip: log.client_ip,
      forwarded_for: log.forwarded_for,
      user_agent: log.user_agent,
      referer: log.referer
    },
    response: {
      status_code: log.status_code,
      response_bytes: log.response_bytes,
      duration_ms: log.duration_ms
    }
  }, null, 2);
  $('log-dialog').showModal();
}

function renderLogs(payload) {
  const logs = payload.items || [];
  $('log-count').textContent = payload.total || 0;
  $('log-empty-state').hidden = logs.length > 0;
  $('log-list').replaceChildren(...logs.map(log => {
    const row = document.createElement('tr');
    const timeCell = document.createElement('td');
    timeCell.textContent = formatTime(log.created_at);
    const tokenCell = document.createElement('td');
    tokenCell.textContent = log.token_name || (log.auth_outcome === 'missing' ? '未提供' : '未知 Token');
    tokenCell.title = log.token_hint || '';
    const authCell = document.createElement('td');
    const authPill = document.createElement('span');
    authPill.className = `status-pill ${log.auth_outcome === 'valid' ? 'on' : 'off'}`;
    authPill.textContent = outcomeLabel(log.auth_outcome);
    authCell.appendChild(authPill);
    const requestCell = document.createElement('td');
    requestCell.className = 'request-cell';
    const method = document.createElement('span');
    method.className = 'method-pill';
    method.textContent = log.method;
    const path = document.createElement('span');
    path.className = 'request-path';
    path.textContent = log.path;
    path.title = log.path;
    requestCell.append(method, path);
    const statusCell = document.createElement('td');
    statusCell.className = `status-code ${log.status_code >= 400 ? 'error' : ''}`;
    statusCell.textContent = log.status_code;
    const durationCell = document.createElement('td');
    durationCell.textContent = `${Number(log.duration_ms).toFixed(1)} ms`;
    const clientCell = document.createElement('td');
    clientCell.className = 'client-cell';
    clientCell.textContent = log.client_ip || '—';
    clientCell.title = log.forwarded_for || log.user_agent || '';
    const detailCell = document.createElement('td');
    detailCell.className = 'actions';
    const detailButton = document.createElement('button');
    detailButton.className = 'small-button';
    detailButton.textContent = '查看';
    detailButton.addEventListener('click', () => showLogDetail(log));
    detailCell.appendChild(detailButton);
    row.append(timeCell, tokenCell, authCell, requestCell, statusCell, durationCell, clientCell, detailCell);
    return row;
  }));
}

async function loadLogs() {
  const params = new URLSearchParams({ limit: '100' });
  const selectedTokenId = $('log-token-filter').value;
  if (selectedTokenId) params.set('token_id', selectedTokenId);
  if ($('log-outcome-filter').value) params.set('auth_outcome', $('log-outcome-filter').value);
  const payload = await adminFetch(`/api/v1/admin/token-logs?${params}`);
  const selectedToken = currentTokens.find(token => String(token.id) === selectedTokenId);
  $('log-scope').textContent = selectedToken ? selectedToken.name : '全部 Token';
  renderLogs(payload.data || {});
}

async function openTokenLogs(token) {
  $('log-token-filter').value = String(token.id);
  $('log-outcome-filter').value = '';
  await loadLogs();
  $('log-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function setEnabled(id, enabled) {
  await adminFetch(`/api/v1/admin/tokens/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) });
  toast(enabled ? 'Token 已恢复' : 'Token 已暂停');
  await loadTokens();
}

async function configureTokenLimit(token) {
  const current = token.max_calls === null ? '' : String(token.max_calls);
  const answer = window.prompt('请输入调用次数上限；留空表示不限次数。已使用次数不会自动清零。', current);
  if (answer === null) return;
  const value = answer.trim();
  if (value && (!/^\d+$/.test(value) || Number(value) < 1 || !Number.isSafeInteger(Number(value)))) {
    throw new Error('次数上限必须是大于 0 的整数');
  }
  await adminFetch(`/api/v1/admin/tokens/${token.id}`, {
    method: 'PATCH', body: JSON.stringify({ max_calls: value ? Number(value) : null })
  });
  toast(value ? `调用上限已设置为 ${value} 次` : '已取消调用次数限制');
  await loadTokens();
}

async function resetTokenUsage(token) {
  if (!window.confirm(`确认将“${token.name}”的已使用次数清零？调用日志会保留。`)) return;
  await adminFetch(`/api/v1/admin/tokens/${token.id}`, {
    method: 'PATCH', body: JSON.stringify({ reset_usage: true })
  });
  toast('已使用次数已清零');
  await loadTokens();
}

async function deleteToken(token) {
  if (!window.confirm(`确认删除“${token.name}”？该操作不可撤销。`)) return;
  await adminFetch(`/api/v1/admin/tokens/${token.id}`, { method: 'DELETE' });
  toast('Token 已删除');
  await loadTokens();
}

$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const key = $('admin-key').value.trim();
  $('login-message').textContent = '';
  adminKey = key;
  try {
    await adminFetch('/api/v1/admin/tokens/verify', { method: 'POST' });
    unlockWorkspace(key);
    await loadTokens();
    await loadLogs();
  } catch (error) {
    lockWorkspace(error.message);
  }
});

$('create-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const name = $('token-name').value.trim();
    const token = $('custom-token').value.trim();
    const maxCalls = $('max-calls').value.trim();
    const payload = await adminFetch('/api/v1/admin/tokens', {
      method: 'POST', body: JSON.stringify({
        name,
        token: token || null,
        max_calls: maxCalls ? Number(maxCalls) : null
      })
    });
    $('new-token').textContent = payload.data.token;
    $('secret-panel').hidden = false;
    $('create-form').reset();
    toast('Token 创建成功');
    await loadTokens();
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});

$('generate-token').addEventListener('click', () => {
  const input = $('custom-token');
  input.value = generateRandomToken();
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.focus();
  toast('已生成高强度随机 Token');
});

$('copy-token').addEventListener('click', async () => {
  await navigator.clipboard.writeText($('new-token').textContent);
  toast('已复制到剪贴板');
});
$('close-secret').addEventListener('click', () => {
  $('secret-panel').hidden = true;
  $('new-token').textContent = '';
});
$('refresh-button').addEventListener('click', () => loadTokens().catch(error => toast(error.message)));
$('refresh-logs').addEventListener('click', () => loadLogs().catch(error => toast(error.message)));
$('log-token-filter').addEventListener('change', () => loadLogs().catch(error => toast(error.message)));
$('log-outcome-filter').addEventListener('change', () => loadLogs().catch(error => toast(error.message)));
$('clear-logs').addEventListener('click', async () => {
  if (!window.confirm('确认清空全部 Token 调用日志？该操作不可撤销。')) return;
  try {
    const payload = await adminFetch('/api/v1/admin/token-logs', { method: 'DELETE' });
    toast(`已清空 ${payload.data.deleted} 条日志`);
    await loadLogs();
    await loadTokens();
  } catch (error) {
    toast(error.message);
  }
});
$('close-log-dialog').addEventListener('click', () => $('log-dialog').close());
$('log-dialog').addEventListener('click', event => {
  if (event.target === $('log-dialog')) $('log-dialog').close();
});

async function init() {
  const status = await readPayload(await fetch('/api/v1/admin/tokens/status'));
  if (!status.data.configured) {
    $('login-message').textContent = '后台尚未配置 TOKEN_ADMIN_KEY，请先设置环境变量并重启服务。';
    $('admin-key').disabled = true;
    return;
  }
  const stored = sessionStorage.getItem(ADMIN_STORAGE_KEY) || '';
  if (!stored) return;
  adminKey = stored;
  try {
    await adminFetch('/api/v1/admin/tokens/verify', { method: 'POST' });
    unlockWorkspace(stored);
    await loadTokens();
    await loadLogs();
  } catch (error) {
    lockWorkspace('请重新输入管理员密钥。');
  }
}

init().catch(error => { $('login-message').textContent = error.message; });
