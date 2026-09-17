#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}=== Glances Dashboard - Installation ===${NC}"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 not found. Install: sudo apt install python3 python3-pip python3-venv${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python: ${YELLOW}$PY_VERSION${NC}"

# Verificar/instalar glances
GLANCES_BIN=""
if command -v glances &> /dev/null; then
    GLANCES_BIN=$(command -v glances)
    echo -e "Glances: ${GREEN}found at $GLANCES_BIN${NC}"
else
    echo -e "${YELLOW}Installing Glances...${NC}"
    pip3 install --break-system-packages "glances[web]" 2>/dev/null && {
        GLANCES_BIN=$(python3 -c "import shutil; print(shutil.which('glances'))" 2>/dev/null || echo "")
    } || true

    if [ -z "$GLANCES_BIN" ] || [ ! -f "$GLANCES_BIN" ]; then
        echo -e "${YELLOW}Creating venv for Glances...${NC}"
        python3 -m venv /opt/glances-venv
        /opt/glances-venv/bin/pip install glances
        GLANCES_BIN="/opt/glances-venv/bin/glances"
        echo -e "Glances: ${GREEN}installed at $GLANCES_BIN${NC}"
    fi
fi

echo ""
echo -e "${GREEN}[1/6]${NC} Creating virtual environment..."
VENV_DIR="$SCRIPT_DIR/venv"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo -e "${GREEN}[2/6]${NC} Installing Python dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo -e "${GREEN}[3/6]${NC} Initializing database..."
python3 -c "from app.database import init_db; init_db()"

echo -e "${GREEN}[4/6]${NC} Configuring systemd services..."

# Dashboard service
cat > /tmp/glances-dashboard.service <<EOF
[Unit]
Description=Glances Dashboard
After=network.target glances-web.service
Requires=glances-web.service

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

# Glances Web service
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

echo -e "${GREEN}[5/6]${NC} Enabling and starting services..."
sudo systemctl enable glances-web.service glances-dashboard.service 2>/dev/null
sudo systemctl restart glances-web.service
sudo systemctl restart glances-dashboard.service

echo -e "${GREEN}[6/6]${NC} Checking status..."
sleep 3

GLANCES_STATUS=$(systemctl is-active glances-web.service 2>/dev/null || echo "inactive")
DASHBOARD_STATUS=$(systemctl is-active glances-dashboard.service 2>/dev/null || echo "inactive")

echo ""
if [ "$GLANCES_STATUS" = "active" ]; then
    echo -e "  Glances Web:  ${GREEN}✓ $GLANCES_STATUS${NC}"
else
    echo -e "  Glances Web:  ${RED}✗ $GLANCES_STATUS${NC}"
    echo -e "  ${YELLOW}Logs: sudo journalctl -u glances-web -n 20${NC}"
fi

if [ "$DASHBOARD_STATUS" = "active" ]; then
    echo -e "  Dashboard:    ${GREEN}✓ $DASHBOARD_STATUS${NC}"
else
    echo -e "  Dashboard:    ${RED}✗ $DASHBOARD_STATUS${NC}"
    echo -e "  ${YELLOW}Logs: sudo journalctl -u glances-dashboard -n 20${NC}"
fi

# Detectar IP
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
