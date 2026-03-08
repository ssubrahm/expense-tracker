from django import forms
from .models import Expense, Category, Budget, SavedFilter, FamilyMember


class FamilyMemberForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150, required=False,
        help_text="Login username. Leave blank to keep unchanged.",
    )
    password = forms.CharField(
        max_length=128, required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Leave blank to keep unchanged"}),
        help_text="Set or change password. Leave blank to keep current.",
    )

    class Meta:
        model = FamilyMember
        fields = ["name", "email", "phone", "relationship", "gender", "date_of_birth", "avatar_color"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "avatar_color": forms.TextInput(attrs={"type": "color", "style": "width:50px;height:36px;padding:2px;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["username"].initial = self.instance.user.username


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["title", "amount", "date", "category", "spent_by", "payment_method", "recurrence", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "year", "month", "amount"]
        widgets = {
            "month": forms.Select(choices=[(i, f"{i:02d}") for i in range(1, 13)]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "Overall (all categories)"


class SavedFilterForm(forms.ModelForm):
    class Meta:
        model = SavedFilter
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Filter name…"})}


class ExpenseFilterForm(forms.Form):
    DATE_PRESETS = [
        ("", "Custom range"),
        ("today", "Today"),
        ("this_week", "This week"),
        ("this_month", "This month"),
        ("last_month", "Last month"),
        ("last_3_months", "Last 3 months"),
        ("this_year", "This year"),
    ]

    search = forms.CharField(
        required=False, max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Search title or notes…"})
    )
    family_members = forms.ModelMultipleChoiceField(
        queryset=FamilyMember.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    payment_method = forms.MultipleChoiceField(
        choices=Expense.PAYMENT_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    date_preset = forms.ChoiceField(choices=DATE_PRESETS, required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    amount_min = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "0"}))
    amount_max = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "∞"}))
