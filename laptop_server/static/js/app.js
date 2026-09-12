/**
 * app.js — AgriScan 360 Dashboard JavaScript
 * Handles: WebSocket live feed, API calls, UI state management,
 *           history table, image grid, modal, pagination, toasts.
 */

'use strict';

// =============================================================================
// State
// =============================================================================
const State = {
  ws:          null,
  wsConnected: false,
  currentScan: null,       // Latest live scan result
  history:     [],
  stats:       null,
  page:        1,
  limit:       15,
  totalPages:  1,
  filterProduce: '',
  filterStatus:  '',
  scanning:    false,
  scanStop:    0,
};

// =============================================================================
// Utilities
// =============================================================================
const $ = id => document.getElementById(id);
const el = (tag, cls = '', html = '') => {
  const e = document.createElement(tag);
  if (cls)  e.className   = cls;
  if (html) e.innerHTML   = html;
  return e;
};

function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    day:'2-digit', month:'short', year:'numeric',
    hour:'2-digit', minute:'2-digit', second:'2-digit',
  });
}

function statusBadgeHTML(status) {
  const map = {
    HEALTHY:   ['status-badge-healthy',  '✦ Healthy'],
    ROTTEN:    ['status-badge-rotten',   '✗ Rotten'],
    UNCERTAIN: ['status-badge-uncertain','? Uncertain'],
    SCANNING:  ['status-badge-scanning', '◉ Scanning'],
    IDLE:      ['status-badge-idle',     '◌ Idle'],
    PENDING:   ['status-badge-scanning', '⧖ Pending'],
  };
  const [cls, label] = map[status?.toUpperCase()] || ['status-badge-idle', status || 'Unknown'];
  return `<span class="status-badge ${cls}">${label}</span>`;
}

function suspicionHTML(level) {
  const cls = { LOW: 'suspicion-low', MEDIUM: 'suspicion-medium', HIGH: 'suspicion-high' }[level] || 'suspicion-low';
  return `<span class="gas-suspicion-chip ${cls}">${level || 'LOW'}</span>`;
}

function panelClass(status) {
  return {
    HEALTHY: 'panel-healthy', ROTTEN: 'panel-rotten',
    UNCERTAIN: 'panel-uncertain', SCANNING: 'panel-scanning',
  }[status?.toUpperCase()] || 'panel-idle';
}

function confBarColor(status) {
  return { HEALTHY: '#00e676', ROTTEN: '#ff453a', UNCERTAIN: '#ffa500' }[status] || '#64748b';
}

// =============================================================================
// Toast Notifications
// =============================================================================
function showToast(title, body, type = '') {
  const container = $('toast-container');
  const toast = el('div', `toast-notif toast-${type.toLowerCase()}`);
  toast.innerHTML = `
    <div>
      <div class="toast-title">${title}</div>
      <div class="toast-body">${body}</div>
    </div>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.4s'; }, 3500);
  setTimeout(() => toast.remove(), 4000);
}

// =============================================================================
// WebSocket
// =============================================================================
function connectWebSocket() {
  const wsUrl = `ws://${window.location.host}/ws/live`;
  State.ws = new WebSocket(wsUrl);

  State.ws.onopen = () => {
    State.wsConnected = true;
    updateConnectionUI(true);
    console.log('[AgriScan] WebSocket connected');
  };

  State.ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      handleWsEvent(data);
    } catch (e) {
      console.error('[AgriScan] WS parse error:', e);
    }
  };

  State.ws.onclose = () => {
    State.wsConnected = false;
    updateConnectionUI(false);
    console.log('[AgriScan] WebSocket disconnected. Reconnecting in 3s...');
    setTimeout(connectWebSocket, 3000);
  };

  State.ws.onerror = (err) => {
    console.error('[AgriScan] WebSocket error:', err);
  };
}

function handleWsEvent(data) {
  if (data.event === 'connected') {
    console.log('[AgriScan] WS handshake:', data.message);
    return;
  }
  if (data.event === 'scan_complete') {
    State.scanning    = false;
    State.currentScan = data;
    renderLivePanel(data);
    loadHistory();
    loadStats();
    showToast(
      `Scan Complete — ${data.produce_name}`,
      `${data.status} (${data.confidence?.toFixed(1)}% confidence)`,
      data.status
    );
  }
}

