var TOKEN = '';
var machinesData = [];
var currentTemplate = 'grid';
var refreshInterval = null;
var checkedUsers = {};
var checkedProcs = {};
var checkedMachines = {};
var currentLayoutId = 'default';
var layoutsData = [];

function initDashboard(username) {
  TOKEN = getToken();
  loadLayouts();
  changeTemplate('grid');
  refreshAll();
  refreshInterval = setInterval(refreshAll, 10000);
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
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN }
  };
  if (body) opts.body = JSON.stringify(body);
  return fetch('/api' + path, opts).then(function(r) { return r.json(); });
}

function refreshAll() {
  console.log('refreshAll chamado');
  console.log('TOKEN:', TOKEN);
  api('GET', '/dashboard/all').then(function(data) {
    machinesData = data.machines || [];
    console.log('Máquinas carregadas:', machinesData.length);
    updateOverview();
    updateMachineFilter();
    initMachinesSection();
    updatePerMachineFilters();
    renderDashboard();
  }).catch(function(err) {
    console.error('Erro ao carregar dados:', err);
  });
}

function updateOverview() {
  var total = machinesData.length;
  var online = machinesData.filter(function(m) { return m.status === 'online'; }).length;
  var offline = total - online;
  var cpuSum = 0, memSum = 0, count = 0;
  machinesData.forEach(function(m) {
    if (m.status === 'online' && m.cpu) {
      cpuSum += m.cpu.total || 0;
      memSum += m.memory ? (m.memory.percent || 0) : 0;
      count++;
    }
  });
  document.getElementById('statTotal').textContent = total;
  document.getElementById('statOnline').textContent = online;
  document.getElementById('statOffline').textContent = offline;
  document.getElementById('statAvgCPU').textContent = count > 0 ? Math.round(cpuSum / count) + '%' : '0%';
  document.getElementById('statAvgMem').textContent = count > 0 ? Math.round(memSum / count) + '%' : '0%';
}

function updateMachineFilter() {
  var container = document.getElementById('machineFilter');
  var html = '';
  machinesData.forEach(function(m) {
    var mid = m.machine.id;
    if (!(mid in checkedMachines)) checkedMachines[mid] = true;
    var chk = checkedMachines[mid] ? ' checked' : '';
    html += '<label class="filter-item"><input type="checkbox" class="machine-cb"' + chk + ' onchange="toggleMachine(this)" data-machine="' + mid + '"> ' + m.machine.name + '</label>';
  });
  container.innerHTML = html;
  var countEl = document.getElementById('machineCount');
  if (countEl) countEl.textContent = machinesData.length + ' total';
}

function toggleMachine(cb) {
  checkedMachines[parseInt(cb.dataset.machine)] = cb.checked;
  applyFilters();
}

function toggleAllMachines(val) {
  var cbs = document.querySelectorAll('.machine-cb');
  cbs.forEach(function(cb) {
    cb.checked = val;
    checkedMachines[parseInt(cb.dataset.machine)] = val;
  });
  applyFilters();
}

function toggleMachinesSection() {
  var container = document.getElementById('machinesListContainer');
  var icon = document.getElementById('machinesExpandIcon');
  var isHidden = container.style.maxHeight === '0px';
  if (isHidden) {
    container.style.maxHeight = container.scrollHeight + 'px';
    icon.textContent = '▼';
  } else {
    container.style.maxHeight = '0px';
    icon.textContent = '▶';
  }
  localStorage.setItem('machinesCollapsed', isHidden ? '0' : '1');
}

function initMachinesSection() {
  var collapsed = localStorage.getItem('machinesCollapsed') === '1';
  var container = document.getElementById('machinesListContainer');
  var icon = document.getElementById('machinesExpandIcon');
  if (collapsed) {
    container.style.maxHeight = '0px';
    icon.textContent = '▶';
  } else {
    container.style.maxHeight = container.scrollHeight + 'px';
    icon.textContent = '▼';
  }
  var countEl = document.getElementById('machineCount');
  if (countEl && machinesData.length > 0) {
    countEl.textContent = machinesData.length + ' total';
  }
}

