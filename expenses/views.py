import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.db.models import Sum, Avg, Count, Max, Min, Q, F
from django.db.models.functions import TruncMonth, TruncWeek
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .models import Expense, Category, Budget, SavedFilter
from .forms import ExpenseForm, CategoryForm, BudgetForm, SavedFilterForm, ExpenseFilterForm


SORT_FIELDS = {
    "date": "-date", "-date": "date",
    "amount": "-amount", "-amount": "amount",
    "title": "title", "-title": "-title",
    "category": "category__name", "-category": "-category__name",
}

CHART_COLORS = [
    "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
    "#ef4444", "#06b6d4", "#ec4899", "#f97316",
    "#14b8a6", "#6366f1",
]


def get_category_color_map():
    """Build a persistent mapping of category name -> color index."""
    cats = list(Category.objects.order_by("id").values_list("name", flat=True))
    return {name: i % len(CHART_COLORS) for i, name in enumerate(cats)}


def apply_filters(request):
    expenses = Expense.objects.select_related("category").all()
    filter_form = ExpenseFilterForm(request.GET)

    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        categories = filter_form.cleaned_data.get("categories")
        payment_methods = filter_form.cleaned_data.get("payment_method")
        date_preset = filter_form.cleaned_data.get("date_preset")
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")
        amount_min = filter_form.cleaned_data.get("amount_min")
        amount_max = filter_form.cleaned_data.get("amount_max")

        if search:
            expenses = expenses.filter(Q(title__icontains=search) | Q(notes__icontains=search))
        if categories:
            expenses = expenses.filter(category__in=categories)
        if payment_methods:
            expenses = expenses.filter(payment_method__in=payment_methods)
        if amount_min is not None:
            expenses = expenses.filter(amount__gte=amount_min)
        if amount_max is not None:
            expenses = expenses.filter(amount__lte=amount_max)

        today = date.today()
        if date_preset == "today":
            expenses = expenses.filter(date=today)
        elif date_preset == "this_week":
            expenses = expenses.filter(date__gte=today - timedelta(days=today.weekday()))
        elif date_preset == "this_month":
            expenses = expenses.filter(date__year=today.year, date__month=today.month)
        elif date_preset == "last_month":
            first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last = today.replace(day=1) - timedelta(days=1)
            expenses = expenses.filter(date__gte=first, date__lte=last)
        elif date_preset == "last_3_months":
            expenses = expenses.filter(date__gte=today - timedelta(days=90))
        elif date_preset == "this_year":
            expenses = expenses.filter(date__year=today.year)
        else:
            if date_from:
                expenses = expenses.filter(date__gte=date_from)
            if date_to:
                expenses = expenses.filter(date__lte=date_to)

    return expenses, filter_form


