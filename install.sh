#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Glances Dashboard - Instalação ===${NC}"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 não encontrado. Instale: sudo apt install python3 python3-pip${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python: ${YELLOW}$PY_VERSION${NC}"

# Verificar Glances
if ! command -v glances &> /dev/null; then
    echo -e "${YELLOW}⚠ Glances não encontrado. Instale:${NC}"
    echo "  pip3 install glances"
    echo "  ou: sudo apt install glances"
    echo ""
fi

echo ""
echo -e "${GREEN}[1/6]${NC} Instalando dependências Python..."
pip3 install -r requirements.txt --quiet

echo -e "${GREEN}[2/6]${NC} Inicializando banco de dados..."
python3 -c "from app.database import init_db; init_db()"

echo -e "${GREEN}[3/6]${NC} Configurando serviços systemd..."
sudo cp glances-web.service /etc/systemd/system/
sudo cp glances-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload

echo -e "${GREEN}[4/6]${NC} Habilitando e iniciando serviços..."
sudo systemctl enable glances-web.service glances-dashboard.service 2>/dev/null
sudo systemctl restart glances-web.service
sudo systemctl restart glances-dashboard.service

echo -e "${GREEN}[5/6]${NC} Verificando status..."
sleep 2

GLANCES_STATUS=$(systemctl is-active glances-web.service 2>/dev/null || echo "inactive")
DASHBOARD_STATUS=$(systemctl is-active glances-dashboard.service 2>/dev/null || echo "inactive")

echo ""
if [ "$GLANCES_STATUS" = "active" ]; then
    echo -e "  Glances Web:  ${GREEN}✓ $GLANCES_STATUS${NC}"
else
    echo -e "  Glances Web:  ${RED}✗ $GLANCES_STATUS${NC}"
fi

if [ "$DASHBOARD_STATUS" = "active" ]; then
    echo -e "  Dashboard:    ${GREEN}✓ $DASHBOARD_STATUS${NC}"
else
    echo -e "  Dashboard:    ${RED}✗ $DASHBOARD_STATUS${NC}"
fi

# Detectar IP
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP="localhost"

echo -e "${GREEN}[6/6]${NC} Instalação concluída!"
echo ""
echo -e "  Acesse: ${YELLOW}http://$IP:8099${NC}"
echo -e "  Login:  ${YELLOW}admin / admin${NC}"
echo ""
echo "  Gerenciamento:"
echo "    sudo systemctl status glances-dashboard"
echo "    sudo systemctl restart glances-dashboard"
echo "    sudo journalctl -u glances-dashboard -f"
echo ""
