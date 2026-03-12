# OurMoneyTrail — Family Expense Tracker

A full-featured family expense tracking app built with Django. Track expenses, set budgets, view analytics, and manage family member access — all with a modern, mobile-responsive UI optimised for Indian Rupees (INR).

## Features

- **Dashboard** — Stat cards, spending trends, category/payment/family breakdowns
- **Spends** — Full expense list with filters, sorting, saved filters, bulk actions, CSV export
- **Analytics** — Period reports (monthly/quarterly/half-yearly/annual), budget comparison, trends, heatmap, assessment
- **Budgets** — Category-level and overall budget tracking with progress bars
- **Categories** — Organise expenses by type
- **Family** — Member profiles with per-person expense tracking and analytics
- **Authentication** — Login accounts with role-based permissions (admin vs member)
- **Dark Mode** — Toggle between light and dark themes
- **Mobile Responsive** — Works on phones, tablets, and desktops
- **INR Localisation** — Indian Rupee formatting with lakhs/crores grouping

## Quick Start

### Prerequisites

- **Python 3.8+** (tested with 3.10)
- **pip** (Python package manager)
- **Git**

### Install & Run

```bash
# 1. Clone the repository
git clone https://github.com/ssubrahm/expense-tracker.git
cd expense-tracker

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database and seed sample data
python manage.py migrate
python manage.py seed_data

# 5. Start the server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

### One-Command Setup (Linux/Mac)

If you've already cloned the repo:

```bash
bash setup.sh
```

This will install dependencies, run migrations, seed data, and start the server.

## Default Login Accounts

The seed data creates these accounts:

| Name | Username | Password | Role |
|------|----------|----------|------|
| Srinath | `srinath` | `srinath123` | Admin |
| Jeejibai S | `jeejibai` | `jeejibai123` | Member |
| Madhumita S | `madhumita` | `madhumita123` | Member |
| Roopa | `roopa` | `roopa123` | Member |

**Admin** can manage all expenses, budgets, categories, and family members.
**Members** can view all family data but only edit their own expenses and profile.

### Changing Passwords

After first login, change passwords via:
- **Profile page** (top-right menu) — change your own password
- **Family tab** (admin only) — Edit any member's username/password

## Customising for Your Family

### 1. Reset the database (start fresh)

```bash
rm db.sqlite3
python manage.py migrate
```

### 2. Create your own admin account

```bash
python manage.py createsuperuser
```

### 3. Or edit the seed data

Edit `expenses/management/commands/seed_data.py` to change:
- Family member names and relationships
- Default usernames and passwords
- Sample expense data
- Budget amounts and categories

Then run:

```bash
python manage.py seed_data
```

### 4. Add family members via the app

Login as admin, go to the **Family** tab, and click **+ Add Member** to create accounts for your family.

## Project Structure

```
expense-tracker/
├── manage.py                  # Django management
├── setup.sh                   # One-command setup script
├── requirements.txt           # Python dependencies
├── RELEASE.md                 # Version history
├── expense_tracker/           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── expenses/                  # Main app
    ├── models.py              # Expense, Category, Budget, FamilyMember
    ├── views.py               # All views with auth & permissions
    ├── forms.py               # Forms with validation
    ├── urls.py                # URL routing
    ├── context_processors.py  # Template context (user role)
    ├── templatetags/
    │   └── expense_tags.py    # INR formatting filter
    ├── management/commands/
    │   ├── seed_data.py       # Sample data seeder
    │   └── generate_recurring.py  # Recurring expense generator
    └── templates/expenses/    # All HTML templates
```

## Deployment

### Local Network (share with family on same WiFi)

```bash
python manage.py runserver 0.0.0.0:8000
```

Family members can access via your local IP: `http://192.168.x.x:8000`

### Cloud Deployment

The app is ready for deployment on:
- **Railway** / **Render** / **Fly.io** (free tiers available)
- **PythonAnywhere** (free tier)
- **Heroku** / **DigitalOcean**

For production, set these in `expense_tracker/settings.py`:
```python
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = 'your-random-secret-key'
```

## Tech Stack

- **Backend:** Django 5.x
- **Database:** SQLite (default, works for family use)
- **Frontend:** Vanilla HTML/CSS/JS with Chart.js
- **Font:** Inter (Google Fonts)
- **Icons:** SVG + Emoji

## License

Personal use. Built for family expense tracking.
