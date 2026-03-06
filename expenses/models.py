from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import datetime


class FamilyMember(models.Model):
    RELATIONSHIP_CHOICES = [
        ("self", "Self"),
        ("spouse", "Spouse"),
        ("child", "Child"),
        ("parent", "Parent"),
        ("sibling", "Sibling"),
        ("grandparent", "Grandparent"),
        ("other", "Other"),
    ]
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default="self")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    avatar_color = models.CharField(max_length=7, default="#6366f1", help_text="Hex colour for avatar")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.name[:2].upper()

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        import datetime as dt
        today = dt.date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


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
        ("upi", "UPI"),
        ("gpay", "Google Pay (GPay)"),
        ("phonepe", "PhonePe"),
        ("paytm", "Paytm"),
        ("bank_transfer", "Bank Transfer"),
        ("neft", "NEFT"),
        ("mobile_wallet", "Mobile Wallet"),
        ("cheque", "Cheque"),
        ("bnpl", "Buy Now Pay Later"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    date = models.DateField()
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )
    spent_by = models.ForeignKey(
        FamilyMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses",
        verbose_name="Spent by"
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
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

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