function updatePerMachineFilters() {
  machinesData.forEach(function(m) {
    var mid = m.machine.id;
    var key = 'm' + mid;

    if (!(key in checkedUsers)) checkedUsers[key] = {};
    if (!(key in checkedProcs)) checkedProcs[key] = {};

    var processes = m.processlist || [];
    var users = {};
    var procs = {};
    processes.forEach(function(p) {
      var u = p.username || 'N/A';
      var n = p.name || '?';
      users[u] = (users[u] || 0) + 1;
      procs[n] = (procs[n] || 0) + 1;
    });
    Object.keys(users).forEach(function(u) {
      if (!(u in checkedUsers[key])) checkedUsers[key][u] = true;
    });
    Object.keys(procs).forEach(function(p) {
      if (!(p in checkedProcs[key])) checkedProcs[key][p] = true;
    });
  });
}

function toggleExpand(key) {
  var body = document.getElementById('body_' + key);
  var icon = document.getElementById('icon_' + key);
  var isHidden = body.style.display === 'none';
  body.style.display = isHidden ? 'block' : 'none';
  icon.textContent = isHidden ? '▼' : '▶';
  localStorage.setItem('expand_' + key, isHidden ? '1' : '0');
}

function togglePerMachineItem(key, type, name, checked) {
  if (type === 'user') checkedUsers[key][name] = checked;
  else checkedProcs[key][name] = checked;
  applyFilters();
}

function toggleAllPerMachine(key, type, val) {
  var map = type === 'user' ? checkedUsers[key] : checkedProcs[key];
  Object.keys(map).forEach(function(k) { map[k] = val; });
  updatePerMachineFilters();
  applyFilters();
}

function filterItems(key, type, query) {
  var container = document.getElementById('items_' + key + '_' + type);
  if (!container) return;
  var q = query.toLowerCase();
  var labels = container.querySelectorAll('.filter-item');
  labels.forEach(function(lbl) {
    var name = lbl.getAttribute('data-name') || '';
    lbl.style.display = name.indexOf(q) !== -1 ? '' : 'none';
  });
}

function toggleAllPerMachineGlobal(type, val) {
  Object.keys(checkedUsers).forEach(function(key) {
    if (type === 'user') {
      Object.keys(checkedUsers[key]).forEach(function(k) { checkedUsers[key][k] = val; });
    }
  });
  Object.keys(checkedProcs).forEach(function(key) {
    if (type === 'proc') {
      Object.keys(checkedProcs[key]).forEach(function(k) { checkedProcs[key][k] = val; });
    }
  });
  updatePerMachineFilters();
  applyFilters();
}

function applyFilters() {
  renderDashboard();
}

function getFilteredMachines() {
  var showCPU = document.getElementById('filterCPU').checked;
  var showMem = document.getElementById('filterMem').checked;
  var showDisk = document.getElementById('filterDisk').checked;
  var showNet = document.getElementById('filterNet').checked;
  var showProc = document.getElementById('filterProc').checked;
  var sortBy = document.getElementById('sortBy').value;
  var filtered = machinesData.filter(function(m) {
    return checkedMachines[m.machine.id];
  });
  filtered.sort(function(a, b) {
    if (sortBy === 'name') return a.machine.name.localeCompare(b.machine.name);
    if (sortBy === 'cpu') return ((b.cpu ? b.cpu.total : 0) || 0) - ((a.cpu ? a.cpu.total : 0) || 0);
    if (sortBy === 'mem') return ((b.memory ? b.memory.percent : 0) || 0) - ((a.memory ? a.memory.percent : 0) || 0);
    if (sortBy === 'status') return (b.status === 'online' ? 1 : 0) - (a.status === 'online' ? 1 : 0);
    return 0;
  });
  return { machines: filtered, showCPU: showCPU, showMem: showMem, showDisk: showDisk, showNet: showNet, showProc: showProc };
}

