#!/usr/bin/env bash
#
# SipSense EC2 Setup Script
#
# Run this on a fresh Ubuntu 22.04/24.04 EC2 instance:
#   curl -sSL https://raw.githubusercontent.com/<your-repo>/main/deploy/setup.sh | bash
#   — or —
#   git clone <your-repo> /opt/sipsense && bash /opt/sipsense/deploy/setup.sh
#
# Prerequisites:
#   - EC2 instance: t3.micro (free tier) or t3.small (if training ML models)
#   - Security group: ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
#   - Ubuntu 22.04 or 24.04 LTS AMI
#   - At least 2GB RAM (t3.micro has 1GB — add 1GB swap)

set -euo pipefail

APP_DIR="/opt/sipsense"
ENV_FILE="${APP_DIR}/.env"

echo "========================================"
echo "  SipSense Server Setup"
echo "========================================"

# ── 1. System packages ──────────────────────────────────────────────────

echo ""
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib libpq-dev \
    nginx certbot python3-certbot-nginx \
    git curl build-essential

# ── 2. Swap (t3.micro only has 1GB RAM — PyTorch needs more) ────────────

if [ "$(free -m | awk '/^Mem:/{print $2}')" -lt 2000 ]; then
    echo ""
    echo "[2/7] Adding 2GB swap (small instance detected)..."
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
    fi
else
    echo "[2/7] Swap: skipped (enough RAM)"
fi

# ── 3. Create app user ──────────────────────────────────────────────────

echo ""
echo "[3/7] Setting up app user and directory..."
if ! id -u sipsense &>/dev/null; then
    sudo useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" sipsense
fi

# Clone or update repo
if [ ! -d "${APP_DIR}/.git" ]; then
    echo "  Cloning repository..."
    echo "  >> You need to clone the repo to ${APP_DIR} first:"
    echo "     sudo git clone <YOUR_REPO_URL> ${APP_DIR}"
    echo "     Then re-run this script."
    echo ""
    echo "  Or if you already have it somewhere else, move it:"
    echo "     sudo mv /path/to/sipsense ${APP_DIR}"
    if [ ! -d "${APP_DIR}" ]; then
        exit 1
    fi
fi

sudo chown -R sipsense:sipsense "${APP_DIR}"

# ── 4. PostgreSQL ───────────────────────────────────────────────────────

echo ""
echo "[4/7] Setting up PostgreSQL..."
sudo systemctl enable --now postgresql

# Create database and user (idempotent)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='sipsense'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER sipsense WITH PASSWORD 'sipsense_prod_password';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='sipsense'" | grep -q 1 || \
    sudo -u postgres createdb -O sipsense sipsense

echo "  Database 'sipsense' ready."
echo "  >> IMPORTANT: Change the default password!"
echo "     sudo -u postgres psql -c \"ALTER USER sipsense PASSWORD 'your_secure_password';\""

# ── 5. Backend setup ────────────────────────────────────────────────────

echo ""
echo "[5/7] Setting up Python backend..."
cd "${APP_DIR}/backend"

# Create venv if it doesn't exist
if [ ! -d .venv ]; then
    python3.11 -m venv .venv
fi

# Install dependencies
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
.venv/bin/pip install --quiet psycopg2-binary gunicorn

# Create production .env if it doesn't exist
if [ ! -f "${ENV_FILE}" ]; then
    cat > "${ENV_FILE}" << 'ENVEOF'
# SipSense Production Environment
# !! Fill in these values before starting the app !!

DATABASE_URL=postgresql://sipsense:sipsense_prod_password@localhost:5432/sipsense
ANTHROPIC_API_KEY=sk-ant-your-key-here
JWT_SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_STRING
CORS_ORIGINS=https://yourdomain.com
ENVEOF
    echo "  Created ${ENV_FILE} — edit it with your real values!"
else
    echo "  ${ENV_FILE} already exists, skipping."
fi

# Create tables in PostgreSQL
.venv/bin/python -c "
from app.database import engine, Base
from app import models
Base.metadata.create_all(bind=engine)
print('  Database tables created.')
"

# ── 6. Frontend build ───────────────────────────────────────────────────

echo ""
echo "[6/7] Building frontend..."
cd "${APP_DIR}/frontend"

# Install Node.js if not present
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
fi

npm install --silent
npm run build

# ── 7. Nginx + systemd ──────────────────────────────────────────────────

echo ""
echo "[7/7] Configuring nginx and systemd..."

# Install nginx site config
sudo cp "${APP_DIR}/deploy/nginx-sipsense.conf" /etc/nginx/sites-available/sipsense
sudo ln -sf /etc/nginx/sites-available/sipsense /etc/nginx/sites-enabled/sipsense
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Install systemd service
sudo cp "${APP_DIR}/deploy/sipsense-api.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sipsense-api

echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit your environment file:"
echo "     sudo nano ${ENV_FILE}"
echo "     - Set your real ANTHROPIC_API_KEY"
echo "     - Set a random JWT_SECRET_KEY (run: openssl rand -hex 32)"
echo "     - Change the PostgreSQL password if you changed it"
echo ""
echo "  2. Import your whiskey data:"
echo "     cd ${APP_DIR}/backend"
echo "     sudo -u sipsense .venv/bin/python seed_data.py"
echo "     # Or copy your local sipsense.db and use the SQLite URL instead"
echo ""
echo "  3. Start the API:"
echo "     sudo systemctl start sipsense-api"
echo "     sudo journalctl -u sipsense-api -f   # watch logs"
echo ""
echo "  4. (Optional) Add SSL with Let's Encrypt:"
echo "     sudo certbot --nginx -d yourdomain.com"
echo ""
echo "  5. Verify it's working:"
echo "     curl http://localhost/api/whiskeys/?limit=1"
echo ""
