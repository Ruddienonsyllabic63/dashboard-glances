#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLANCES_VENV="/opt/glances-venv"

echo -e "${GREEN}=== Glances Dashboard - Installation ===${NC}"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 not found. Install: sudo apt install python3 python3-pip python3-venv${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python: ${YELLOW}$PY_VERSION${NC}"

# ──── Instalar Glances em venv dedicado ────
echo ""
echo -e "${GREEN}[1/6]${NC} Installing Glances..."

if [ -f "$GLANCES_VENV/bin/glances" ]; then
    echo -e "  Glances: ${GREEN}already installed at $GLANCES_VENV${NC}"
else
    echo -e "  Creating venv at ${YELLOW}$GLANCES_VENV${NC}..."
    python3 -m venv "$GLANCES_VENV"
    "$GLANCES_VENV/bin/pip" install "glances[web]" --quiet
    echo -e "  Glances: ${GREEN}installed${NC}"
fi

GLANCES_BIN="$GLANCES_VENV/bin/glances"
echo -e "  Binary: ${YELLOW}$GLANCES_BIN${NC}"

# ──── Instalar dependências do Dashboard ────
echo ""
echo -e "${GREEN}[2/6]${NC} Installing dashboard dependencies..."
VENV_DIR="$SCRIPT_DIR/venv"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

# ──── Inicializar banco ────
echo ""
echo -e "${GREEN}[3/6]${NC} Initializing database..."
python3 -c "from app.database import init_db; init_db()"

# ──── Configurar systemd ────
echo ""
echo -e "${GREEN}[4/6]${NC} Configuring systemd services..."

cat > /tmp/glances-dashboard.service <<EOF
[Unit]
Description=Glances Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099 --reload
Restart=always
RestartSec=5
Environment=GLANCES_DASH_SECRET=glances-dashboard-secret-change-me

[Install]
WantedBy=multi-user.target
EOF

cat > /tmp/glances-web.service <<EOF
[Unit]
Description=Glances Web Interface
After=network.target

[Service]
Type=simple
ExecStart=$GLANCES_BIN -w
Restart=always
RestartSec=5
Environment=GLANCES_BIND=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/glances-dashboard.service /etc/systemd/system/
sudo cp /tmp/glances-web.service /etc/systemd/system/
sudo systemctl daemon-reload

# ──── Iniciar serviços ────
echo ""
echo -e "${GREEN}[5/6]${NC} Starting services..."
sudo systemctl enable glances-web.service glances-dashboard.service 2>/dev/null
sudo systemctl restart glances-web.service
sudo systemctl restart glances-dashboard.service

# ──── Verificar status ────
echo ""
echo -e "${GREEN}[6/6]${NC} Checking status..."
sleep 3

GLANCES_STATUS=$(systemctl is-active glances-web.service 2>/dev/null || echo "inactive")
DASHBOARD_STATUS=$(systemctl is-active glances-dashboard.service 2>/dev/null || echo "inactive")

echo ""
if [ "$GLANCES_STATUS" = "active" ]; then
    echo -e "  Glances Web:  ${GREEN}✓ $GLANCES_STATUS${NC} (port 61208)"
else
    echo -e "  Glances Web:  ${RED}✗ $GLANCES_STATUS${NC}"
    echo -e "  ${YELLOW}Fix: sudo journalctl -u glances-web -n 20${NC}"
fi

if [ "$DASHBOARD_STATUS" = "active" ]; then
    echo -e "  Dashboard:    ${GREEN}✓ $DASHBOARD_STATUS${NC} (port 8099)"
else
    echo -e "  Dashboard:    ${RED}✗ $DASHBOARD_STATUS${NC}"
    echo -e "  ${YELLOW}Fix: sudo journalctl -u glances-dashboard -n 20${NC}"
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP="localhost"

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "  Access:  ${YELLOW}http://$IP:8099${NC}"
echo -e "  Login:   ${YELLOW}admin / admin${NC}"
echo ""
echo "  Management:"
echo "    sudo systemctl status glances-dashboard"
echo "    sudo systemctl restart glances-dashboard"
echo "    sudo journalctl -u glances-dashboard -f"
echo ""
