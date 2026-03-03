from django.db import models
from django.core.validators import MinValueValidator
import datetime


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(models.Model):
    PAYMENT_CHOICES = [
        ("cash", "Cash"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator("0.01")])
    date = models.DateField()
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="cash")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.title} — ${self.amount}"


class Budget(models.Model):
    """Monthly budget — optionally scoped to a category (None = overall budget)."""
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, blank=True, related_name="budgets"
    )
    year = models.IntegerField()
    month = models.IntegerField()  # 1-12
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator("0.01")])

    class Meta:
        unique_together = ("category", "year", "month")
        ordering = ["-year", "-month"]

    def __str__(self):
        cat = self.category.name if self.category else "Overall"
        return f"{cat} — {self.year}/{self.month:02d} — ${self.amount}"

    @property
    def month_name(self):
        return datetime.date(self.year, self.month, 1).strftime("%B %Y")


class SavedFilter(models.Model):
    """Named saved filter — stores the query string."""
    name = models.CharField(max_length=100, unique=True)
    query_string = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
