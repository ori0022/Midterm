#!/bin/bash
set -e

echo "========================================================"
echo "  Haovdim Bank — Automated Server Deployment Script     "
echo "========================================================"

# 1. Fetch & pull latest changes
echo ">>> [1/5] Pulling latest code from GitHub..."
git fetch origin
git pull origin main

# 2. Activate venv and update dependencies
echo ">>> [2/5] Updating Python virtual environment dependencies..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found! Creating .venv..."
    python3 -m venv .venv
    source .venv/bin/activate
fi
pip install -r requirements.txt --quiet

# 3. Verify database schema integrity
echo ">>> [3/5] Verifying database schema..."
python -c "from database import DatabaseManager; DatabaseManager()"

# 4. Run automated test suite to ensure release integrity
echo ">>> [4/5] Running automated test suite before reloading service..."
python test_scenarios.py

# 5. Restart service
echo ">>> [5/5] Restarting application service..."
if command -v systemctl &> /dev/null && systemctl list-unit-files | grep -q haovdim-bank.service; then
    sudo systemctl restart haovdim-bank.service
    sudo systemctl is-active --quiet haovdim-bank.service && echo ">>> SUCCESS: haovdim-bank.service restarted and active."
elif command -v pm2 &> /dev/null && pm2 list | grep -q haovdim-bank; then
    pm2 restart haovdim-bank
    echo ">>> SUCCESS: PM2 haovdim-bank restarted."
else
    echo ">>> Notice: Neither systemd service nor PM2 found. Restarting background process..."
    pkill -f "api_server.py" || true
    nohup python api_server.py > app.log 2>&1 &
    sleep 2
    echo ">>> Process launched in background (PID: $!). Check app.log for details."
fi

echo "========================================================"
echo "  Deployment Complete! Application is up to date.       "
echo "========================================================"
