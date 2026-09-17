var TOKEN = '';

function initSettings() {
  TOKEN = getToken();
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
  return fetch('/api' + path, opts).then(function(r) {
    if (!r.ok) return r.json().catch(function() { return { detail: 'Erro HTTP ' + r.status }; });
    return r.json();
  });
}

function loadSettings() {
  initSettings();
  loadMachines();
  if (IS_ADMIN) {
    loadUsers();
    loadBackups();
  }
}

function loadMachines() {
  api('GET', '/machines/').then(function(data) {
    var tbody = document.getElementById('machinesBody');
    var html = '';
    data.forEach(function(m) {
      html += '<tr>';
      html += '<td>' + m.name + '</td>';
      html += '<td>' + m.host + '</td>';
      html += '<td>' + m.port + '</td>';
      html += '<td><span class="status-dot ' + m.status + '"></span>' + m.status + '</td>';
      if (IS_ADMIN) {
        html += '<td><button class="btn-danger" onclick="deleteMachine(' + m.id + ')">Remover</button></td>';
      }
      html += '</tr>';
    });
    tbody.innerHTML = html || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Nenhuma máquina cadastrada</td></tr>';
  });
}

function addMachine() {
  var name = document.getElementById('machineName').value.trim();
  var host = document.getElementById('machineHost').value.trim();
  var port = parseInt(document.getElementById('machinePort').value) || 61208;
  var isLocal = document.getElementById('machineLocal').checked;
  var tags = document.getElementById('machineTags').value.trim();
  if (!name || !host) return alert('Nome e Host são obrigatórios');
  api('POST', '/machines/', { name: name, host: host, port: port, is_local: isLocal, tags: tags }).then(function(res) {
    document.getElementById('machineName').value = '';
    document.getElementById('machineHost').value = '';
    document.getElementById('machineTags').value = '';
    loadMachines();
  });
}

function testMachine() {
  var host = document.getElementById('machineHost').value.trim();
  var port = parseInt(document.getElementById('machinePort').value) || 61208;
  var name = document.getElementById('machineName').value.trim() || 'Teste';
  var result = document.getElementById('testResult');
  if (!host) {
    result.className = 'test-result error';
    result.textContent = 'Digite o IP ou hostname da máquina';
    return;
  }
  result.className = 'test-result';
  result.textContent = 'Testando conexão...';
  result.style.display = 'block';
  api('POST', '/machines/test', { name: name, host: host, port: port }).then(function(res) {
    if (res.alive) {
      result.className = 'test-result success';
      result.textContent = 'Conexão OK! ' + (res.system ? res.system.os_name + ' ' + res.system.os_version : '');
    } else {
      result.className = 'test-result error';
      result.textContent = 'Falha: ' + (res.error || 'Verifique IP/porta e firewall.');
    }
  }).catch(function(err) {
    result.className = 'test-result error';
    result.textContent = 'Erro de rede: ' + err.message;
  });
}

function deleteMachine(id) {
  if (!confirm('Remover esta máquina?')) return;
  api('DELETE', '/machines/' + id).then(function() { loadMachines(); });
}

function loadUsers() {
  api('GET', '/system/users').then(function(data) {
    var tbody = document.getElementById('usersBody');
    if (!tbody) return;
    var html = '';
    data.forEach(function(u) {
      html += '<tr>';
      html += '<td>' + u.username + '</td>';
      html += '<td>' + (u.full_name || '<span style="color:var(--text-muted)">-</span>') + '</td>';
      html += '<td>' + (u.email || '<span style="color:var(--text-muted)">-</span>') + '</td>';
      html += '<td>' + (u.telegram_username || '<span style="color:var(--text-muted)">-</span>') + '</td>';
      html += '<td><span class="role-badge ' + u.role + '">' + u.role + '</span></td>';
      html += '<td>';
      if (u.username !== 'admin') {
        html += '<select onchange="changeRole(' + u.id + ', this.value)" style="padding:0.2rem;background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;font-size:0.8rem">';
        html += '<option value="viewer"' + (u.role === 'viewer' ? ' selected' : '') + '>Visualizador</option>';
        html += '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>Admin</option>';
        html += '</select> ';
        html += '<button class="btn-danger" onclick="deleteUser(' + u.id + ', \'' + u.username + '\')">Remover</button>';
      } else {
        html += '<span style="color:var(--text-muted);font-size:0.8rem">Admin principal</span>';
      }
      html += '</td></tr>';
    });
    tbody.innerHTML = html;
  });
}

