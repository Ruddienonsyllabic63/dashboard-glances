# Glances Dashboard

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen)

Painel de monitoramento web para [Glances](https://nicolargo.github.io/glances/) com suporte a múltiplas máquinas, alertas, backups e internacionalização.

---

## Features

- **Dashboard em tempo real** — CPU, memória, disco, rede e processos
- **Múltiplos templates** — Grid, lista, cards e compacto
- **Múltiplas máquinas** — Monitore vários servidores Glances ao mesmo tempo
- **Sistema de alertas** — SMTP (email) e Telegram com limiares configuráveis
- **Monitoramento periódico** — Coleta automática de dados com gráficos
- **Backup e restauração** — Export/import do banco de dados completo
- **Filtros avançados** — Por máquina, data, status e processos
- **Controle de acesso** — Usuários admin e viewer com perfis
- **Internacionalização** — Português e Inglês
- **Temas** — Dark (padrão) e Light
- **Instalação de clientes** — GUIA completo para instalar Glances nos clientes
- **Configuração via web** — Tudo configurável pela interface

---

## Pré-requisitos

- Python 3.10+
- [Glances](https://nicolargo.github.io/glances/) com API web habilitada (`glances -w`)
- pip3

---

## Instalação Rápida

```bash
git clone https://github.com/SEU_USER/dashboard-glances.git
cd dashboard-glances
chmod +x install.sh
./install.sh
```

Acesse: `http://SEU_IP:8099`

Login padrão: **admin** / **admin**

---

## Instalação Manual

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU_USER/dashboard-glances.git
cd dashboard-glances
```

### 2. Instalar dependências

```bash
pip3 install -r requirements.txt
```

### 3. Inicializar o banco de dados

```bash
python3 -c "from app.database import init_db; init_db()"
```

### 4. Configurar serviços systemd

```bash
# Copiar arquivos de serviço
sudo cp glances-web.service /etc/systemd/system/
sudo cp glances-dashboard.service /etc/systemd/system/

# Recarregar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable glances-web glances-dashboard
sudo systemctl start glances-web glances-dashboard
```

### 5. Verificar

```bash
sudo systemctl status glances-dashboard
```

---

## Instalar Glances nos Clientes

Para monitorar máquinas remotas, o Glances precisa estar rodando nelas com a API web habilitada.

### Linux (Ubuntu/Debian)

```bash
# Instalar Glances
pip3 install glances[web]

# Criar serviço systemd
sudo tee /etc/systemd/system/glances-web.service > /dev/null <<EOF
[Unit]
Description=Glances Web Interface
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash -c 'hash -r && glances -w'
Restart=always
RestartSec=5
Environment=GLANCES_BIND=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

# Iniciar
sudo systemctl daemon-reload
sudo systemctl enable glances-web
sudo systemctl start glances-web
```

### Linux (CentOS/RHEL)

```bash
pip3 install glances[web]

# Seguir o mesmo passo de serviço systemd do Ubuntu
```

### Windows

```powershell
# Instalar Python e Glances
winget install Python.Python.3.12
pip install glances[web]

# Criar serviço
sc.exe create GlancesWeb binPath= "python -m glances -w" start= auto
sc.exe start GlancesWeb
```

### Docker

```bash
docker run -d --name glances -p 61208:61208 -v /var/run/docker.sock:/var/run/docker.sock:ro docker.io/nicolargo/glances:latest-full -w
```

---

## Firewall

A porta **8099** (Dashboard) e **61208** (Glances) precisam estar abertas.

### UFW (Ubuntu)

```bash
sudo ufw allow 8099/tcp
sudo ufw allow 61208/tcp
sudo ufw reload
```

### firewalld (CentOS)

```bash
sudo firewall-cmd --permanent --add-port=8099/tcp
sudo firewall-cmd --permanent --add-port=61208/tcp
sudo firewall-cmd --reload
```

### Windows

```powershell
netsh advfirewall firewall add rule name="Glances Dashboard" dir=in action=allow protocol=TCP localport=8099
netsh advfirewall firewall add rule name="Glances Web" dir=in action=allow protocol=TCP localport=61208
```

---

## Configuração

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `GLANCES_DASH_SECRET` | `glances-dashboard-secret-key-change-in-production` | Chave JWT (MUDE em produção!) |

### Arquivo `config.py`

```python
SECRET_KEY = os.getenv("GLANCES_DASH_SECRET", "sua-chave-aqui")
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas
GLANCES_DEFAULT_PORT = 61208
```

---

## Estrutura do Projeto

```
dashboard-glances/
├── app/
│   ├── main.py              # FastAPI app + rotas
│   ├── database.py           # Modelos SQLAlchemy
│   ├── auth.py               # JWT + bcrypt
│   ├── i18n/                 # Internacionalização
│   │   ├── pt.json
│   │   └── en.json
│   ├── routers/
│   │   ├── auth.py           # Login, registro, senha
│   │   ├── machines.py       # CRUD máquinas
│   │   ├── dashboard.py      # Layouts + dados
│   │   ├── backup.py         # Backup/restore
│   │   ├── monitor.py        # Monitoramento + logs
│   │   ├── system.py         # Config do sistema
│   │   ├── logo.py           # Upload de logo
│   │   └── alerts.py         # Alertas SMTP/Telegram
│   ├── services/
│   │   ├── glances.py        # Cliente HTTP Glances
│   │   ├── monitor.py        # Scheduler de coleta
│   │   └── backup.py         # Lógica de backup
│   └── templates/            # Templates Jinja2
│       ├── dashboard.html
│       ├── login.html
│       ├── settings.html
│       ├── logs.html
│       ├── admin_setup.html
│       ├── admin_alerts.html
│       ├── profile.html
│       └── email/            # Templates de email
├── static/
│   ├── css/style.css
│   ├── js/
│   │   ├── dashboard.js
│   │   ├── settings.js
│   │   ├── logs.js
│   │   └── i18n.js
│   └── img/default.svg
├── config.py
├── requirements.txt
├── install.sh
├── glances-dashboard.service
└── glances-web.service
```

---

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/register` | Registrar usuário (admin) |
| GET | `/api/machines/` | Listar máquinas |
| POST | `/api/machines/` | Adicionar máquina |
| GET | `/api/dashboard/all-data` | Dados de todas máquinas |
| GET | `/api/monitor/config` | Config de monitoramento |
| PUT | `/api/monitor/config` | Atualizar config |
| GET | `/api/monitor/logs` | Logs de monitoramento |
| POST | `/api/backup/create` | Criar backup |
| GET | `/api/backup/list` | Listar backups |
| GET | `/api/backup/download?name=...` | Download backup (ZIP) |
| POST | `/api/backup/restore` | Restaurar backup |

---

## Gerenciamento

```bash
# Status
sudo systemctl status glances-dashboard

# Reiniciar
sudo systemctl restart glances-dashboard

# Logs em tempo real
sudo journalctl -u glances-dashboard -f

# Parar
sudo systemctl stop glances-dashboard
```

---

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## Créditos

- [Glances](https://nicolargo.github.io/glances/) — Monitor de sistema
- [FastAPI](https://fastapi.tiangolo.com/) — Framework web
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM
