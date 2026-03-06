"""Generate due recurring expenses up to today's date."""
from datetime import date

from django.core.management.base import BaseCommand

from expenses.models import Expense


class Command(BaseCommand):
    help = "Generate recurring expense entries that are due up to today"

    def handle(self, *args, **options):
        today = date.today()
        recurring = Expense.objects.filter(
            recurrence__in=["monthly", "quarterly", "half_yearly", "annual"],
        ).exclude(recurrence="one_time")

        created_count = 0
        for expense in recurring:
            # Find the latest occurrence for this recurring chain
            if expense.recurring_parent is not None:
                # Skip children — only process root/source expenses
                continue

            # Get the latest date in this chain
            latest = expense.recurring_children.order_by("-date").first()
            last_date = latest.date if latest else expense.date

            # Generate all due occurrences
            next_date = expense.next_occurrence_date(last_date)
            while next_date and next_date <= today:
                # Check if this exact occurrence already exists
                exists = Expense.objects.filter(
                    recurring_parent=expense,
                    date=next_date,
                ).exists()
                if not exists:
                    Expense.objects.create(
                        title=expense.title,
                        amount=expense.amount,
                        date=next_date,
                        category=expense.category,
                        spent_by=expense.spent_by,
                        payment_method=expense.payment_method,
                        recurrence=expense.recurrence,
                        is_recurring_source=False,
                        recurring_parent=expense,
                        notes=expense.notes,
                    )
                    created_count += 1
                    self.stdout.write(f"  Created: {expense.title} on {next_date}")
                last_date = next_date
                next_date = expense.next_occurrence_date(last_date)

        if created_count:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Created {created_count} recurring expense(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("✓ No recurring expenses due."))
