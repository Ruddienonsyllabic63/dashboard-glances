/* logs.js v2 */
var TOKEN = '';
var logsChart = null;
var currentPage = 1;
var searchTimer = null;

function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.getElementById(tabId).classList.add('active');
  event.target.classList.add('active');
}

function initLogs() {
  TOKEN = getToken();
  loadMonitorConfig();
  loadMonitorMachines();
  loadLogs();
}

function getToken() {
  var stored = localStorage.getItem('token');
  if (stored) return stored;
  var parts = document.cookie.split(';');
  for (var i = 0; i < parts.length; i++) {
    var c = parts[i].trim();
    if (c.startsWith('token=')) return c.substring(6);
  }
  return '';
}

function api(method, path, body) {
  var opts = {
    method: method,
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN }
  };
  if (body) opts.body = JSON.stringify(body);
  return fetch('/api' + path, opts).then(function(r) { return r.json(); });
}

function loadMonitorConfig() {
  api('GET', '/monitor/config').then(function(cfg) {
    document.getElementById('monitorInterval').value = cfg.interval_minutes || 5;
    document.getElementById('monitorRetention').value = cfg.retention_months || 3;
    document.getElementById('monitorEnabled').checked = cfg.enabled !== false;
    document.getElementById('mCPU').checked = cfg.collect_cpu !== false;
    document.getElementById('mMEM').checked = cfg.collect_mem !== false;
    document.getElementById('mDISK').checked = cfg.collect_disk !== false;
    document.getElementById('mLOAD').checked = cfg.collect_load !== false;
    document.getElementById('mPROCS').checked = cfg.collect_procs !== false;
    document.getElementById('monitorThreshold').value = cfg.process_threshold || 0;
    document.getElementById('monitorPerUserThreshold').value = cfg.per_user_threshold || 0;
    document.getElementById('cpuThreshold').value = cfg.cpu_threshold || 90;
    document.getElementById('memThreshold').value = cfg.mem_threshold || 90;
    document.getElementById('diskThreshold').value = cfg.disk_threshold || 90;
    document.getElementById('gpuThreshold').value = cfg.gpu_threshold || 90;
    document.getElementById('alertCpu').checked = cfg.alert_cpu !== false;
    document.getElementById('alertMem').checked = cfg.alert_mem !== false;
    document.getElementById('alertDisk').checked = cfg.alert_disk !== false;
    document.getElementById('alertGpu').checked = cfg.alert_gpu !== false;
    document.getElementById('alertProcess').checked = cfg.alert_process !== false;
    document.getElementById('alertPerUser').checked = cfg.alert_per_user !== false;

    var selectedUsers = cfg.per_user_names || [];
    window._perUserSelected = selectedUsers;
    renderPerUserList();
    loadDetectedUsers(selectedUsers);

    try {
      var selected = JSON.parse(cfg.selected_machines || '[]');
      var cbs = document.querySelectorAll('.monitor-machine-cb');
      cbs.forEach(function(cb) {
        cb.checked = selected.length === 0 || selected.indexOf(parseInt(cb.dataset.id)) !== -1;
      });
    } catch(e) {}
  });
}

