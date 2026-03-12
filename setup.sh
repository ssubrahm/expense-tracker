#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║     OurMoneyTrail — Setup            ║"
echo "║     Family Expense Tracker           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Pull latest if inside a git repo
if [ -d .git ]; then
  echo "→ Pulling latest from GitHub..."
  git pull origin master 2>/dev/null || echo "  (skipped — no remote or offline)"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "→ Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv
echo "→ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "→ Installing dependencies..."
pip install -r requirements.txt -q

# Run migrations
echo "→ Running database migrations..."
python manage.py migrate

# Seed data (idempotent — safe to run multiple times)
echo "→ Seeding sample data..."
python manage.py seed_data

# Generate any pending recurring expenses
echo "→ Generating recurring expenses..."
python manage.py generate_recurring

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  ✓ Setup complete!                   ║"
echo "║                                      ║"
echo "║  Starting server at:                 ║"
echo "║  http://127.0.0.1:8000               ║"
echo "║                                      ║"
echo "║  Login: srinath / srinath123          ║"
echo "║                                      ║"
echo "║  Press Ctrl+C to stop the server     ║"
echo "╚══════════════════════════════════════╝"
echo ""

python manage.py runserver