function updateConnectionUI(connected) {
  const dot  = $('connection-dot');
  const text = $('connection-text');
  dot.className  = `connection-dot ${connected ? 'connected' : 'disconnected'}`;
  text.textContent = connected ? 'Live' : 'Reconnecting...';
}

// =============================================================================
// Live Panel Rendering
// =============================================================================
function renderLivePanel(data) {
  const panel    = $('live-panel');
  const statusEl = $('live-status');
  const produceEl = $('live-produce');
  const confVal  = $('live-confidence-val');
  const confBar  = $('live-confidence-bar');
  const reasonEl = $('live-reason');
  const gasVal   = $('live-gas-delta');
  const gasUnit  = $('live-gas-unit');
  const gasSusp  = $('live-gas-suspicion');

  // Panel state class
  panel.className = `card-tech ${panelClass(data.status)}`;

  // Status + produce
  statusEl.innerHTML   = statusBadgeHTML(data.status);
  produceEl.textContent = data.produce_name || '—';

  // Big status text
  const bigStatus = $('live-status-large');
  if (bigStatus) {
    bigStatus.textContent = data.status || '—';
    bigStatus.style.color = confBarColor(data.status);
  }

  // Confidence bar
  const conf = data.confidence || 0;
  confVal.textContent   = `${conf.toFixed(1)}%`;
  confBar.style.width   = `${conf}%`;
  confBar.style.background = confBarColor(data.status);

  // Reason
  if (reasonEl) reasonEl.textContent = data.reason || '—';

  // Gas
  if (gasVal)  gasVal.textContent = (data.gas_delta || 0).toFixed(2);
  if (gasUnit) gasUnit.style.display = 'inline';
  if (gasSusp) gasSusp.innerHTML = suspicionHTML(data.rot_suspicion);

  // Animate in
  panel.classList.add('fade-in');
}

function renderScanningState(stop) {
  const panel = $('live-panel');
  if (panel) panel.className = 'card-tech panel-scanning';

  const bigStatus = $('live-status-large');
  if (bigStatus) { bigStatus.textContent = 'SCANNING'; bigStatus.style.color = '#bf5af2'; }

  const statusEl = $('live-status');
  if (statusEl)  statusEl.innerHTML = statusBadgeHTML('SCANNING');

  const produceEl = $('live-produce');
  if (produceEl) produceEl.textContent = `Stop ${stop}/8`;

  // Progress ring
  updateProgressRing(stop, 8);
}

function updateProgressRing(current, total) {
  const ring = $('progress-ring-fg');
  const txt  = $('progress-stop-display');
  if (!ring) return;
  const radius = 30;
  const circ   = 2 * Math.PI * radius;
  const offset = circ - (current / total) * circ;
  ring.style.strokeDasharray  = `${circ}`;
  ring.style.strokeDashoffset = `${offset}`;
  if (txt) txt.textContent = `${current}/${total}`;
}

// =============================================================================
// API Calls
// =============================================================================
async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
  return resp.json();
}

async function loadHistory() {
  try {
    const params = new URLSearchParams({
      page:  State.page,
      limit: State.limit,
    });
    if (State.filterProduce) params.set('produce', State.filterProduce);
    if (State.filterStatus)  params.set('status',  State.filterStatus);

    const data = await fetchJSON(`/api/history?${params}`);
    State.history   = data.items || [];
    State.totalPages = Math.ceil((data.total || 0) / State.limit) || 1;
    renderHistoryTable(State.history, data.total);
    renderPagination();
  } catch (e) {
    console.error('[AgriScan] History load error:', e);
  }
}

async function loadStats() {
  try {
    const data = await fetchJSON('/api/stats');
    State.stats = data;
    renderStats(data);
  } catch (e) {
    console.error('[AgriScan] Stats load error:', e);
  }
}

async function openScanDetail(scanId) {
  try {
    const data = await fetchJSON(`/api/scan/${scanId}`);
    renderDetailModal(data);
    const modal = new bootstrap.Modal($('detailModal'));
    modal.show();
  } catch (e) {
    console.error('[AgriScan] Detail load error:', e);
    showToast('Error', `Could not load scan #${scanId}`, 'rotten');
  }
}