function renderPerUserList() {
  var container = document.getElementById('perUserCheckboxes');
  container.innerHTML = '';
  (window._perUserSelected || []).forEach(function(u) {
    container.innerHTML += '<label class="toggle" style="display:inline-flex;align-items:center;gap:0.3rem"><input type="checkbox" checked onchange="togglePerUser(this, \'' + u.replace(/'/g, "\\'") + '\')"><span class="toggle-track"></span><span class="toggle-label">' + u + '</span> <span style="cursor:pointer;color:var(--red);font-size:0.85rem" onclick="removePerUser(\'' + u.replace(/'/g, "\\'") + '\')" title="Remover">✕</span></label>';
  });
}

function loadDetectedUsers(selected) {
  api('GET', '/monitor/detected-users').then(function(users) {
    var container = document.getElementById('perUserDetected');
    if (!container) return;
    container.innerHTML = '';
    var selectedArray = Array.isArray(selected) ? selected : [];
    if (users.length === 0) {
      container.innerHTML = '<span style="font-size:0.8rem;color:var(--text-muted)">Nenhum usuário detectado nos logs</span>';
      return;
    }
    users.forEach(function(u) {
      var already = selectedArray.indexOf(u) !== -1;
      var style = already ? 'opacity:0.5;text-decoration:line-through' : '';
      container.innerHTML += '<label class="toggle" style="' + style + '"><input type="checkbox" ' + (already ? 'checked disabled' : '') + ' onchange="addDetectedUser(\'' + u.replace(/'/g, "\\'") + '\')"><span class="toggle-track"></span><span class="toggle-label">' + u + '</span></label>';
    });
  });
}

function togglePerUser(cb, username) {
  if (!window._perUserSelected) window._perUserSelected = [];
  if (cb.checked) {
    window._perUserSelected.push(username);
  } else {
    window._perUserSelected = window._perUserSelected.filter(function(u) { return u !== username; });
  }
}

function addPerUserCustom() {
  var input = document.getElementById('perUserCustom');
  var name = input.value.trim();
  if (!name) return;
  if (!window._perUserSelected) window._perUserSelected = [];
  if (window._perUserSelected.indexOf(name) === -1) {
    window._perUserSelected.push(name);
    renderPerUserList();
    loadDetectedUsers(window._perUserSelected);
  }
  input.value = '';
}

function removePerUser(username) {
  window._perUserSelected = (window._perUserSelected || []).filter(function(u) { return u !== username; });
  renderPerUserList();
  loadDetectedUsers(window._perUserSelected);
}

function addDetectedUser(username) {
  if (!window._perUserSelected) window._perUserSelected = [];
  if (window._perUserSelected.indexOf(username) === -1) {
    window._perUserSelected.push(username);
    renderPerUserList();
    loadDetectedUsers(window._perUserSelected);
  }
}

function saveMonitorConfig() {
  var result = document.getElementById('monitorConfigResult');
  var cfg = {
    per_user_threshold: parseInt(document.getElementById('monitorPerUserThreshold').value) || 0,
    per_user_names: window._perUserSelected || [],
    cpu_threshold: parseInt(document.getElementById('cpuThreshold').value) || 90,
    mem_threshold: parseInt(document.getElementById('memThreshold').value) || 90,
    disk_threshold: parseInt(document.getElementById('diskThreshold').value) || 90,
    gpu_threshold: parseInt(document.getElementById('gpuThreshold').value) || 90,
    alert_cpu: document.getElementById('alertCpu').checked,
    alert_mem: document.getElementById('alertMem').checked,
    alert_disk: document.getElementById('alertDisk').checked,
    alert_gpu: document.getElementById('alertGpu').checked,
    alert_process: document.getElementById('alertProcess').checked,
    alert_per_user: document.getElementById('alertPerUser').checked,
  };
  api('PUT', '/monitor/config', cfg).then(function(res) {
    if (res.message) {
      result.style.color = 'var(--green)';
      result.textContent = res.message;
      setTimeout(function() { result.textContent = ''; }, 3000);
    } else {
      result.style.color = 'var(--red)';
      result.textContent = res.detail || 'Erro';
    }
  });
}

function loadMonitorMachines() {
  api('GET', '/monitor/machines').then(function(data) {
    var list = document.getElementById('monitorMachineList');
    var sel = document.getElementById('logMachineFilter');
    (data || []).forEach(function(m) {
      list.innerHTML += '<label class="toggle"><input type="checkbox" class="monitor-machine-cb" data-id="' + m.id + '" checked><span class="toggle-track"></span><span class="toggle-label">' + m.name + '</span></label>';
      var opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      sel.appendChild(opt);
    });
    loadMonitorConfig();
  });
}

function saveMonitorSelection() {
  var result = document.getElementById('selectResult');
  var machines = [];
  document.querySelectorAll('.monitor-machine-cb:checked').forEach(function(cb) {
    machines.push(parseInt(cb.dataset.id));
  });
  var cfg = {
    selected_machines: machines,
    collect_cpu: document.getElementById('mCPU').checked,
    collect_mem: document.getElementById('mMEM').checked,
    collect_disk: document.getElementById('mDISK').checked,
    collect_load: document.getElementById('mLOAD').checked,
    collect_procs: document.getElementById('mPROCS').checked,
  };
  api('PUT', '/monitor/config', cfg).then(function(res) {
    if (res.message) {
      result.style.color = 'var(--green)';
      result.textContent = 'Seleção salva! ' + machines.length + ' máquina(s), ' +
        [cfg.collect_cpu?'CPU':'', cfg.collect_mem?'Mem':'', cfg.collect_disk?'Disco':'', cfg.collect_load?'Load':'', cfg.collect_procs?'Proc':''].filter(Boolean).join(', ');
    } else {
      result.style.color = 'var(--red)';
      result.textContent = res.detail || 'Erro';
    }
  });
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(function() {
    currentPage = 1;
    loadLogs();
  }, 400);
}

function loadLogs() {
  var machineId = document.getElementById('logMachineFilter').value;
  var dateFrom = document.getElementById('logDateFrom').value;
  var dateTo = document.getElementById('logDateTo').value;
  var alertsOnly = document.getElementById('logAlertsOnly').checked;
  var search = document.getElementById('logSearch').value.trim();
  var params = [];
  if (machineId) params.push('machine_id=' + machineId);
  if (dateFrom) params.push('date_from=' + dateFrom);
  if (dateTo) params.push('date_to=' + dateTo);
  if (alertsOnly) params.push('alerts_only=true');
  if (search) params.push('search=' + encodeURIComponent(search));
  params.push('page=' + currentPage);
  params.push('per_page=150');
  var qs = '?' + params.join('&');

  api('GET', '/monitor/logs' + qs).then(function(res) {
    var logs = res.logs || [];
    if (search) {
      var term = search.toLowerCase();
      logs = logs.filter(function(l) {
        try {
          var top = JSON.parse(l.top_procs || '[]');
          if (top.length > 0) {
            var first = top[0];
            return first.user.toLowerCase().indexOf(term) !== -1 ||
                   first.name.toLowerCase().indexOf(term) !== -1;
          }
        } catch(e) {}
        return false;
      });
    }
    renderLogsTable(logs);
    renderChart(logs);
    renderPagination(res.page, Math.ceil(res.total / 150), res.total);
  });

  var statsQs = machineId ? '?machine_id=' + machineId : '';
  api('GET', '/monitor/stats' + statsQs).then(function(s) {
    document.getElementById('statTotalLogs').textContent = s.total || 0;
    document.getElementById('statAvgCPU').textContent = (s.avg_cpu || 0) + '%';
    document.getElementById('statAvgMem').textContent = (s.avg_mem || 0) + '%';
    document.getElementById('statMaxCPU').textContent = (s.max_cpu || 0) + '%';
    document.getElementById('statAlerts').textContent = s.alerts || 0;
  });
}

function renderLogsTable(logs) {
  var tbody = document.getElementById('logsBody');
  if (!logs || logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">Nenhum registro encontrado</td></tr>';
    return;
  }
  var html = '';
  logs.forEach(function(l) {
    var dt = l.timestamp ? new Date(l.timestamp).toLocaleString('pt-BR') : '-';
    var procs = '';
    try {
      var top = JSON.parse(l.top_procs || '[]');
      if (top.length > 0) procs = top[0].user + ' → ' + top[0].name + ' (' + top[0].cpu + '%)';
    } catch(e) {}
    var alertClass = l.threshold_alert ? 'log-alert-row' : '';
    var alertBadge = l.threshold_alert ? '<span class="alert-badge">PROCS</span>' : '';
    html += '<tr class="' + alertClass + '">';
    html += '<td>' + dt + '</td>';
    html += '<td>' + l.machine_name + '</td>';
    html += '<td><span class="status-dot ' + l.status + '"></span>' + l.status + '</td>';
    html += '<td>' + (l.cpu_percent || '-') + '</td>';
    html += '<td>' + (l.mem_percent || '-') + '</td>';
    html += '<td>' + (l.load_1 || '-') + ' / ' + (l.load_5 || '-') + ' / ' + (l.load_15 || '-') + '</td>';
    html += '<td>' + (l.disk_root_percent || '-') + '</td>';
    html += '<td>' + (l.gpu_load || '-') + '</td>';
    html += '<td>' + (l.process_count || '-') + '</td>';
    html += '<td style="font-size:0.75rem">' + procs + '</td>';
    html += '<td>' + alertBadge + '</td>';
    html += '</tr>';
  });
  tbody.innerHTML = html;
}

function renderPagination(page, totalPages, total) {
  var info = document.getElementById('paginationInfo');
  var pag = document.getElementById('pagination');
  if (totalPages <= 1) {
    info.textContent = total + ' registro(s)';
    pag.innerHTML = '';
    return;
  }
  var start = (page - 1) * 150 + 1;
  var end = Math.min(page * 150, total);
  info.textContent = start + '-' + end + ' de ' + total;

  var html = '';
  if (page > 1) html += '<button class="btn-page" onclick="goPage(' + (page - 1) + ')">« Anterior</button>';

  var range = 2;
  var pStart = Math.max(1, page - range);
  var pEnd = Math.min(totalPages, page + range);
  if (pStart > 1) {
    html += '<button class="btn-page" onclick="goPage(1)">1</button>';
    if (pStart > 2) html += '<span class="btn-page-dots">...</span>';
  }
  for (var i = pStart; i <= pEnd; i++) {
    var cls = i === page ? 'btn-page active' : 'btn-page';
    html += '<button class="' + cls + '" onclick="goPage(' + i + ')">' + i + '</button>';
  }
  if (pEnd < totalPages) {
    if (pEnd < totalPages - 1) html += '<span class="btn-page-dots">...</span>';
    html += '<button class="btn-page" onclick="goPage(' + totalPages + ')">' + totalPages + '</button>';
  }

  if (page < totalPages) html += '<button class="btn-page" onclick="goPage(' + (page + 1) + ')">Próxima »</button>';
  pag.innerHTML = html;
}

function goPage(p) {
  currentPage = p;
  loadLogs();
  window.scrollTo({ top: document.getElementById('logsTable').offsetTop - 60, behavior: 'smooth' });
}

function renderChart(logs) {
  var ctx = document.getElementById('logsChart');
  if (logsChart) logsChart.destroy();
  if (!logs || logs.length === 0) return;

  var reversed = logs.slice().reverse();
  var labels = reversed.map(function(l) {
    return l.timestamp ? new Date(l.timestamp).toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'}) : '';
  });
  var cpuData = reversed.map(function(l) { return l.cpu_percent || 0; });
  var memData = reversed.map(function(l) { return l.mem_percent || 0; });
  var gpuData = reversed.map(function(l) { return l.gpu_load || 0; });

  logsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        { label: 'CPU %', data: cpuData, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.3, pointRadius: 0 },
        { label: 'Mem %', data: memData, borderColor: '#a855f7', backgroundColor: 'rgba(168,85,247,0.1)', fill: true, tension: 0.3, pointRadius: 0 },
        { label: 'GPU %', data: gpuData, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', fill: true, tension: 0.3, pointRadius: 0 },
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#94a3b8' } } },
      scales: {
        x: { ticks: { color: '#64748b', maxTicksLimit: 15 }, grid: { color: 'rgba(42,54,80,0.5)' } },
        y: { min: 0, max: 100, ticks: { color: '#64748b' }, grid: { color: 'rgba(42,54,80,0.5)' } }
      }
    }
  });
}

function forceCollect() {
  api('POST', '/monitor/collect').then(function(res) {
    alert(res.message || 'Coleta executada');
    loadLogs();
  });
}

function clearLogs() {
  if (!confirm('Limpar todos os logs de monitoramento?')) return;
  api('DELETE', '/monitor/logs').then(function(res) {
    alert(res.message);
    loadLogs();
  });
}
/* v2 */
1789564232
