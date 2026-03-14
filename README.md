# OurMoneyTrail — Family Expense Tracker

A full-featured family expense tracking app built with Django. Track expenses, set budgets, view analytics, and manage family member access — all with a modern, mobile-responsive UI optimised for Indian Rupees (INR).

## Features

- **Dashboard** — Stat cards, spending trends, category/payment/family breakdowns with collapsible sections
- **Spends** — Full expense list with filters, sorting, saved filters, bulk actions, CSV export
- **Analytics** — Period reports (monthly/quarterly/half-yearly/annual), budget comparison, trends, heatmap, assessment
- **Budgets** — Category-level and overall budget tracking with progress bars
- **Categories** — Organise expenses by type
- **Family** — Member profiles with per-person expense tracking and analytics
- **Authentication** — Login accounts with role-based permissions (admin vs member)
- **Dark Mode** — Toggle between light and dark themes
- **Mobile Responsive** — Works on phones, tablets, and desktops
- **INR Localisation** — Indian Rupee formatting with lakhs/crores grouping
- **Recurring Expenses** — Monthly, quarterly, half-yearly, annual auto-generation

## Quick Start

### Prerequisites

- **Python 3.8+** (tested with 3.10)
- **pip** (Python package manager)
- **Git**

### Install & Run

```bash
git clone https://github.com/ssubrahm/expense-tracker.git
cd expense-tracker
bash setup.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

## Login Accounts

| Name | Username | Password | Role |
|------|----------|----------|------|
| Srinath | `srinath` | `Sri@Expense2026!` | Admin |
| Jeejibai S | `jeejibai` | `Jeeji@Expense2026!` | Member |
| Madhumita S | `madhumita` | `Madhu@Expense2026!` | Member |
| Roopa | `roopa` | `Roopa@Expense2026!` | Member |

**Admin** can manage all expenses, budgets, categories, and family members.
**Members** can view all family data but only edit their own expenses and profile.

Change passwords anytime via the **Profile** page or **Family** tab (admin).

---

## Deployment Options

### Option 1: Local Network (Same WiFi)

Share the app with family members on your home network — no cloud needed.

**On your Mac/PC (the host):**

```bash
cd expense-tracker
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

**Find your local IP:**
- **Mac:** `ifconfig | grep "inet " | grep -v 127.0.0.1`
- **Linux:** `ip addr show | grep "inet " | grep -v 127.0.0.1`
- **Windows:** `ipconfig` → look for IPv4 Address

**Family members open on their phone/laptop:**
```
http://192.168.x.x:8000
```
(Replace `192.168.x.x` with your actual IP, e.g. `http://192.168.1.42:8000`)

> **Note:** The server must be running for others to access it. The app is only available while your computer is on and the server is active.

---

### Option 2: PythonAnywhere (Free Cloud — Always On)

Deploy to the cloud so family can access from anywhere, anytime.

#### Step-by-step:

**1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com/)** (free, no credit card)

**2. Open a Bash console** on PythonAnywhere (Dashboard → Consoles → Bash)

**3. Clone and set up:**
```bash
git clone https://github.com/ssubrahm/expense-tracker.git
cd expense-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py collectstatic --noinput
```

**4. Set environment variables** (PythonAnywhere → Web tab → "Environment variables" section):
```
DJANGO_ENV = production
DJANGO_SECRET_KEY = (generate one at https://djecrety.ir/)
DJANGO_ALLOWED_HOSTS = YOURUSERNAME.pythonanywhere.com
```

**5. Configure the web app** (PythonAnywhere → Web tab):
- Click **"Add a new web app"**
- Choose **Manual configuration** → **Python 3.10**
- Set **Source code:** `/home/YOURUSERNAME/expense-tracker`
- Set **Virtualenv:** `/home/YOURUSERNAME/expense-tracker/venv`

**6. Edit the WSGI file** (click the link on the Web tab):
Delete everything and replace with:
```python
import os
import sys

path = '/home/YOURUSERNAME/expense-tracker'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'expense_tracker.settings'
os.environ['DJANGO_ENV'] = 'production'
os.environ['DJANGO_SECRET_KEY'] = 'YOUR-SECRET-KEY-HERE'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'YOURUSERNAME.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**7. Set static files** (Web tab → Static files):
- URL: `/static/`
- Directory: `/home/YOURUSERNAME/expense-tracker/staticfiles`

**8. Click "Reload"** on the Web tab.

**9. Visit `https://YOURUSERNAME.pythonanywhere.com`** — done!

#### Updating after code changes:
```bash
cd ~/expense-tracker
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```
Then click **Reload** on the Web tab.

---

## Customising for Your Family

### Edit members through the app
Log in as admin → **Family** tab → edit names, add/remove members, set passwords.

### Start fresh
```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Customise seed data
Edit `expenses/management/commands/seed_data.py` to change names, passwords, expenses, then:
```bash
rm db.sqlite3
python manage.py migrate
python manage.py seed_data
```

## Project Structure

```
expense-tracker/
├── manage.py
├── setup.sh                   # One-command setup
├── requirements.txt           # Django + whitenoise + python-dateutil
├── RELEASE.md                 # Version history
├── expense_tracker/
│   ├── settings.py            # Auto-toggles dev/production via DJANGO_ENV
│   ├── urls.py
│   └── wsgi.py
└── expenses/
    ├── models.py              # Expense, Category, Budget, FamilyMember
    ├── views.py               # Views with auth & role-based permissions
    ├── forms.py               # Forms with client-side validation
    ├── context_processors.py  # User role context
    ├── templatetags/
    │   └── expense_tags.py    # INR formatting filter
    ├── management/commands/
    │   ├── seed_data.py       # Customisable data seeder
    │   └── generate_recurring.py
    └── templates/expenses/    # All HTML templates
```

## Tech Stack

- **Backend:** Django 5.x, Python 3.8+
- **Database:** SQLite (zero config)
- **Static Files:** WhiteNoise (production-ready)
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js (CDN)
- **Font:** Inter (Google Fonts CDN)

## License

Personal use. Built for family expense tracking.