async function deleteScan(scanId) {
  if (!confirm(`Delete scan #${scanId}? This will remove all ${16} images permanently.`)) return;
  try {
    const resp = await fetch(`/api/scan/${scanId}`, { method: 'DELETE' });
    if (resp.ok) {
      showToast('Deleted', `Scan #${scanId} removed.`, '');
      loadHistory();
      loadStats();
    }
  } catch (e) {
    showToast('Error', 'Delete failed.', 'rotten');
  }
}

// =============================================================================
// History Table Rendering
// =============================================================================
function renderHistoryTable(items, total) {
  const tbody = $('history-tbody');
  const count = $('history-count');
  if (!tbody) return;

  if (count) count.textContent = `${total ?? items.length} total`;

  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center; padding:2rem; color:var(--text-muted);">
          No scan records yet. Run a scan from the Raspberry Pi.
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = '';
  items.forEach(item => {
    const tr = el('tr', 'fade-in');
    tr.innerHTML = `
      <td class="table-id">#${item.id}</td>
      <td class="table-produce">${item.produce_name}</td>
      <td>${statusBadgeHTML(item.status)}</td>
      <td><span style="font-family:monospace; font-size:0.85rem">${(item.confidence || 0).toFixed(1)}%</span></td>
      <td class="table-gas">${(item.gas_delta || 0).toFixed(2)} kΩ</td>
      <td>${suspicionHTML(item.rot_suspicion)}</td>
      <td class="table-timestamp">${formatDateTime(item.created_at)}</td>
      <td style="display:flex; gap:6px; align-items:center;">
        <button class="btn-detail" onclick="openScanDetail(${item.id})">Detail</button>
        <button class="btn-delete" onclick="deleteScan(${item.id})">✕</button>
      </td>`;
    tbody.appendChild(tr);
  });
}

// =============================================================================
// Stats Rendering
// =============================================================================
function renderStats(data) {
  const set = (id, val) => { const e = $(id); if (e) e.textContent = val; };
  set('stat-total',     data.total_scans ?? 0);
  set('stat-healthy',   data.healthy_count ?? 0);
  set('stat-rotten',    data.rotten_count ?? 0);
  set('stat-uncertain', data.uncertain_count ?? 0);
  set('stat-healthy-pct',   `${data.healthy_pct ?? 0}%`);
  set('stat-rotten-pct',    `${data.rotten_pct ?? 0}%`);
  set('stat-uncertain-pct', `${data.uncertain_pct ?? 0}%`);
  set('stat-avg-conf',  `${(data.avg_confidence ?? 0).toFixed(1)}%`);

  // Produce breakdown bars
  renderProduceBreakdown(data.produce_breakdown || {}, data.total_scans || 1);
}

function renderProduceBreakdown(breakdown, total) {
  const container = $('produce-breakdown');
  if (!container) return;
  container.innerHTML = '';
  const sorted = Object.entries(breakdown).sort((a, b) => b[1] - a[1]).slice(0, 8);
  if (sorted.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem">No data yet</p>';
    return;
  }
  sorted.forEach(([name, count]) => {
    const pct = Math.round(count / total * 100);
    const item = el('div', 'produce-bar-item');
    item.innerHTML = `
      <span class="produce-bar-name">${name}</span>
      <div class="produce-bar-track"><div class="produce-bar-fill" style="width:${pct}%"></div></div>
      <span class="produce-bar-count">${count}</span>`;
    container.appendChild(item);
  });
}