def dashboard(request):
    # Saved filter actions
    saved_filters = SavedFilter.objects.all()
    if request.method == "POST":
        if "save_filter" in request.POST:
            sf_form = SavedFilterForm(request.POST)
            if sf_form.is_valid():
                qs = request.POST.get("current_qs", "")
                SavedFilter.objects.update_or_create(
                    name=sf_form.cleaned_data["name"],
                    defaults={"query_string": qs},
                )
                messages.success(request, f"Filter '{sf_form.cleaned_data['name']}' saved.")
            return redirect(request.META.get("HTTP_REFERER", "/"))
        elif "delete_filter" in request.POST:
            fid = request.POST.get("filter_id")
            SavedFilter.objects.filter(pk=fid).delete()
            messages.success(request, "Saved filter deleted.")
            return redirect("/")

    expenses, filter_form = apply_filters(request)
    sort = request.GET.get("sort", "-date")
    sort_field = SORT_FIELDS.get(sort, "-date")
    expenses = expenses.order_by(sort_field)

    agg = expenses.aggregate(
        total=Sum("amount"), avg=Avg("amount"),
        biggest=Max("amount"), count=Count("id"),
    )
    total = agg["total"] or Decimal("0")
    avg_expense = agg["avg"] or Decimal("0")
    biggest = agg["biggest"] or Decimal("0")
    count = agg["count"] or 0

    date_list = list(expenses.values_list("date", flat=True))
    if len(date_list) > 1:
        span_days = max((max(date_list) - min(date_list)).days, 1)
        avg_daily = total / span_days
    else:
        avg_daily = total

    # Category breakdown
    by_category = (
        expenses.values("category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Monthly trend (all data for context)
    monthly_qs = (
        Expense.objects.annotate(month=TruncMonth("date"))
        .values("month").annotate(total=Sum("amount")).order_by("month")
    )
    monthly_labels = [m["month"].strftime("%b %Y") for m in monthly_qs if m["month"]]
    monthly_data = [float(m["total"]) for m in monthly_qs if m["month"]]

    # Category stacked data per month (top 5 cats)
    top_cats = list(
        Expense.objects.values("category__name")
        .annotate(t=Sum("amount")).order_by("-t")
        .values_list("category__name", flat=True)[:5]
    )
    stacked_datasets = []
    for i, cat in enumerate(top_cats):
        cat_monthly = (
            Expense.objects.filter(category__name=cat)
            .annotate(month=TruncMonth("date"))
            .values("month").annotate(total=Sum("amount")).order_by("month")
        )
        cat_map = {m["month"].strftime("%b %Y"): float(m["total"]) for m in cat_monthly if m["month"]}
        stacked_datasets.append({
            "label": cat or "Uncategorised",
            "data": [cat_map.get(l, 0) for l in monthly_labels],
            "backgroundColor": CHART_COLORS[i % len(CHART_COLORS)],
        })

    # Payment method breakdown
    by_payment = (
        expenses.values("payment_method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    cat_labels = [r["category__name"] or "Uncategorised" for r in by_category]
    cat_data = [float(r["total"]) for r in by_category]

    # Amount bounds for slider
    all_amounts = Expense.objects.aggregate(mn=Min("amount"), mx=Max("amount"))
    amount_global_min = float(all_amounts["mn"] or 0)
    amount_global_max = float(all_amounts["mx"] or 1000)

    # Budget progress for current month
    today = date.today()
    current_month_total = (
        Expense.objects.filter(date__year=today.year, date__month=today.month)
        .aggregate(t=Sum("amount"))["t"] or Decimal("0")
    )
    overall_budget = Budget.objects.filter(
        category=None, year=today.year, month=today.month
    ).first()
    budget_pct = 0
    if overall_budget and overall_budget.amount > 0:
        budget_pct = min(int(current_month_total / overall_budget.amount * 100), 100)

    # Category budgets this month
    cat_budgets = []
    for b in Budget.objects.filter(year=today.year, month=today.month, category__isnull=False).select_related("category"):
        spent = (
            Expense.objects.filter(category=b.category, date__year=today.year, date__month=today.month)
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )
        pct = min(int(spent / b.amount * 100), 100) if b.amount > 0 else 0
        cat_budgets.append({"budget": b, "spent": spent, "pct": pct, "remaining": b.amount - spent})

    cat_color_map = get_category_color_map()

    context = {
        "expenses": expenses,
        "filter_form": filter_form,
        "saved_filters": saved_filters,
        "save_filter_form": SavedFilterForm(),
        "sort": sort,
        "total": total,
        "avg_expense": avg_expense,
        "avg_daily": avg_daily,
        "biggest": biggest,
        "count": count,
        "by_category": by_category,
        "by_payment": by_payment,
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_data": json.dumps(monthly_data),
        "stacked_datasets": json.dumps(stacked_datasets),
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "amount_global_min": amount_global_min,
        "amount_global_max": amount_global_max,
        "current_qs": request.GET.urlencode(),
        "overall_budget": overall_budget,
        "current_month_total": current_month_total,
        "budget_pct": budget_pct,
        "cat_budgets": cat_budgets,
        "today": today,
        "cat_color_map": cat_color_map,
        "chart_colors": json.dumps(CHART_COLORS),
    }
    return render(request, "expenses/dashboard.html", context)


def analytics(request):
    today = date.today()
    all_expenses = Expense.objects.select_related("category").all()

    # --- Monthly trend (12 months) ---
    monthly_qs = (
        all_expenses.annotate(month=TruncMonth("date"))
        .values("month").annotate(total=Sum("amount"), count=Count("id"))
        .order_by("month")
    )
    monthly_labels = [m["month"].strftime("%b %Y") for m in monthly_qs if m["month"]]
    monthly_totals = [float(m["total"]) for m in monthly_qs if m["month"]]
    monthly_counts = [m["count"] for m in monthly_qs if m["month"]]

    # Month-over-month change
    mom_changes = []
    for i, v in enumerate(monthly_totals):
        if i == 0:
            mom_changes.append(0)
        else:
            prev = monthly_totals[i - 1]
            mom_changes.append(round((v - prev) / prev * 100, 1) if prev else 0)

    # --- Weekly trend (last 12 weeks) ---
    twelve_weeks_ago = today - timedelta(weeks=12)
    weekly_qs = (
        all_expenses.filter(date__gte=twelve_weeks_ago)
        .annotate(week=TruncWeek("date"))
        .values("week").annotate(total=Sum("amount")).order_by("week")
    )
    weekly_labels = [w["week"].strftime("W%W %b") for w in weekly_qs if w["week"]]
    weekly_data = [float(w["total"]) for w in weekly_qs if w["week"]]

    # --- Spending heatmap: day-of-week × week ---
    heatmap_raw = (
        all_expenses.filter(date__gte=today - timedelta(days=84))
        .values("date").annotate(total=Sum("amount"))
    )
    heatmap = defaultdict(float)
    for row in heatmap_raw:
        heatmap[row["date"].isoformat()] = float(row["total"])

    # Build 12-week grid
    heatmap_weeks = []
    start = today - timedelta(days=today.weekday() + 7 * 11)
    for w in range(12):
        week = []
        for d in range(7):
            day = start + timedelta(days=w * 7 + d)
            week.append({"date": day.isoformat(), "amount": heatmap.get(day.isoformat(), 0)})
        heatmap_weeks.append(week)

    # --- Category trend: stacked monthly ---
    top_cats = list(
        all_expenses.values("category__name")
        .annotate(t=Sum("amount")).order_by("-t")
        .values_list("category__name", flat=True)[:6]
    )
    stacked = []
    for i, cat in enumerate(top_cats):
        cat_qs = (
            all_expenses.filter(category__name=cat)
            .annotate(month=TruncMonth("date"))
            .values("month").annotate(total=Sum("amount")).order_by("month")
        )
        cat_map = {m["month"].strftime("%b %Y"): float(m["total"]) for m in cat_qs if m["month"]}
        stacked.append({
            "label": cat or "Uncategorised",
            "data": [cat_map.get(l, 0) for l in monthly_labels],
            "backgroundColor": CHART_COLORS[i % len(CHART_COLORS)],
            "borderColor": CHART_COLORS[i % len(CHART_COLORS)],
            "fill": False,
            "tension": 0.4,
        })

    # --- Top expenses ---
    top_expenses = all_expenses.order_by("-amount")[:10]

    # --- Actionable Insights (Copilot-style) ---
    insights = []
    if len(monthly_totals) >= 2:
        last = monthly_totals[-1]
        prev = monthly_totals[-2]
        diff = last - prev
        pct = round(abs(diff) / prev * 100, 1) if prev else 0
        if diff > 0:
            savings = diff
            insights.append({
                "type": "warning", "icon": "📈",
                "text": f"Spending is up {pct}% vs last month (₹{last:,.2f} vs ₹{prev:,.2f})",
                "nudge": f"Reduce by ₹{savings:,.0f} this month to match last month's level.",
            })
        else:
            monthly_saved = abs(diff)
            yearly_proj = monthly_saved * 12
            insights.append({
                "type": "success", "icon": "📉",
                "text": f"Spending is down {pct}% vs last month — great job!",
                "nudge": f"At this rate, you'll save ₹{yearly_proj:,.0f} over a year. Keep it up!",
            })

    # Most expensive category this month with budget context
    this_month_cat = (
        all_expenses.filter(date__year=today.year, date__month=today.month)
        .values("category__name").annotate(t=Sum("amount")).order_by("-t").first()
    )
    if this_month_cat:
        cat_name = this_month_cat["category__name"] or "Uncategorised"
        cat_total = this_month_cat["t"]
        cat_budget = Budget.objects.filter(
            category__name=cat_name, year=today.year, month=today.month
        ).first()
        nudge = ""
        if cat_budget and cat_total > cat_budget.amount:
            over = cat_total - cat_budget.amount
            nudge = f"You're ₹{over:,.0f} over your {cat_name} budget. Review recent purchases."
        elif cat_budget:
            left = cat_budget.amount - cat_total
            nudge = f"₹{left:,.0f} remaining in your {cat_name} budget this month."
        else:
            nudge = f"Consider setting a budget for {cat_name} to stay in control."
        insights.append({
            "type": "info", "icon": "🏆",
            "text": f"Top category this month: {cat_name} (₹{cat_total:,.2f})",
            "nudge": nudge,
        })

    # Biggest single day
    biggest_day = (
        all_expenses.values("date").annotate(t=Sum("amount")).order_by("-t").first()
    )
    if biggest_day:
        insights.append({
            "type": "info", "icon": "🔥",
            "text": f"Biggest spending day: {biggest_day['date']} (₹{biggest_day['t']:,.2f})",
            "nudge": "Tip: Space out large purchases across the month to maintain steady cash flow.",
        })

    # Weekend vs weekday with advice
    weekday_avg = all_expenses.filter(date__week_day__in=[2,3,4,5,6]).aggregate(a=Avg("amount"))["a"] or 0
    weekend_avg = all_expenses.filter(date__week_day__in=[1,7]).aggregate(a=Avg("amount"))["a"] or 0
    if weekday_avg and weekend_avg:
        if float(weekend_avg) > float(weekday_avg) * 1.2:
            nudge = "Your weekends cost significantly more. Try a no-spend Saturday challenge."
        else:
            nudge = "Your spending is well-balanced across the week."
        insights.append({
            "type": "info", "icon": "📅",
            "text": f"Weekend avg ₹{weekend_avg:,.2f} vs weekday ₹{weekday_avg:,.2f}",
            "nudge": nudge,
        })

    # Most used payment method
    top_payment = (
        all_expenses.values("payment_method").annotate(c=Count("id")).order_by("-c").first()
    )
    if top_payment:
        pm_display = dict(Expense.PAYMENT_CHOICES).get(top_payment["payment_method"], top_payment["payment_method"])
        total_txns = all_expenses.count()
        pm_pct = round(top_payment["c"] / total_txns * 100) if total_txns else 0
        nudge = ""
        if pm_pct > 70:
            nudge = f"{pm_display} is {pm_pct}% of all transactions. Track cash expenses separately to avoid blind spots."
        else:
            nudge = f"Good diversification across payment methods."
        insights.append({
            "type": "info", "icon": "💳",
            "text": f"Most used: {pm_display} ({top_payment['c']} transactions, {pm_pct}%)",
            "nudge": nudge,
        })

    # Overall stats
    overall = all_expenses.aggregate(
        total=Sum("amount"), avg=Avg("amount"),
        count=Count("id"), biggest=Max("amount"),
    )

    cat_color_map = get_category_color_map()

    context = {
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_totals": json.dumps(monthly_totals),
        "monthly_counts": json.dumps(monthly_counts),
        "mom_changes": json.dumps(mom_changes),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_data": json.dumps(weekly_data),
        "stacked_datasets": json.dumps(stacked),
        "heatmap_weeks": heatmap_weeks,
        "heatmap_max": max(heatmap.values()) if heatmap else 1,
        "top_expenses": top_expenses,
        "insights": insights,
        "overall": overall,
        "today": today,
        "cat_color_map": cat_color_map,
    }
    return render(request, "expenses/analytics.html", context)


def budget_list(request):
    today = date.today()
    budgets = Budget.objects.select_related("category").order_by("-year", "-month")

    budget_data = []
    for b in budgets:
        spent = (
            Expense.objects.filter(
                date__year=b.year, date__month=b.month,
                category=b.category,
            ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )
        remaining = b.amount - spent
        pct = min(int(spent / b.amount * 100), 100) if b.amount > 0 else 0
        budget_data.append({"budget": b, "spent": spent, "remaining": remaining, "pct": pct})

    return render(request, "expenses/budget_list.html", {"budget_data": budget_data, "cat_color_map": get_category_color_map()})


def budget_create(request):
    if request.method == "POST":
        form = BudgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget created.")
            return redirect("budget_list")
    else:
        today = date.today()
        form = BudgetForm(initial={"year": today.year, "month": today.month})
    return render(request, "expenses/budget_form.html", {"form": form, "title": "Set Budget"})


def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted.")
        return redirect("budget_list")
    return render(request, "expenses/budget_confirm_delete.html", {"budget": budget})


def monthly_view(request):
    expenses, filter_form = apply_filters(request)
    today = date.today()

    grouped = (
        expenses.annotate(month=TruncMonth("date"))
        .values("month").annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-month")
    )

    months = []
    for g in grouped:
        month_expenses = expenses.filter(
            date__year=g["month"].year, date__month=g["month"].month,
        ).order_by("-date")
        budget = Budget.objects.filter(
            category=None, year=g["month"].year, month=g["month"].month
        ).first()
        budget_pct = 0
        if budget and budget.amount > 0:
            budget_pct = min(int(g["total"] / budget.amount * 100), 100)
        months.append({
            "month": g["month"],
            "total": g["total"],
            "count": g["count"],
            "expenses": month_expenses,
            "budget": budget,
            "budget_pct": budget_pct,
        })

    context = {
        "months": months,
        "filter_form": filter_form,
        "grand_total": expenses.aggregate(t=Sum("amount"))["t"] or 0,
        "cat_color_map": get_category_color_map(),
    }
    return render(request, "expenses/monthly_view.html", context)


def export_csv(request):
    expenses, _ = apply_filters(request)
    sort = request.GET.get("sort", "-date")
    expenses = expenses.order_by(SORT_FIELDS.get(sort, "-date"))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Amount", "Payment Method", "Notes"])
    for e in expenses:
        writer.writerow([e.date, e.title, e.category.name if e.category else "",
                         e.amount, e.get_payment_method_display(), e.notes])
    return response


def expense_create(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense added.")
            return redirect("dashboard")
    else:
        form = ExpenseForm(initial={"date": date.today()})
    return render(request, "expenses/expense_form.html", {"form": form, "title": "Add Expense"})


def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense updated.")
            return redirect("dashboard")
    else:
        form = ExpenseForm(instance=expense)
    return render(request, "expenses/expense_form.html", {"form": form, "title": "Edit Expense", "expense": expense})


def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted.")
        return redirect("dashboard")
    return render(request, "expenses/expense_confirm_delete.html", {"expense": expense})


def reports(request):
    """Spending reports: monthly, quarterly, half-yearly, annual with budget comparison."""
    today = date.today()
    period = request.GET.get("period", "monthly")

    # Build period ranges
    if period == "quarterly":
        q = (today.month - 1) // 3
        period_start = date(today.year, q * 3 + 1, 1)
        period_end = today
        period_label = f"Q{q + 1} {today.year}"
        prev_start = date(today.year if q > 0 else today.year - 1, (q - 1) * 3 + 1 if q > 0 else 10, 1)
        prev_end = period_start - timedelta(days=1)
    elif period == "half_yearly":
        if today.month <= 6:
            period_start = date(today.year, 1, 1)
            period_label = f"H1 {today.year}"
            prev_start = date(today.year - 1, 7, 1)
            prev_end = date(today.year - 1, 12, 31)
        else:
            period_start = date(today.year, 7, 1)
            period_label = f"H2 {today.year}"
            prev_start = date(today.year, 1, 1)
            prev_end = date(today.year, 6, 30)
        period_end = today
    elif period == "annual":
        period_start = date(today.year, 1, 1)
        period_end = today
        period_label = f"FY {today.year}"
        prev_start = date(today.year - 1, 1, 1)
        prev_end = date(today.year - 1, 12, 31)
    else:  # monthly
        period_start = today.replace(day=1)
        period_end = today
        period_label = today.strftime("%B %Y")
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)

    # Current period expenses
    expenses = Expense.objects.filter(date__gte=period_start, date__lte=period_end)
    prev_expenses = Expense.objects.filter(date__gte=prev_start, date__lte=prev_end)

    # Summary stats
    agg = expenses.aggregate(
        total=Sum("amount"), avg=Avg("amount"), count=Count("id"),
        biggest=Max("amount"),
    )
    total = agg["total"] or Decimal("0")
    prev_total = prev_expenses.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    change_pct = round(float(total - prev_total) / float(prev_total) * 100, 1) if prev_total else 0

    # Category breakdown with budget comparison
    cat_breakdown = []
    cat_spending = (
        expenses.values("category__name", "category__id")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    for cs in cat_spending:
        cat_name = cs["category__name"] or "Uncategorised"
        cat_id = cs["category__id"]
        spent = cs["total"]

        # Sum budgets for this category across all months in the period
        budgets_in_period = Budget.objects.filter(
            category_id=cat_id,
            year__gte=period_start.year, year__lte=period_end.year,
        )
        # Filter months within period range
        total_budget = Decimal("0")
        for b in budgets_in_period:
            b_date = date(b.year, b.month, 1)
            if period_start <= b_date <= period_end:
                total_budget += b.amount

        gap = spent - total_budget if total_budget > 0 else None
        pct_of_budget = round(float(spent) / float(total_budget) * 100) if total_budget > 0 else None

        # Previous period for this category
        prev_cat_total = prev_expenses.filter(category_id=cat_id).aggregate(
            t=Sum("amount")
        )["t"] or Decimal("0")

        cat_breakdown.append({
            "name": cat_name,
            "spent": spent,
            "count": cs["count"],
            "budget": total_budget if total_budget > 0 else None,
            "gap": gap,
            "pct_of_budget": pct_of_budget,
            "prev_spent": prev_cat_total,
            "change": spent - prev_cat_total,
        })

    # Payment method breakdown
    pay_breakdown = (
        expenses.values("payment_method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Overall budget for the period
    overall_budgets = Budget.objects.filter(
        category__isnull=True,
        year__gte=period_start.year, year__lte=period_end.year,
    )
    overall_budget_total = Decimal("0")
    for b in overall_budgets:
        b_date = date(b.year, b.month, 1)
        if period_start <= b_date <= period_end:
            overall_budget_total += b.amount

    overall_gap = total - overall_budget_total if overall_budget_total > 0 else None

    # THE GOOD, THE NOT SO GOOD, AND RECOMMENDATIONS
    the_good = []
    the_not_so_good = []
    recommendations = []

    # Analyse: categories under budget
    for cb in cat_breakdown:
        if cb["budget"] and cb["gap"] is not None:
            if cb["gap"] < 0:  # Under budget
                the_good.append(
                    f"{cb['name']}: ₹{abs(cb['gap']):,.0f} under budget "
                    f"({cb['pct_of_budget']}% of allocation used)"
                )
            elif cb["gap"] > 0:  # Over budget
                the_not_so_good.append(
                    f"{cb['name']}: ₹{cb['gap']:,.0f} over budget "
                    f"({cb['pct_of_budget']}% of allocation used)"
                )
                recommendations.append(
                    f"Review {cb['name']} spending and set tighter weekly limits. "
                    f"Consider reducing by ₹{cb['gap']:,.0f} next period."
                )

    # Analyse: spending trend vs previous period
    if prev_total > 0:
        if total > prev_total:
            pct_up = round(float(total - prev_total) / float(prev_total) * 100, 1)
            the_not_so_good.append(
                f"Overall spending increased by {pct_up}% compared to previous period."
            )
            recommendations.append(
                f"Target a {min(pct_up, 15):.0f}% reduction next period by "
                f"focusing on the top over-budget categories."
            )
        else:
            pct_down = round(float(prev_total - total) / float(prev_total) * 100, 1)
            the_good.append(
                f"Overall spending decreased by {pct_down}% vs previous period — keep it up!"
            )

    # Analyse: categories with big jumps
    for cb in cat_breakdown:
        if cb["prev_spent"] > 0 and cb["change"] > 0:
            jump_pct = round(float(cb["change"]) / float(cb["prev_spent"]) * 100, 1)
            if jump_pct > 30:
                the_not_so_good.append(
                    f"{cb['name']} spending jumped {jump_pct}% vs previous period "
                    f"(₹{cb['prev_spent']:,.0f} → ₹{cb['spent']:,.0f})"
                )
        elif cb["prev_spent"] > 0 and cb["change"] < 0:
            drop_pct = round(float(abs(cb["change"])) / float(cb["prev_spent"]) * 100, 1)
            if drop_pct > 20:
                the_good.append(
                    f"{cb['name']} spending dropped {drop_pct}% vs previous period — well managed."
                )

    # Categories without budgets
    unbudgeted = [cb["name"] for cb in cat_breakdown if cb["budget"] is None and cb["name"] != "Uncategorised"]
    if unbudgeted:
        recommendations.append(
            f"Set budgets for: {', '.join(unbudgeted[:3])}{'...' if len(unbudgeted) > 3 else ''}. "
            f"Without limits, these categories can grow unchecked."
        )

    # Default messages if nothing to report
    if not the_good:
        the_good.append("Keep tracking your expenses to build positive spending patterns.")
    if not the_not_so_good:
        the_not_so_good.append("No major spending concerns detected for this period.")
    if not recommendations:
        recommendations.append("Continue maintaining your current spending discipline.")

    # Chart data for category bar chart
    chart_labels = [cb["name"] for cb in cat_breakdown[:8]]
    chart_spent = [float(cb["spent"]) for cb in cat_breakdown[:8]]
    chart_budget = [float(cb["budget"]) if cb["budget"] else 0 for cb in cat_breakdown[:8]]

    context = {
        "period": period,
        "period_label": period_label,
        "period_start": period_start,
        "period_end": period_end,
        "total": total,
        "prev_total": prev_total,
        "change_pct": change_pct,
        "count": agg["count"] or 0,
        "avg": agg["avg"] or Decimal("0"),
        "biggest": agg["biggest"] or Decimal("0"),
        "cat_breakdown": cat_breakdown,
        "pay_breakdown": pay_breakdown,
        "overall_budget_total": overall_budget_total,
        "overall_gap": overall_gap,
        "the_good": the_good,
        "the_not_so_good": the_not_so_good,
        "recommendations": recommendations,
        "chart_labels": json.dumps(chart_labels),
        "chart_spent": json.dumps(chart_spent),
        "chart_budget": json.dumps(chart_budget),
        "today": today,
    }
    return render(request, "expenses/reports.html", context)


def category_list(request):
    categories = Category.objects.annotate(
        total=Sum("expenses__amount"), count=Count("expenses"),
    ).order_by("name")
    return render(request, "expenses/category_list.html", {
        "categories": categories,
        "cat_color_map": get_category_color_map(),
    })


def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect("category_list")
    else:
        form = CategoryForm()
    return render(request, "expenses/category_form.html", {"form": form, "title": "Add Category"})


def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect("category_list")
    return render(request, "expenses/category_confirm_delete.html", {"category": category})
