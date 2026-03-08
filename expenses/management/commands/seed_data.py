"""Seed the database with Srinath's expense data from v1.0 personal tracker."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from expenses.models import Category, Expense, Budget, FamilyMember


class Command(BaseCommand):
    help = "Seed categories, family member (Srinath), expenses, and budgets"

    def handle(self, *args, **options):
        # ── Categories ──
        categories = [
            "Entertainment", "Food & Dining", "Health & Medical",
            "Shopping", "Transport", "Travel", "Utilities",
        ]
        cat_map = {}
        for name in categories:
            cat, created = Category.objects.get_or_create(name=name)
            cat_map[name] = cat
            self.stdout.write(f"  {'Created' if created else 'Exists'}: {name}")

        # ── Family member: Srinath (self, admin) ──
        srinath, created = FamilyMember.objects.get_or_create(
            name="Srinath",
            defaults={
                "relationship": "self",
                "avatar_color": "#6366f1",
                "is_active": True,
                "is_family_admin": True,
            },
        )
        if not srinath.is_family_admin:
            srinath.is_family_admin = True
            srinath.save()
        self.stdout.write(f"\n  Family member: {'Created' if created else 'Exists'} — {srinath.name}")

        # ── Create User account for Srinath ──
        if not srinath.user:
            user, u_created = User.objects.get_or_create(
                username="srinath",
                defaults={"first_name": "Srinath", "is_staff": True},
            )
            if u_created:
                user.set_password("srinath123")
                user.save()
                self.stdout.write("  User: Created 'srinath' (password: srinath123)")
            else:
                self.stdout.write("  User: Exists 'srinath'")
            srinath.user = user
            srinath.save()
        else:
            self.stdout.write(f"  User: Already linked — {srinath.user.username}")

        # ── Other family members ──
        family_members = [
            {"name": "Jeejibai S", "relationship": "spouse", "avatar_color": "#ec4899", "username": "jeejibai", "password": "jeejibai123"},
            {"name": "Madhumita S", "relationship": "child", "avatar_color": "#f59e0b", "username": "madhumita", "password": "madhumita123"},
            {"name": "Roopa", "relationship": "parent", "avatar_color": "#10b981", "username": "roopa", "password": "roopa123"},
        ]
        for fm_data in family_members:
            fm, fm_created = FamilyMember.objects.get_or_create(
                name=fm_data["name"],
                defaults={
                    "relationship": fm_data["relationship"],
                    "avatar_color": fm_data["avatar_color"],
                    "is_active": True,
                },
            )
            self.stdout.write(f"  Family member: {'Created' if fm_created else 'Exists'} — {fm.name}")
            if not fm.user:
                u, u_created = User.objects.get_or_create(
                    username=fm_data["username"],
                    defaults={"first_name": fm_data["name"]},
                )
                if u_created:
                    u.set_password(fm_data["password"])
                    u.save()
                    self.stdout.write(f"    User: Created '{fm_data['username']}' (password: {fm_data['password']})")
                else:
                    self.stdout.write(f"    User: Exists '{fm_data['username']}'")
                fm.user = u
                fm.save()

        # ── Expenses ──
        # (date, title, amount, category, payment_method, recurrence)
        expenses = [
            ("2026-01-02", "Bus pass", "35.00", "Transport", "debit_card", "monthly"),
            ("2026-01-08", "Gas station", "55.00", "Transport", "credit_card", "one_time"),
            ("2026-01-10", "Breakfast cafe", "12.50", "Food & Dining", "cash", "one_time"),
            ("2026-01-12", "Cinema tickets", "22.00", "Entertainment", "cash", "one_time"),
            ("2026-01-15", "Supermarket", "93.00", "Food & Dining", "debit_card", "one_time"),
            ("2026-01-18", "Takeaway pizza", "24.00", "Food & Dining", "credit_card", "one_time"),
            ("2026-01-20", "Doctor visit", "80.00", "Health & Medical", "credit_card", "one_time"),
            ("2026-01-25", "Shoes", "89.00", "Shopping", "debit_card", "one_time"),
            ("2026-01-31", "Electricity", "110.00", "Utilities", "bank_transfer", "monthly"),
            ("2026-01-31", "Water bill", "45.00", "Utilities", "bank_transfer", "monthly"),
            ("2026-02-01", "Gym membership", "45.00", "Health & Medical", "credit_card", "monthly"),
            ("2026-02-01", "Spotify", "9.99", "Entertainment", "credit_card", "monthly"),
            ("2026-02-03", "Metro card top-up", "40.00", "Transport", "debit_card", "one_time"),
            ("2026-02-05", "Flight ticket", "320.00", "Travel", "credit_card", "one_time"),
            ("2026-02-07", "Hotel stay", "180.00", "Travel", "credit_card", "one_time"),
            ("2026-02-10", "Amazon order", "78.99", "Shopping", "credit_card", "one_time"),
            ("2026-02-14", "Zara clothes", "120.00", "Shopping", "debit_card", "one_time"),
            ("2026-02-15", "Movie night", "28.00", "Entertainment", "cash", "one_time"),
            ("2026-02-18", "Taxi", "14.00", "Transport", "cash", "one_time"),
            ("2026-02-20", "Restaurant dinner", "65.00", "Food & Dining", "credit_card", "one_time"),
            ("2026-02-22", "Lunch delivery", "18.50", "Food & Dining", "debit_card", "one_time"),
            ("2026-02-25", "Pharmacy", "32.50", "Health & Medical", "credit_card", "one_time"),
            ("2026-02-28", "Monthly electricity bill", "120.00", "Utilities", "cash", "monthly"),
            ("2026-02-28", "Internet bill", "59.99", "Utilities", "bank_transfer", "monthly"),
            ("2026-03-01", "Grocery shopping", "85.50", "Food & Dining", "cash", "one_time"),
            ("2026-03-01", "Netflix subscription", "15.99", "Entertainment", "cash", "monthly"),
            ("2026-03-01", "Train tickets", "48.00", "Travel", "credit_card", "one_time"),
            ("2026-03-01", "Online course", "99.00", "Entertainment", "credit_card", "quarterly"),
            ("2026-03-02", "Uber ride", "22.75", "Transport", "cash", "one_time"),
            ("2026-03-02", "Vitamin supplements", "38.00", "Health & Medical", "credit_card", "one_time"),
            ("2026-03-02", "Parking", "15.00", "Transport", "cash", "one_time"),
            ("2026-03-03", "Coffee shop", "7.50", "Food & Dining", "cash", "one_time"),
            ("2026-03-03", "Brunch", "42.00", "Food & Dining", "debit_card", "one_time"),
        ]

        created_count = 0
        for dt, title, amount, cat_name, payment, recurrence in expenses:
            y, m, d = dt.split("-")
            is_recurring = recurrence != "one_time"
            _, created = Expense.objects.get_or_create(
                title=title,
                date=date(int(y), int(m), int(d)),
                defaults={
                    "amount": Decimal(amount),
                    "category": cat_map[cat_name],
                    "payment_method": payment,
                    "spent_by": srinath,
                    "recurrence": recurrence,
                    "is_recurring_source": is_recurring,
                },
            )
            if created:
                created_count += 1
        self.stdout.write(f"\n  Expenses: {created_count} created, {len(expenses) - created_count} already existed")

        # ── Budgets (March 2026) ──
        budgets = [
            (None, 2026, 3, "1500.00"),
            ("Food & Dining", 2026, 3, "400.00"),
            ("Transport", 2026, 3, "200.00"),
            ("Entertainment", 2026, 3, "100.00"),
            ("Health & Medical", 2026, 3, "150.00"),
        ]
        budget_count = 0
        for cat_name, year, month, amount in budgets:
            cat = cat_map.get(cat_name)
            _, created = Budget.objects.get_or_create(
                category=cat, year=year, month=month,
                defaults={"amount": Decimal(amount)},
            )
            if created:
                budget_count += 1
        self.stdout.write(f"  Budgets: {budget_count} created, {len(budgets) - budget_count} already existed")

        self.stdout.write(self.style.SUCCESS("\n✓ Seed data loaded successfully!"))