// =============================================================================
// Detail Modal
// =============================================================================
function renderDetailModal(data) {
  const modalTitle   = $('detail-modal-title');
  const modalContent = $('detail-modal-content');
  if (!modalContent) return;

  if (modalTitle) modalTitle.textContent = `Scan #${data.id} — ${data.produce_name}`;

  const imgGrid = (imgs, type) => {
    if (!imgs || imgs.length === 0) return '<p style="color:var(--text-muted);font-size:0.8rem">No images</p>';
    return imgs
      .filter(i => i.light_type === type)
      .sort((a, b) => a.angle_deg - b.angle_deg)
      .map(img => `
        <div class="scan-thumb" onclick="window.open('${img.url_path}','_blank')">
          <img src="${img.url_path}" alt="${img.light_type} ${img.angle_deg}°"
               onerror="this.parentElement.innerHTML='<div class=\'thumb-placeholder\'>🖼</div>'">
          <span class="angle-label">${img.angle_deg}°</span>
        </div>`).join('');
  };

  modalContent.innerHTML = `
    <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:flex-start; margin-bottom:1rem;">
      <div>${statusBadgeHTML(data.status)}</div>
      <div style="font-size:1.5rem; font-weight:700; color:${confBarColor(data.status)}">${data.status}</div>
      <div style="margin-left:auto; font-family:monospace; font-size:1.2rem; color:var(--uv-purple)">${(data.confidence||0).toFixed(1)}%</div>
    </div>

    <div class="reason-text" style="margin-bottom:1rem">${data.reason || '—'}</div>

    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:1.2rem">
      <div class="stat-card">
        <div class="stat-value stat-total" style="font-size:1.3rem; color:var(--text-mono)">${(data.gas_delta||0).toFixed(2)} kΩ</div>
        <div class="stat-label">Gas Δ</div>
        <div class="stat-sub">${suspicionHTML(data.rot_suspicion)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="font-size:1.3rem; color:var(--text-secondary)">${data.temperature_c ? data.temperature_c.toFixed(1)+'°C' : '—'}</div>
        <div class="stat-label">Temperature</div>
        <div class="stat-sub">${data.humidity_pct ? data.humidity_pct.toFixed(1)+'% RH' : ''}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="font-size:1.1rem; color:var(--text-muted)">${data.model_used || 'rule_based'}</div>
        <div class="stat-label">Model</div>
        <div class="stat-sub">${data.scan_duration_s ? data.scan_duration_s.toFixed(1)+'s scan' : ''}</div>
      </div>
    </div>

    <div class="spectral-band-title band-rgb">🔆 360° Visible Surface Vector (RGB) — 8 angles</div>
    <div class="image-grid" style="margin-bottom:1rem">${imgGrid(data.images, 'rgb')}</div>

    <div class="spectral-band-title band-uv">🔵 Fungal Fluorescence Index (365nm UV-A) — 8 angles</div>
    <div class="image-grid">${imgGrid(data.images, 'uv')}</div>

    <p style="font-size:0.75rem; color:var(--text-muted); margin-top:1rem">
      Scanned: ${formatDateTime(data.created_at)}
    </p>`;
}

// =============================================================================
// Pagination
// =============================================================================
function renderPagination() {
  const container = $('pagination');
  if (!container) return;
  container.innerHTML = '';

  const prev = el('button', `page-btn${State.page <= 1 ? ' disabled' : ''}`);
  prev.textContent = '← Prev';
  prev.disabled    = State.page <= 1;
  prev.onclick     = () => { State.page--; loadHistory(); };
  container.appendChild(prev);

  for (let p = Math.max(1, State.page - 2); p <= Math.min(State.totalPages, State.page + 2); p++) {
    const btn = el('button', `page-btn${p === State.page ? ' active' : ''}`);
    btn.textContent = p;
    btn.onclick = () => { State.page = p; loadHistory(); };
    container.appendChild(btn);
  }

  const next = el('button', `page-btn${State.page >= State.totalPages ? ' disabled' : ''}`);
  next.textContent = 'Next →';
  next.disabled    = State.page >= State.totalPages;
  next.onclick     = () => { State.page++; loadHistory(); };
  container.appendChild(next);
}

// =============================================================================
// Filter Bar
// =============================================================================
function applyFilters() {
  State.filterProduce = $('filter-produce')?.value?.trim() || '';
  State.filterStatus  = $('filter-status')?.value  || '';
  State.page = 1;
  loadHistory();
}

function clearFilters() {
  const fp = $('filter-produce');
  const fs = $('filter-status');
  if (fp) fp.value = '';
  if (fs) fs.value = '';
  State.filterProduce = '';
  State.filterStatus  = '';
  State.page = 1;
  loadHistory();
}

// =============================================================================
// Init
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
  // Initial data load
  loadHistory();
  loadStats();

  // Connect WebSocket
  connectWebSocket();

  // Filter listeners
  const applyBtn = $('btn-apply-filter');
  const clearBtn = $('btn-clear-filter');
  if (applyBtn) applyBtn.addEventListener('click', applyFilters);
  if (clearBtn) clearBtn.addEventListener('click', clearFilters);

  // Enter key on filter input
  const fp = $('filter-produce');
  if (fp) fp.addEventListener('keydown', e => { if (e.key === 'Enter') applyFilters(); });

  // Auto-refresh stats every 30 seconds
  setInterval(loadStats, 30_000);

  console.log('[AgriScan 360] Dashboard initialized ✓');
});
