#!/bin/bash
set -e

echo "=== OurMoneyTrail Setup ==="

echo "→ Pulling latest from GitHub..."
git pull origin master

echo "→ Installing dependencies..."
pip install -r requirements.txt -q

echo "→ Running migrations..."
python manage.py migrate

echo "→ Seeding data..."
python manage.py seed_data

echo "→ Generating recurring expenses..."
python manage.py generate_recurring

echo ""
echo "✓ Setup complete! Starting server..."
echo "  Open http://127.0.0.1:8000 in your browser"
echo ""
python manage.py runserver