function addUser() {
  var username = document.getElementById('newUsername').value.trim();
  var password = document.getElementById('newPassword').value;
  var role = document.getElementById('newRole').value;
  var fullName = document.getElementById('newFullName').value.trim();
  var email = document.getElementById('newEmail').value.trim();
  var telegram = document.getElementById('newTelegram').value.trim();
  var result = document.getElementById('userActionResult');
  if (!username || !password) {
    result.className = 'test-result error';
    result.textContent = 'Usuário e senha são obrigatórios';
    return;
  }
  api('POST', '/auth/register', {
    username: username,
    password: password,
    role: role,
    full_name: fullName,
    email: email,
    telegram_username: telegram
  }).then(function(res) {
    if (res.message) {
      result.className = 'test-result success';
      result.textContent = res.message;
      document.getElementById('newUsername').value = '';
      document.getElementById('newPassword').value = '';
      document.getElementById('newFullName').value = '';
      document.getElementById('newEmail').value = '';
      document.getElementById('newTelegram').value = '';
      loadUsers();
    } else {
      result.className = 'test-result error';
      result.textContent = res.detail || 'Erro ao criar usuário';
    }
  });
}

function changeRole(userId, newRole) {
  api('PUT', '/auth/users/role', { user_id: userId, role: newRole }).then(function(res) {
    if (res.message) {
      loadUsers();
    } else {
      alert(res.detail || 'Erro ao alterar role');
    }
  });
}

function deleteUser(userId, username) {
  if (!confirm('Remover o usuário "' + username + '"?')) return;
  api('DELETE', '/auth/users/' + userId).then(function(res) {
    if (res.message) {
      loadUsers();
    } else {
      alert(res.detail || 'Erro ao remover usuário');
    }
  });
}

function createBackup() {
  api('POST', '/backup/create').then(function(res) {
    alert('Backup criado: ' + res.path);
    loadBackups();
  });
}

function loadBackups() {
  api('GET', '/backup/list').then(function(data) {
    var container = document.getElementById('backupList');
    if (!container) return;
    var html = '';
    (data.backups || []).forEach(function(b) {
      html += '<div class="backup-item"><span>' + b.name + '</span>';
      html += '<div style="display:flex;gap:0.5rem">';
      html += '<button class="btn-secondary" onclick="downloadBackup(\'' + b.name + '\')">Download</button>';
      html += '<button class="btn-secondary" onclick="restoreBackup(\'' + b.path + '\')">Restaurar</button>';
      html += '</div></div>';
    });
    container.innerHTML = html || '<p style="color:var(--text-muted)">Nenhum backup encontrado</p>';
  });
}

function downloadBackup(name) {
  window.location.href = '/api/backup/download?name=' + encodeURIComponent(name);
}

function restoreBackup(path) {
  if (!confirm('Restaurar este backup? Os dados atuais serão substituídos.')) return;
  api('POST', '/backup/restore?backup_path=' + encodeURIComponent(path)).then(function(res) {
    alert(res.message || 'Backup restaurado');
    loadMachines();
  });
}

function changePassword() {
  var oldP = document.getElementById('currentPassword').value;
  var newP = document.getElementById('changeNewPassword').value;
  var confirmP = document.getElementById('changeConfirmPassword').value;
  var result = document.getElementById('passwordResult');

  if (!oldP || !newP || !confirmP) {
    result.style.color = 'var(--red)';
    result.textContent = 'Preencha todos os campos';
    return;
  }
  if (newP !== confirmP) {
    result.style.color = 'var(--red)';
    result.textContent = 'As senhas novas não conferem';
    return;
  }
  if (newP.length < 4) {
    result.style.color = 'var(--red)';
    result.textContent = 'A nova senha deve ter no mínimo 4 caracteres';
    return;
  }

  api('POST', '/auth/change-password', { old_password: oldP, new_password: newP, confirm_password: confirmP }).then(function(res) {
    if (res.message) {
      result.style.color = 'var(--green)';
      result.textContent = res.message;
      document.getElementById('currentPassword').value = '';
      document.getElementById('changeNewPassword').value = '';
      document.getElementById('changeConfirmPassword').value = '';
    } else {
      result.style.color = 'var(--red)';
      result.textContent = res.detail || 'Erro';
    }
  });
}

function saveProfile() {
  var r = document.getElementById('profileResult');
  api('PUT', '/system/me', {
    full_name: document.getElementById('profileName').value,
    email: document.getElementById('profileEmail').value,
    telegram_username: document.getElementById('profileTelegram').value,
    receive_alerts_email: document.getElementById('alertEmail').checked,
    receive_alerts_telegram: document.getElementById('alertTelegram').checked
  }).then(function(d) {
    r.style.color = d.message ? 'var(--green)' : 'var(--red)';
    r.textContent = d.message || d.detail || 'Erro';
  });
}

function saveAlertPrefs() {
  var r = document.getElementById('alertResult');
  api('PUT', '/system/me', {
    receive_alerts_email: document.getElementById('alertEmail').checked,
    receive_alerts_telegram: document.getElementById('alertTelegram').checked
  }).then(function(d) {
    r.style.color = d.message ? 'var(--green)' : 'var(--red)';
    r.textContent = d.message || d.detail || 'Erro';
  });
}