function renderDashboard() {
  var f = getFilteredMachines();
  var grid = document.getElementById('dashboardGrid');
  grid.className = 'dashboard-grid view-' + currentTemplate;
  var html = '';
  f.machines.forEach(function(m) {
    html += renderMachineCard(m, f);
  });
  grid.innerHTML = html || '<p style="color:var(--text-muted);text-align:center;grid-column:1/-1;">' + t('dashboard.no_machines') + '</p>';
}

function pctClass(val) {
  if (val >= 90) return 'critical';
  if (val >= 70) return 'warning';
  return 'normal';
}

function renderMachineCard(m, filters) {
  var isOffline = m.status !== 'online';
  var cpuTotal = m.cpu ? (m.cpu.total || 0) : 0;
  var memPercent = m.memory ? (m.memory.percent || 0) : 0;
  var memTotal = m.memory ? (m.memory.total || 0) : 0;
  var memUsed = m.memory ? (m.memory.used || 0) : 0;
  var load = m.load ? m.load : {};
  var uptime = m.uptime ? m.uptime : {};
  var disks = m.disk || [];
  var networks = m.network || [];
  var processes = m.processlist || [];
  var hostname = m.system ? (m.system.hostname || m.machine.name) : m.machine.name;
  var displayName = m.machine.name + (m.system && m.system.hostname ? ' — ' + m.system.hostname : '');
  var mid = m.machine.id;
  var key = 'm' + mid;

  var html = '<div class="machine-card ' + (isOffline ? 'offline' : '') + '">';
  html += '<div class="card-header"><h4><span class="status-dot ' + (isOffline ? 'offline' : 'online') + '"></span>' + displayName + '</h4>';
  html += '<div style="display:flex;align-items:center;gap:0.5rem">';
  html += '<span style="font-size:0.75rem;color:var(--text-muted)">' + m.machine.host + '</span>';
  if (!isOffline && processes.length > 0) {
    html += '<button class="card-filter-btn" onclick="openFilterModal(' + mid + ')" title="Filtrar processos">⚙ ' + t('machine.filters') + '</button>';
  }
  html += '</div></div>';
  html += '<div class="card-body">';

  if (isOffline) {
    html += '<p style="text-align:center;color:var(--text-muted);padding:1rem;">' + t('dashboard.offline') + '</p></div></div>';
    return html;
  }

  html += '<div class="metric-grid">';

  if (filters.showCPU) {
    html += '<div class="metric-item"><span class="metric-label">CPU</span>';
    html += '<span class="metric-value ' + pctClass(cpuTotal) + '">' + Math.round(cpuTotal) + '%</span>';
    html += '<div class="progress-bar"><div class="progress-fill ' + pctClass(cpuTotal) + '" style="width:' + cpuTotal + '%"></div></div></div>';
  }

  if (filters.showMem) {
    html += '<div class="metric-item"><span class="metric-label">' + t('machine.memory') + '</span>';
    html += '<span class="metric-value ' + pctClass(memPercent) + '">' + Math.round(memPercent) + '%</span>';
    html += '<div class="progress-bar"><div class="progress-fill ' + pctClass(memPercent) + '" style="width:' + memPercent + '%"></div></div>';
    html += '<span style="font-size:0.7rem;color:var(--text-muted)">' + formatBytes(memUsed) + ' / ' + formatBytes(memTotal) + '</span></div>';
  }

  if (filters.showMem && uptime) {
    var ut = uptime.uptime || 0;
    html += '<div class="metric-item"><span class="metric-label">' + t('machine.uptime') + '</span>';
    html += '<span class="metric-value" style="font-size:0.85rem">' + formatUptime(ut) + '</span></div>';
  }

  if (filters.showDisk && disks.length > 0) {
    html += '</div><div style="margin-top:0.75rem"><span class="metric-label">' + t('machine.disks') + '</span>';
    disks.forEach(function(d) {
      var dp = d.percent || 0;
      html += '<div style="display:flex;align-items:center;gap:0.5rem;margin:0.2rem 0;font-size:0.8rem">';
      html += '<span style="width:120px;color:var(--text-secondary)">' + (d.device_name || d.mnt_point || '') + '</span>';
      html += '<div class="progress-bar" style="flex:1"><div class="progress-fill ' + pctClass(dp) + '" style="width:' + dp + '%"></div></div>';
      html += '<span style="width:40px;text-align:right;color:var(--text-muted)">' + Math.round(dp) + '%</span></div>';
    });
    html += '</div>';
  }

  if (filters.showNet && networks.length > 0) {
    html += '<div style="margin-top:0.75rem"><span class="metric-label">' + t('machine.network') + '</span>';
    networks.forEach(function(n) {
      if (n.interface_name && n.interface_name !== 'lo') {
        html += '<div style="font-size:0.75rem;color:var(--text-secondary);margin:0.15rem 0">';
        html += n.interface_name + ': ▼' + formatBytes(n.bytes_recv || 0) + ' ▲' + formatBytes(n.bytes_sent || 0) + '</div>';
      }
    });
    html += '</div>';
  }

  html += '</div>';

  if (filters.showProc && processes.length > 0) {
    var machineUsers = checkedUsers[key] || {};
    var machineProcs = checkedProcs[key] || {};
    var filteredProcs = processes.filter(function(p) {
      var u = p.username || 'N/A';
      var n = p.name || '?';
      return machineUsers[u] && machineProcs[n];
    });
    var topProcs = filteredProcs.slice(0, 10);
    var cpuCount = (m.cpu && m.cpu.cpucore) || 1;
    html += '<div style="margin-top:0.75rem"><span class="metric-label">' + t('machine.processes') + ' (' + filteredProcs.length + ' de ' + processes.length + ')</span>';
    html += '<table class="process-table"><thead><tr><th>' + t('machine.name') + '</th><th>' + t('machine.user') + '</th><th>' + t('machine.cpu_pct') + '</th><th>' + t('machine.mem_pct') + '</th></tr></thead><tbody>';
    topProcs.forEach(function(p) {
      var cpuNorm = Math.round((p.cpu_percent || 0) / cpuCount * 10) / 10;
      html += '<tr><td title="' + (p.cmdline || '') + '">' + (p.name || '?') + '</td>';
      html += '<td>' + (p.username || '-') + '</td>';
      html += '<td>' + cpuNorm + '</td>';
      html += '<td>' + (p.memory_percent || 0) + '</td></tr>';
    });
    html += '</tbody></table></div>';
  }

  html += '</div></div>';
  return html;
}

