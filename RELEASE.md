# OurMoneyTrail — Release History

## v1.2 — Production-Ready Family Finance Tracker
**Date:** 2026-03-11
**Tag:** `v1.2`

### What's New in v1.2

#### Login & Authentication
- Family member login accounts with Django auth (username/password)
- Role-based permissions: admin (Srinath) vs regular members
- Admin can manage all family members, budgets, categories, and expenses
- Non-admin members can view all family data but only edit their own expenses and profile
- Profile page with password change
- Logout via POST (Django 5.0+ compatible)

#### Role-Based Access Control
- Budget CRUD restricted to admin only
- Category CRUD restricted to admin only
- Family member add/delete restricted to admin; non-admin can edit only own profile
- Expense edit/delete buttons hidden for other members' expenses
- Bulk actions enforce ownership for non-admin users
- Expense form locks "Spent By" field for non-admin (auto-assigns to self)

#### Family Member Accounts
- Seed data creates 4 accounts: Srinath (admin), Jeejibai S, Madhumita S, Roopa
- Admin can set/change username and password for any member via Family tab
- Non-admin can change their own username and password
- Family list shows username, admin badge, and role-aware action buttons

#### Dashboard & Analytics Cleanup
- Dashboard: paired side-by-side layout (Category chart+table, Trend+Payment, Family chart+table)
- Analytics: 7 collapsible sections with topic headers and icons
  - Period Overview, By Category, Trends, Activity Heatmap, By Payment Method, By Family Member, Assessment, Top 10
- Collapse/expand state persists via localStorage
- Week-over-Week change % chart added alongside weekly spending
- Bigger maroon chevron icons for collapse/expand (no border, high visibility)

#### MECE Tab Redesign
- Removed redundant Monthly tab (Spends already has date filters)
- Removed dead /monthly/ and /reports/ URLs, templates, and view code (475 lines cleaned)
- Navigation: Dashboard, Spends, Analytics, Budgets, Categories, Family

#### Form Validation & UX
- Client-side validation: required fields, amount > 0, date required
- Red border + error messages on invalid fields
- Amount auto-formats to 2 decimal places on blur
- `inputmode="decimal"` for mobile number pad on amount field
- Required field indicators (red asterisk)

#### Mobile Responsive Design
- All grids collapse to single column on mobile (<768px)
- Stat cards: 2-column on mobile, 1-column on small phones (<400px)
- Tables: horizontal scroll with preserved structure
- Form card: full width on mobile
- Touch devices: 16px font-size to prevent iOS zoom, 44px min touch targets
- Safe area insets for iPhone notch/home bar
- Mobile bottom navigation bar with 5 tabs
- Login page optimised for mobile

### Default Login Accounts
| Member | Username | Password | Role |
|---|---|---|---|
| Srinath | srinath | srinath123 | Admin |
| Jeejibai S | jeejibai | jeejibai123 | Member |
| Madhumita S | madhumita | madhumita123 | Member |
| Roopa | roopa | roopa123 | Member |

---

## v2.0-family — Family Expense Tracker
**Tag:** `v2.0-family`

### Features
- Family member profiles with relationship, gender, date of birth, avatar
- Tag expenses to family members (spent_by field)
- Family tab with member cards showing stats
- Dashboard/Analytics/Reports with family breakdown charts and per-member filtering
- Seed data: Srinath as primary member, 33 expenses, 5 budgets

---

## v1.0-personal — Personal Expense Tracker (MySpendTracker)
**Tag:** `v1.0-personal`

### Features
- Full Django expense tracker with modern UI
- Categories, budgets, saved filters, CSV export
- INR localisation with Indian number grouping (lakhs/crores)
- IST timezone
- Dark mode toggle with Inter font
- Toast notifications, floating action button
- Chart.js integration (9+ chart types)
- UX inspired by Mint, YNAB, Copilot Money, Monarch Money
- Recurring expenses (monthly, quarterly, half-yearly, annual)
- Bulk actions on Spends and Budgets pages
- Automated setup via `bash setup.sh`

---

## Version Timeline

| Version | Tag | Key Milestone |
|---|---|---|
| v1.0 | `v1.0-personal` | Personal expense tracker with modern UI, INR, dark mode |
| v2.0 | `v2.0-family` | Family member profiles and per-member tracking |
| v1.2 | `v1.2` | Auth, role-based permissions, MECE redesign, mobile responsive |

## Setup

```bash
git clone https://github.com/ssubrahm/expense-tracker.git
cd expense-tracker
bash setup.sh
# Open http://127.0.0.1:8000/login/
# Login as srinath / srinath123
```