function formatBytes(b) {
  if (b === 0) return '0 B';
  var k = 1024;
  var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  var i = Math.floor(Math.log(b) / Math.log(k));
  return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatUptime(s) {
  var d = Math.floor(s / 86400);
  var h = Math.floor((s % 86400) / 3600);
  var m = Math.floor((s % 3600) / 60);
  if (d > 0) return d + 'd ' + h + 'h';
  if (h > 0) return h + 'h ' + m + 'm';
  return m + 'm';
}

function changeTemplate(tpl) {
  currentTemplate = tpl;
  renderDashboard();
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

function getCurrentConfig() {
  return {
    template: currentTemplate,
    display: {
      cpu: document.getElementById('filterCPU').checked,
      mem: document.getElementById('filterMem').checked,
      disk: document.getElementById('filterDisk').checked,
      net: document.getElementById('filterNet').checked,
      proc: document.getElementById('filterProc').checked,
    },
    sortBy: document.getElementById('sortBy').value,
    machines: JSON.parse(JSON.stringify(checkedMachines)),
    users: JSON.parse(JSON.stringify(checkedUsers)),
    procs: JSON.parse(JSON.stringify(checkedProcs)),
  };
}

function applyConfig(cfg) {
  if (!cfg) return;
  if (cfg.template) {
    currentTemplate = cfg.template;
    document.getElementById('templateSelector').value = cfg.template;
  }
  if (cfg.display) {
    document.getElementById('filterCPU').checked = cfg.display.cpu !== false;
    document.getElementById('filterMem').checked = cfg.display.mem !== false;
    document.getElementById('filterDisk').checked = cfg.display.disk !== false;
    document.getElementById('filterNet').checked = cfg.display.net !== false;
    document.getElementById('filterProc').checked = cfg.display.proc !== false;
  }
  if (cfg.sortBy) document.getElementById('sortBy').value = cfg.sortBy;
  if (cfg.machines) {
    Object.keys(cfg.machines).forEach(function(k) { checkedMachines[k] = cfg.machines[k]; });
    var mcbs = document.querySelectorAll('.machine-cb');
    mcbs.forEach(function(cb) {
      var mid = parseInt(cb.dataset.machine);
      if (mid in checkedMachines) cb.checked = checkedMachines[mid];
    });
  }
  if (cfg.users) {
    Object.keys(cfg.users).forEach(function(k) { checkedUsers[k] = cfg.users[k]; });
  }
  if (cfg.procs) {
    Object.keys(cfg.procs).forEach(function(k) { checkedProcs[k] = cfg.procs[k]; });
  }
  updatePerMachineFilters();
  applyFilters();
}

function loadLayouts() {
  api('GET', '/dashboard/layouts').then(function(data) {
    layoutsData = data || [];
    var sel = document.getElementById('layoutSelector');
    sel.innerHTML = '';
    var defOpt = document.createElement('option');
    defOpt.value = 'default';
    defOpt.textContent = 'Default ★';
    if (currentLayoutId === 'default') defOpt.selected = true;
    sel.appendChild(defOpt);
    layoutsData.forEach(function(l) {
      var opt = document.createElement('option');
      opt.value = l.id;
      opt.textContent = l.name + (l.is_default ? ' ★' : '');
      if (l.id == currentLayoutId) opt.selected = true;
      sel.appendChild(opt);
    });
  });
}

function loadLayout(id) {
  if (id === 'default') {
    currentLayoutId = 'default';
    checkedUsers = {};
    checkedProcs = {};
    checkedMachines = {};
    document.getElementById('filterCPU').checked = true;
    document.getElementById('filterMem').checked = true;
    document.getElementById('filterDisk').checked = true;
    document.getElementById('filterNet').checked = true;
    document.getElementById('filterProc').checked = true;
    document.getElementById('sortBy').value = 'name';
    refreshAll();
    return;
  }
  var layout = layoutsData.find(function(l) { return l.id == id; });
  if (!layout) return;
  currentLayoutId = layout.id;
  try {
    var cfg = JSON.parse(layout.config);
    applyConfig(cfg);
    refreshAll();
  } catch(e) {
    console.error('Erro ao carregar layout:', e);
  }
}

function saveCurrentLayout() {
  document.getElementById('layoutNameInput').value = '';
  document.getElementById('layoutActionSelect').value = 'new';
  toggleLayoutNameInput();

  var updateSel = document.getElementById('layoutUpdateSelect');
  updateSel.innerHTML = '';
  layoutsData.forEach(function(l) {
    var opt = document.createElement('option');
    opt.value = l.id;
    opt.textContent = l.name;
    if (l.id == currentLayoutId) opt.selected = true;
    updateSel.appendChild(opt);
  });

  var baseSel = document.getElementById('layoutBaseSelect');
  baseSel.innerHTML = '<option value="">' + t('layouts.copy_empty') + '</option><option value="__current__">' + t('layouts.use_current') + '</option>';
  layoutsData.forEach(function(l) {
    if (String(l.id) !== String(currentLayoutId)) {
      var opt = document.createElement('option');
      opt.value = l.id;
      opt.textContent = l.name;
      baseSel.appendChild(opt);
    }
  });
  baseSel.value = currentLayoutId !== 'default' ? currentLayoutId : '';

  document.getElementById('layoutModal').style.display = 'flex';
  document.getElementById('layoutNameInput').focus();
}

function toggleLayoutNameInput() {
  var action = document.getElementById('layoutActionSelect').value;
  document.getElementById('layoutNameInput').style.display = action === 'new' ? 'block' : 'none';
  document.getElementById('layoutUpdateSelect').style.display = action === 'update' ? 'block' : 'none';
}

function closeLayoutModal(e) {
  if (!e || e.target === document.getElementById('layoutModal')) {
    document.getElementById('layoutModal').style.display = 'none';
  }
}

function confirmSaveLayout() {
  var action = document.getElementById('layoutActionSelect').value;
  var baseVal = document.getElementById('layoutBaseSelect').value;
  var cfg;
  if (baseVal === '__current__' || baseVal === '') {
    cfg = getCurrentConfig();
  } else {
    var baseLayout = layoutsData.find(function(l) { return String(l.id) === baseVal; });
    if (baseLayout) {
      try { cfg = JSON.parse(baseLayout.config); } catch(e) { cfg = getCurrentConfig(); }
    } else {
      cfg = getCurrentConfig();
    }
  }

  if (action === 'update') {
    var selId = document.getElementById('layoutUpdateSelect').value;
    if (!selId) return;
    api('PUT', '/dashboard/layouts/' + selId, { name: '', config: JSON.stringify(cfg) }).then(function(res) {
      document.getElementById('layoutModal').style.display = 'none';
      if (res.message) {
        loadLayouts();
      } else {
        alert(res.detail || 'Erro ao atualizar');
      }
    });
  } else {
    var name = document.getElementById('layoutNameInput').value.trim();
    if (!name) return;
    api('POST', '/dashboard/layouts', { name: name, config: JSON.stringify(cfg) }).then(function(res) {
      document.getElementById('layoutModal').style.display = 'none';
      if (res.id) {
        currentLayoutId = res.id;
        loadLayouts();
      } else {
        alert(res.detail || 'Erro ao salvar');
      }
    });
  }
}

function deleteCurrentLayout() {
  if (currentLayoutId === 'default') {
    alert('Não é possível excluir o layout padrão');
    return;
  }
  if (!confirm('Excluir este layout?')) return;
  api('DELETE', '/dashboard/layouts/' + currentLayoutId).then(function(res) {
    if (res.message) {
      currentLayoutId = 'default';
      loadLayouts();
      loadLayout('default');
    } else {
      alert(res.detail || 'Erro ao excluir');
    }
  });
}

/* ============================================================
   FILTER MODAL (per-machine)
   ============================================================ */
function openFilterModal(machineId) {
  var m = machinesData.find(function(d) { return d.machine.id === machineId; });
  if (!m) return;
  var key = 'm' + machineId;
  var processes = m.processlist || [];

  if (!(key in checkedUsers)) checkedUsers[key] = {};
  if (!(key in checkedProcs)) checkedProcs[key] = {};

  var users = {};
  var procs = {};
  processes.forEach(function(p) {
    var u = p.username || 'N/A';
    var n = p.name || '?';
    users[u] = (users[u] || 0) + 1;
    procs[n] = (procs[n] || 0) + 1;
  });
  Object.keys(users).forEach(function(u) {
    if (!(u in checkedUsers[key])) checkedUsers[key][u] = true;
  });
  Object.keys(procs).forEach(function(p) {
    if (!(p in checkedProcs[key])) checkedProcs[key][p] = true;
  });

  var hostname = m.system ? (m.system.hostname || m.machine.name) : m.machine.name;
  var displayName = m.machine.name + (m.system && m.system.hostname ? ' — ' + m.system.hostname : '');

  var modal = document.createElement('div');
  modal.className = 'filter-modal-overlay';
  modal.id = 'filterModal';
  modal.onclick = function(e) { if (e.target === modal) closeFilterModal(); };

  var html = '<div class="filter-modal">';
  html += '<h3>⚙ ' + t('filter_modal.title') + ' — ' + displayName + '</h3>';

  html += '<div class="filter-modal-section">';
   html += '<h4>' + t('filter_modal.users') + '<span>';
  html += '<button class="btn-filter-action" onclick="modalToggleAll(\'' + key + '\',\'user\',true)">' + t('filter_modal.toggle_all') + '</button> ';
  html += '<button class="btn-filter-action" onclick="modalToggleAll(\'' + key + '\',\'user\',false)">' + t('common.none') + '</button>';
  html += '</span></h4>';
  html += '<input type="text" class="filter-search" placeholder="' + t('filter_modal.search_user') + '... oninput="modalFilterList(this,\'user-list\')" style="width:100%;margin-bottom:0.3rem">';
  html += '<div class="filter-modal-list" id="user-list">';
  Object.keys(users).sort().forEach(function(u) {
    var chk = checkedUsers[key][u] ? ' checked' : '';
    html += '<label class="filter-modal-item" data-name="' + u.toLowerCase() + '">';
    html += '<input type="checkbox"' + chk + ' onchange="modalToggleItem(\'' + key + '\',\'user\',\'' + u.replace(/'/g, "\\'") + '\',this.checked)"> ';
    html += u + ' <span class="filter-count">(' + users[u] + ')</span></label>';
  });
  html += '</div></div>';

  html += '<div class="filter-modal-section">';
  html += '<h4>' + t('filter_modal.processes') + '<span>';
  html += '<button class="btn-filter-action" onclick="modalToggleAll(\'' + key + '\',\'proc\',true)">' + t('filter_modal.toggle_all') + '</button> ';
  html += '<button class="btn-filter-action" onclick="modalToggleAll(\'' + key + '\',\'proc\',false)">' + t('common.none') + '</button>';
  html += '</span></h4>';
  html += '<input type="text" class="filter-search" placeholder="' + t('filter_modal.search_proc') + '... oninput="modalFilterList(this,\'proc-list\')" style="width:100%;margin-bottom:0.3rem">';
  html += '<div class="filter-modal-list" id="proc-list">';
  Object.keys(procs).sort().forEach(function(p) {
    var chk = checkedProcs[key][p] ? ' checked' : '';
    var safeName = p.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    html += '<label class="filter-modal-item" data-name="' + p.toLowerCase() + '">';
    html += '<input type="checkbox"' + chk + ' onchange="modalToggleItem(\'' + key + '\',\'proc\',\'' + safeName + '\',this.checked)"> ';
    html += p + ' <span class="filter-count">(' + procs[p] + ')</span></label>';
  });
  html += '</div></div>';

  html += '<div class="filter-modal-actions">';
  html += '<button class="btn-secondary" onclick="closeFilterModal()">' + t('filter_modal.cancel') + '</button>';
  html += '</div></div>';

  modal.innerHTML = html;
  document.body.appendChild(modal);
}

function closeFilterModal() {
  var m = document.getElementById('filterModal');
  if (m) m.remove();
}

function modalToggleItem(key, type, name, checked) {
  if (type === 'user') checkedUsers[key][name] = checked;
  else checkedProcs[key][name] = checked;
  applyFilters();
}

function modalToggleAll(key, type, val) {
  var map = type === 'user' ? checkedUsers[key] : checkedProcs[key];
  Object.keys(map).forEach(function(k) { map[k] = val; });
  var listId = type === 'user' ? 'user-list' : 'proc-list';
  var list = document.getElementById(listId);
  if (list) {
    list.querySelectorAll('input[type="checkbox"]').forEach(function(cb) { cb.checked = val; });
  }
  applyFilters();
}

function modalFilterList(input, listId) {
  var list = document.getElementById(listId);
  if (!list) return;
  var q = input.value.toLowerCase();
  list.querySelectorAll('.filter-modal-item').forEach(function(lbl) {
    var name = lbl.getAttribute('data-name') || '';
    lbl.style.display = name.indexOf(q) !== -1 ? '' : 'none';
  });
}
