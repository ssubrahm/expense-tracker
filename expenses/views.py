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
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

from .models import Expense, Category, Budget, SavedFilter, FamilyMember
from .forms import ExpenseForm, CategoryForm, BudgetForm, SavedFilterForm, ExpenseFilterForm, FamilyMemberForm


def _get_member(request):
    """Return the FamilyMember linked to the logged-in user, or None."""
    if request.user.is_authenticated and hasattr(request.user, "family_member"):
        return request.user.family_member
    return None


def _is_admin(request):
    """True if logged-in user is a family admin (Srinath) or Django superuser."""
    member = _get_member(request)
    return (member and member.is_family_admin) or request.user.is_superuser


def _filter_expenses(queryset, request):
    """All users see all family expenses (read access). No filtering by member for viewing."""
    return queryset


def _can_edit_expense(request, expense):
    """Non-admin can only edit/delete their own expenses."""
    if _is_admin(request):
        return True
    member = _get_member(request)
    return member and expense.spent_by == member


def _save_member_credentials(family_member, form):
    """Create or update User account from form's username/password fields."""
    from django.contrib.auth.models import User
    username = form.cleaned_data.get("username", "").strip()
    password = form.cleaned_data.get("password", "").strip()
    if not username:
        return
    if family_member.user:
        if family_member.user.username != username:
            family_member.user.username = username
            family_member.user.save()
        if password:
            family_member.user.set_password(password)
            family_member.user.save()
    else:
        user = User.objects.create_user(
            username=username,
            first_name=family_member.name,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        family_member.user = user
        family_member.save()


def _generate_recurring_expenses():
    """Generate any due recurring expenses. Safe to call multiple times."""
    today = date.today()
    recurring = Expense.objects.filter(
        recurrence__in=["monthly", "quarterly", "half_yearly", "annual"],
        recurring_parent__isnull=True,
    )
    for expense in recurring:
        latest = expense.recurring_children.order_by("-date").first()
        last_date = latest.date if latest else expense.date

        next_date = expense.next_occurrence_date(last_date)
        while next_date and next_date <= today:
            if not Expense.objects.filter(recurring_parent=expense, date=next_date).exists():
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
            last_date = next_date
            next_date = expense.next_occurrence_date(last_date)


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
    expenses = _filter_expenses(Expense.objects.select_related("category", "spent_by").all(), request)
    filter_form = ExpenseFilterForm(request.GET)

    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        categories = filter_form.cleaned_data.get("categories")
        payment_methods = filter_form.cleaned_data.get("payment_method")
        family_members = filter_form.cleaned_data.get("family_members")
        date_preset = filter_form.cleaned_data.get("date_preset")
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")
        amount_min = filter_form.cleaned_data.get("amount_min")
        amount_max = filter_form.cleaned_data.get("amount_max")

        if search:
            expenses = expenses.filter(Q(title__icontains=search) | Q(notes__icontains=search))
        if categories:
            expenses = expenses.filter(category__in=categories)
        if family_members:
            expenses = expenses.filter(spent_by__in=family_members)
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


@login_required
def dashboard(request):
    _generate_recurring_expenses()
    expenses = _filter_expenses(Expense.objects.select_related("category", "spent_by").all(), request)
    today = date.today()

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

    # Monthly trend
    monthly_qs = (
        expenses.annotate(month=TruncMonth("date"))
        .values("month").annotate(total=Sum("amount")).order_by("month")
    )
    monthly_labels = [m["month"].strftime("%b %Y") for m in monthly_qs if m["month"]]
    monthly_data = [float(m["total"]) for m in monthly_qs if m["month"]]

    # Category stacked data per month (top 5)
    top_cats = list(
        expenses.values("category__name")
        .annotate(t=Sum("amount")).order_by("-t")
        .values_list("category__name", flat=True)[:5]
    )
    stacked_datasets = []
    for i, cat in enumerate(top_cats):
        cat_monthly = (
            expenses.filter(category__name=cat)
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

    # Budget progress for current month
    current_month_total = (
        expenses.filter(date__year=today.year, date__month=today.month)
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
            expenses.filter(category=b.category, date__year=today.year, date__month=today.month)
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )
        pct = min(int(spent / b.amount * 100), 100) if b.amount > 0 else 0
        cat_budgets.append({"budget": b, "spent": spent, "pct": pct, "remaining": b.amount - spent})

    cat_color_map = get_category_color_map()

    # Family member spending breakdown
    by_member = (
        expenses.values("spent_by__name", "spent_by__avatar_color", "spent_by__id")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    member_labels = [r["spent_by__name"] or "Unassigned" for r in by_member]
    member_data = [float(r["total"]) for r in by_member]

    context = {
        "total": total,
        "avg_expense": avg_expense,
        "avg_daily": avg_daily,
        "biggest": biggest,
        "count": count,
        "by_category": by_category,
        "by_payment": by_payment,
        "by_member": by_member,
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_data": json.dumps(monthly_data),
        "stacked_datasets": json.dumps(stacked_datasets),
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "member_labels": json.dumps(member_labels),
        "member_data": json.dumps(member_data),
        "overall_budget": overall_budget,
        "current_month_total": current_month_total,
        "budget_pct": budget_pct,
        "cat_budgets": cat_budgets,
        "today": today,
        "cat_color_map": cat_color_map,
        "chart_colors": json.dumps(CHART_COLORS),
        "export_categories": Category.objects.all().order_by("name"),
    }
    return render(request, "expenses/dashboard.html", context)


@login_required
def spends(request):
    """Transactional expense listing with filters, sorting, and saved filters."""
    _generate_recurring_expenses()
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
            return redirect(request.META.get("HTTP_REFERER", "/spends/"))
        elif "delete_filter" in request.POST:
            fid = request.POST.get("filter_id")
            SavedFilter.objects.filter(pk=fid).delete()
            messages.success(request, "Saved filter deleted.")
            return redirect("spends")
        elif "bulk_action" in request.POST:
            selected = request.POST.getlist("selected")
            action = request.POST.get("bulk_action")
            if selected:
                qs = Expense.objects.filter(pk__in=selected)
                if not _is_admin(request):
                    member = _get_member(request)
                    qs = qs.filter(spent_by=member)
                    if not qs.exists():
                        messages.error(request, "You can only modify your own expenses.")
                        return redirect("spends")
                if action == "delete":
                    count_del = qs.count()
                    qs.delete()
                    messages.success(request, f"{count_del} expense(s) deleted.")
                elif action in dict(Expense.RECURRENCE_CHOICES):
                    qs.update(recurrence=action, is_recurring_source=(action != "one_time"))
                    messages.success(request, f"{qs.count()} expense(s) set to {dict(Expense.RECURRENCE_CHOICES)[action]}.")
            else:
                messages.warning(request, "No expenses selected.")
            return redirect("spends")

    expenses, filter_form = apply_filters(request)
    sort = request.GET.get("sort", "-date")
    sort_field = SORT_FIELDS.get(sort, "-date")
    expenses = expenses.order_by(sort_field)

    agg = expenses.aggregate(
        total=Sum("amount"), avg=Avg("amount"),
        biggest=Max("amount"), count=Count("id"),
    )
    total = agg["total"] or Decimal("0")
    count = agg["count"] or 0

    all_amounts = _filter_expenses(Expense.objects.all(), request).aggregate(mn=Min("amount"), mx=Max("amount"))
    amount_global_min = float(all_amounts["mn"] or 0)
    amount_global_max = float(all_amounts["mx"] or 1000)

    cat_color_map = get_category_color_map()

    context = {
        "expenses": expenses,
        "filter_form": filter_form,
        "saved_filters": saved_filters,
        "save_filter_form": SavedFilterForm(),
        "sort": sort,
        "total": total,
        "count": count,
        "amount_global_min": amount_global_min,
        "amount_global_max": amount_global_max,
        "current_qs": request.GET.urlencode(),
        "cat_color_map": cat_color_map,
        "chart_colors": json.dumps(CHART_COLORS),
        "recurrence_choices": Expense.RECURRENCE_CHOICES,
    }
    return render(request, "expenses/spends.html", context)


@login_required
def analytics(request):
    """Merged Analytics + Reports: trends, insights, period reports, budget comparison, assessment."""
    today = date.today()

    # ── Period handling (from Reports) ──
    period = request.GET.get("period", "monthly")
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
    else:
        period = "monthly"
        period_start = today.replace(day=1)
        period_end = today
        period_label = today.strftime("%B %Y")
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)

    # ── Family member filter ──
    member_id = request.GET.get("member")
    selected_member = None
    family_members = FamilyMember.objects.filter(is_active=True)

    all_expenses = Expense.objects.select_related("category", "spent_by").all()
    if member_id:
        try:
            selected_member = FamilyMember.objects.get(pk=member_id)
            all_expenses = all_expenses.filter(spent_by=selected_member)
        except FamilyMember.DoesNotExist:
            pass

    # ── Period expenses & previous period (for report section) ──
    period_expenses = all_expenses.filter(date__gte=period_start, date__lte=period_end)
    prev_expenses = all_expenses.filter(date__gte=prev_start, date__lte=prev_end)

    period_agg = period_expenses.aggregate(
        total=Sum("amount"), avg=Avg("amount"), count=Count("id"), biggest=Max("amount"),
    )
    period_total = period_agg["total"] or Decimal("0")
    prev_total = prev_expenses.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    change_pct = round(float(period_total - prev_total) / float(prev_total) * 100, 1) if prev_total else 0

    # ── Category breakdown with budget comparison (Report) ──
    cat_breakdown = []
    cat_spending = (
        period_expenses.values("category__name", "category__id")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    for cs in cat_spending:
        cat_name = cs["category__name"] or "Uncategorised"
        cat_id = cs["category__id"]
        spent = cs["total"]
        total_budget = Decimal("0")
        for b in Budget.objects.filter(category_id=cat_id, year__gte=period_start.year, year__lte=period_end.year):
            b_date = date(b.year, b.month, 1)
            if period_start <= b_date <= period_end:
                total_budget += b.amount
        gap = spent - total_budget if total_budget > 0 else None
        pct_of_budget = round(float(spent) / float(total_budget) * 100) if total_budget > 0 else None
        prev_cat_total = prev_expenses.filter(category_id=cat_id).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        cat_breakdown.append({
            "name": cat_name, "spent": spent, "count": cs["count"],
            "budget": total_budget if total_budget > 0 else None,
            "gap": gap, "pct_of_budget": pct_of_budget,
            "prev_spent": prev_cat_total, "change": spent - prev_cat_total,
        })

    # Overall budget for the period
    overall_budget_total = Decimal("0")
    for b in Budget.objects.filter(category__isnull=True, year__gte=period_start.year, year__lte=period_end.year):
        b_date = date(b.year, b.month, 1)
        if period_start <= b_date <= period_end:
            overall_budget_total += b.amount
    overall_gap = period_total - overall_budget_total if overall_budget_total > 0 else None

    # Payment method breakdown (period)
    pay_breakdown = (
        period_expenses.values("payment_method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    # Chart data for category vs budget bar chart
    rpt_chart_labels = [cb["name"] for cb in cat_breakdown[:8]]
    rpt_chart_spent = [float(cb["spent"]) for cb in cat_breakdown[:8]]
    rpt_chart_budget = [float(cb["budget"]) if cb["budget"] else 0 for cb in cat_breakdown[:8]]

    # ── Assessment: The Good / The Not So Good / Recommendations ──
    the_good, the_not_so_good, recommendations = [], [], []
    for cb in cat_breakdown:
        if cb["budget"] and cb["gap"] is not None:
            if cb["gap"] < 0:
                the_good.append(f"{cb['name']}: ₹{abs(cb['gap']):,.0f} under budget ({cb['pct_of_budget']}% used)")
            elif cb["gap"] > 0:
                the_not_so_good.append(f"{cb['name']}: ₹{cb['gap']:,.0f} over budget ({cb['pct_of_budget']}% used)")
                recommendations.append(f"Review {cb['name']} spending. Consider reducing by ₹{cb['gap']:,.0f} next period.")
    if prev_total > 0:
        if period_total > prev_total:
            pct_up = round(float(period_total - prev_total) / float(prev_total) * 100, 1)
            the_not_so_good.append(f"Overall spending increased by {pct_up}% compared to previous period.")
            recommendations.append(f"Target a {min(pct_up, 15):.0f}% reduction next period.")
        else:
            pct_down = round(float(prev_total - period_total) / float(prev_total) * 100, 1)
            the_good.append(f"Overall spending decreased by {pct_down}% vs previous period — keep it up!")
    for cb in cat_breakdown:
        if cb["prev_spent"] > 0 and cb["change"] > 0:
            jump_pct = round(float(cb["change"]) / float(cb["prev_spent"]) * 100, 1)
            if jump_pct > 30:
                the_not_so_good.append(f"{cb['name']} spending jumped {jump_pct}% vs previous period.")
        elif cb["prev_spent"] > 0 and cb["change"] < 0:
            drop_pct = round(float(abs(cb["change"])) / float(cb["prev_spent"]) * 100, 1)
            if drop_pct > 20:
                the_good.append(f"{cb['name']} spending dropped {drop_pct}% — well managed.")
    unbudgeted = [cb["name"] for cb in cat_breakdown if cb["budget"] is None and cb["name"] != "Uncategorised"]
    if unbudgeted:
        recommendations.append(f"Set budgets for: {', '.join(unbudgeted[:3])}{'...' if len(unbudgeted) > 3 else ''}.")
    if not the_good:
        the_good.append("Keep tracking your expenses to build positive spending patterns.")
    if not the_not_so_good:
        the_not_so_good.append("No major spending concerns detected for this period.")
    if not recommendations:
        recommendations.append("Continue maintaining your current spending discipline.")

    # ── Family member breakdown for period (Report) ──
    all_period_expenses = Expense.objects.filter(date__gte=period_start, date__lte=period_end)
    all_prev_expenses = Expense.objects.filter(date__gte=prev_start, date__lte=prev_end)
    member_breakdown = []
    for fm in family_members:
        fm_spent = all_period_expenses.filter(spent_by=fm).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        fm_prev = all_prev_expenses.filter(spent_by=fm).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        fm_count = all_period_expenses.filter(spent_by=fm).count()
        fm_change = round(float(fm_spent - fm_prev) / float(fm_prev) * 100, 1) if fm_prev > 0 else 0
        fm_top = all_period_expenses.filter(spent_by=fm).values("category__name").annotate(t=Sum("amount")).order_by("-t").first()
        member_breakdown.append({
            "member": fm, "spent": fm_spent, "prev": fm_prev, "count": fm_count,
            "change": fm_change,
            "top_category": fm_top["category__name"] if fm_top else "—",
            "pct_of_total": round(float(fm_spent) / float(period_total) * 100, 1) if period_total else 0,
        })
    member_breakdown.sort(key=lambda x: x["spent"], reverse=True)
    report_member_labels = [mb["member"].name for mb in member_breakdown]
    report_member_data = [float(mb["spent"]) for mb in member_breakdown]

    # ── Trends & Insights (from old Analytics — uses all_expenses, all-time) ──
    monthly_qs = (
        all_expenses.annotate(month=TruncMonth("date"))
        .values("month").annotate(total=Sum("amount"), count=Count("id"))
        .order_by("month")
    )
    monthly_labels = [m["month"].strftime("%b %Y") for m in monthly_qs if m["month"]]
    monthly_totals = [float(m["total"]) for m in monthly_qs if m["month"]]

    mom_changes = []
    for i, v in enumerate(monthly_totals):
        if i == 0:
            mom_changes.append(0)
        else:
            prev = monthly_totals[i - 1]
            mom_changes.append(round((v - prev) / prev * 100, 1) if prev else 0)

    twelve_weeks_ago = today - timedelta(weeks=12)
    weekly_qs = (
        all_expenses.filter(date__gte=twelve_weeks_ago)
        .annotate(week=TruncWeek("date"))
        .values("week").annotate(total=Sum("amount")).order_by("week")
    )
    weekly_labels = [w["week"].strftime("W%W %b") for w in weekly_qs if w["week"]]
    weekly_data = [float(w["total"]) for w in weekly_qs if w["week"]]
    wow_changes = []
    for i, val in enumerate(weekly_data):
        if i == 0 or weekly_data[i - 1] == 0:
            wow_changes.append(0)
        else:
            wow_changes.append(round((val - weekly_data[i - 1]) / weekly_data[i - 1] * 100, 1))

    # Heatmap
    heatmap_raw = all_expenses.filter(date__gte=today - timedelta(days=84)).values("date").annotate(total=Sum("amount"))
    heatmap = defaultdict(float)
    for row in heatmap_raw:
        heatmap[row["date"].isoformat()] = float(row["total"])
    heatmap_weeks = []
    start = today - timedelta(days=today.weekday() + 7 * 11)
    for w in range(12):
        week = []
        for d in range(7):
            day = start + timedelta(days=w * 7 + d)
            week.append({"date": day.isoformat(), "amount": heatmap.get(day.isoformat(), 0)})
        heatmap_weeks.append(week)

    # Category stacked trend
    top_cats = list(
        all_expenses.values("category__name").annotate(t=Sum("amount")).order_by("-t")
        .values_list("category__name", flat=True)[:6]
    )
    stacked = []
    for i, cat in enumerate(top_cats):
        cat_qs = (
            all_expenses.filter(category__name=cat).annotate(month=TruncMonth("date"))
            .values("month").annotate(total=Sum("amount")).order_by("month")
        )
        cat_map_d = {m["month"].strftime("%b %Y"): float(m["total"]) for m in cat_qs if m["month"]}
        stacked.append({
            "label": cat or "Uncategorised",
            "data": [cat_map_d.get(l, 0) for l in monthly_labels],
            "backgroundColor": CHART_COLORS[i % len(CHART_COLORS)],
            "borderColor": CHART_COLORS[i % len(CHART_COLORS)],
            "fill": False, "tension": 0.4,
        })

    top_expenses = all_expenses.order_by("-amount")[:10]

    # ── Smart Insights ──
    insights = []
    if len(monthly_totals) >= 2:
        last = monthly_totals[-1]
        prev_m = monthly_totals[-2]
        diff = last - prev_m
        pct = round(abs(diff) / prev_m * 100, 1) if prev_m else 0
        if diff > 0:
            insights.append({"type": "warning", "icon": "📈",
                "text": f"Spending is up {pct}% vs last month (₹{last:,.2f} vs ₹{prev_m:,.2f})",
                "nudge": f"Reduce by ₹{diff:,.0f} this month to match last month's level."})
        else:
            yearly_proj = abs(diff) * 12
            insights.append({"type": "success", "icon": "📉",
                "text": f"Spending is down {pct}% vs last month — great job!",
                "nudge": f"At this rate, you'll save ₹{yearly_proj:,.0f} over a year."})

    this_month_cat = (
        all_expenses.filter(date__year=today.year, date__month=today.month)
        .values("category__name").annotate(t=Sum("amount")).order_by("-t").first()
    )
    if this_month_cat:
        cn = this_month_cat["category__name"] or "Uncategorised"
        ct = this_month_cat["t"]
        cb_obj = Budget.objects.filter(category__name=cn, year=today.year, month=today.month).first()
        if cb_obj and ct > cb_obj.amount:
            nudge = f"You're ₹{ct - cb_obj.amount:,.0f} over your {cn} budget."
        elif cb_obj:
            nudge = f"₹{cb_obj.amount - ct:,.0f} remaining in your {cn} budget."
        else:
            nudge = f"Consider setting a budget for {cn}."
        insights.append({"type": "info", "icon": "🏆", "text": f"Top category this month: {cn} (₹{ct:,.2f})", "nudge": nudge})

    biggest_day = all_expenses.values("date").annotate(t=Sum("amount")).order_by("-t").first()
    if biggest_day:
        insights.append({"type": "info", "icon": "🔥",
            "text": f"Biggest spending day: {biggest_day['date']} (₹{biggest_day['t']:,.2f})",
            "nudge": "Space out large purchases across the month for steadier cash flow."})

    weekday_avg = all_expenses.filter(date__week_day__in=[2,3,4,5,6]).aggregate(a=Avg("amount"))["a"] or 0
    weekend_avg = all_expenses.filter(date__week_day__in=[1,7]).aggregate(a=Avg("amount"))["a"] or 0
    if weekday_avg and weekend_avg:
        nudge = "Your weekends cost significantly more. Try a no-spend Saturday challenge." if float(weekend_avg) > float(weekday_avg) * 1.2 else "Spending is well-balanced across the week."
        insights.append({"type": "info", "icon": "📅", "text": f"Weekend avg ₹{weekend_avg:,.2f} vs weekday ₹{weekday_avg:,.2f}", "nudge": nudge})

    top_payment = all_expenses.values("payment_method").annotate(c=Count("id")).order_by("-c").first()
    if top_payment:
        pm_display = dict(Expense.PAYMENT_CHOICES).get(top_payment["payment_method"], top_payment["payment_method"])
        total_txns = all_expenses.count()
        pm_pct = round(top_payment["c"] / total_txns * 100) if total_txns else 0
        nudge = f"{pm_display} is {pm_pct}% of all transactions." if pm_pct > 70 else "Good diversification across payment methods."
        insights.append({"type": "info", "icon": "💳", "text": f"Most used: {pm_display} ({top_payment['c']} txns, {pm_pct}%)", "nudge": nudge})

    overall = all_expenses.aggregate(total=Sum("amount"), avg=Avg("amount"), count=Count("id"), biggest=Max("amount"))

    # Family member all-time comparison
    base_expenses = Expense.objects.select_related("spent_by").all()
    member_spending = []
    for fm in family_members:
        fm_total = base_expenses.filter(spent_by=fm).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        fm_count = base_expenses.filter(spent_by=fm).count()
        fm_this_month = base_expenses.filter(spent_by=fm, date__year=today.year, date__month=today.month).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        fm_top_cat = base_expenses.filter(spent_by=fm).values("category__name").annotate(t=Sum("amount")).order_by("-t").first()
        member_spending.append({
            "member": fm, "total": fm_total, "count": fm_count,
            "this_month": fm_this_month,
            "top_category": fm_top_cat["category__name"] if fm_top_cat else "—",
        })
    member_spending.sort(key=lambda x: x["total"], reverse=True)

    context = {
        # Period / Report data
        "period": period, "period_label": period_label,
        "period_start": period_start, "period_end": period_end,
        "p_total": period_total, "prev_total": prev_total, "change_pct": change_pct,
        "p_count": period_agg["count"] or 0,
        "p_avg": period_agg["avg"] or Decimal("0"),
        "p_biggest": period_agg["biggest"] or Decimal("0"),
        "cat_breakdown": cat_breakdown,
        "pay_breakdown": pay_breakdown,
        "overall_budget_total": overall_budget_total, "overall_gap": overall_gap,
        "the_good": the_good, "the_not_so_good": the_not_so_good, "recommendations": recommendations,
        "rpt_chart_labels": json.dumps(rpt_chart_labels),
        "rpt_chart_spent": json.dumps(rpt_chart_spent),
        "rpt_chart_budget": json.dumps(rpt_chart_budget),
        "member_breakdown": member_breakdown,
        "report_member_labels": json.dumps(report_member_labels),
        "report_member_data": json.dumps(report_member_data),
        # Trends / Insights data
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_totals": json.dumps(monthly_totals),
        "mom_changes": json.dumps(mom_changes),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_data": json.dumps(weekly_data),
        "wow_changes": json.dumps(wow_changes),
        "stacked_datasets": json.dumps(stacked),
        "heatmap_weeks": heatmap_weeks,
        "top_expenses": top_expenses,
        "insights": insights,
        "overall": overall,
        "today": today,
        "cat_color_map": get_category_color_map(),
        "chart_colors": json.dumps(CHART_COLORS),
        "family_members": family_members,
        "selected_member": selected_member,
        "member_spending": member_spending,
        "member_chart_labels": json.dumps([ms["member"].name for ms in member_spending]),
        "member_chart_data": json.dumps([float(ms["total"]) for ms in member_spending]),
        "member_month_data": json.dumps([float(ms["this_month"]) for ms in member_spending]),
    }
    return render(request, "expenses/analytics.html", context)


@login_required
def budget_list(request):
    if request.method == "POST" and "bulk_action" in request.POST:
        if not _is_admin(request):
            messages.error(request, "Only the family admin can manage budgets.")
            return redirect("budget_list")
        selected = request.POST.getlist("selected")
        action = request.POST.get("bulk_action")
        if selected and action == "delete":
            count_del = Budget.objects.filter(pk__in=selected).count()
            Budget.objects.filter(pk__in=selected).delete()
            messages.success(request, f"{count_del} budget(s) deleted.")
        else:
            messages.warning(request, "No budgets selected.")
        return redirect("budget_list")

    today = date.today()
    budgets = Budget.objects.select_related("category").order_by("-year", "-month")

    cat_budget_data = []
    overall_budget_data = []

    # Sum of category budgets per month (for reference on overall cards)
    cat_sums = defaultdict(Decimal)

    for b in budgets:
        if b.category:
            spent = (
                Expense.objects.filter(
                    date__year=b.year, date__month=b.month,
                    category=b.category,
                ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            )
            cat_sums[(b.year, b.month)] += b.amount
        else:
            spent = (
                Expense.objects.filter(date__year=b.year, date__month=b.month)
                .aggregate(t=Sum("amount"))["t"] or Decimal("0")
            )
        remaining = b.amount - spent
        pct = min(int(spent / b.amount * 100), 100) if b.amount > 0 else 0
        entry = {"budget": b, "spent": spent, "remaining": remaining, "pct": pct}
        if b.category:
            cat_budget_data.append(entry)
        else:
            overall_budget_data.append(entry)

    # Auto-create overall budget for current month if category budgets exist but no overall
    current_cat_sum = cat_sums.get((today.year, today.month), Decimal("0"))
    has_current_overall = any(
        o["budget"].year == today.year and o["budget"].month == today.month
        for o in overall_budget_data
    )
    if current_cat_sum > 0 and not has_current_overall:
        overall, created = Budget.objects.get_or_create(
            category=None, year=today.year, month=today.month,
            defaults={"amount": current_cat_sum},
        )
        if created:
            spent = (
                Expense.objects.filter(date__year=today.year, date__month=today.month)
                .aggregate(t=Sum("amount"))["t"] or Decimal("0")
            )
            remaining = overall.amount - spent
            pct = min(int(spent / overall.amount * 100), 100) if overall.amount > 0 else 0
            overall_budget_data.insert(0, {
                "budget": overall, "spent": spent, "remaining": remaining, "pct": pct,
            })

    # Attach category sum reference to each overall entry
    for o in overall_budget_data:
        o["cat_sum"] = cat_sums.get((o["budget"].year, o["budget"].month), Decimal("0"))

    return render(request, "expenses/budget_list.html", {
        "cat_budget_data": cat_budget_data,
        "overall_budget_data": overall_budget_data,
        "cat_color_map": get_category_color_map(),
    })


@login_required
def budget_create(request):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can create budgets.")
        return redirect("budget_list")
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


@login_required
def budget_edit(request, pk):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can edit budgets.")
        return redirect("budget_list")
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == "POST":
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget updated.")
            return redirect("budget_list")
    else:
        form = BudgetForm(instance=budget)
    cat_name = budget.category.name if budget.category else "Overall"
    return render(request, "expenses/budget_form.html", {
        "form": form, "title": f"Edit Budget — {cat_name}", "budget": budget,
    })


@login_required
def budget_delete(request, pk):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can delete budgets.")
        return redirect("budget_list")
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted.")
        return redirect("budget_list")
    return render(request, "expenses/budget_confirm_delete.html", {"budget": budget})


@login_required
def export_csv(request):
    expenses, _ = apply_filters(request)
    sort = request.GET.get("sort", "-date")
    expenses = expenses.order_by(SORT_FIELDS.get(sort, "-date"))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Spent By", "Amount", "Payment Method", "Recurrence", "Notes"])
    for e in expenses:
        writer.writerow([e.date, e.title, e.category.name if e.category else "",
                         e.spent_by.name if e.spent_by else "",
                         e.amount, e.get_payment_method_display(),
                         e.get_recurrence_display(), e.notes])
    return response


@login_required
def expense_create(request):
    member = _get_member(request)
    is_admin = _is_admin(request)
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            if expense.recurrence != "one_time":
                expense.is_recurring_source = True
            if not is_admin or not expense.spent_by:
                expense.spent_by = member
            expense.save()
            messages.success(request, "Expense added.")
            return redirect("spends")
    else:
        form = ExpenseForm(initial={"date": date.today(), "spent_by": member})
    if not is_admin:
        form.fields["spent_by"].disabled = True
    return render(request, "expenses/expense_form.html", {"form": form, "title": "Add Expense"})


@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if not _can_edit_expense(request, expense):
        messages.error(request, "You can only edit your own expenses.")
        return redirect("spends")
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.is_recurring_source = (exp.recurrence != "one_time" and exp.recurring_parent is None)
            exp.save()
            messages.success(request, "Expense updated.")
            return redirect("spends")
    else:
        form = ExpenseForm(instance=expense)
    if not _is_admin(request):
        form.fields["spent_by"].disabled = True
    return render(request, "expenses/expense_form.html", {"form": form, "title": "Edit Expense", "expense": expense})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if not _can_edit_expense(request, expense):
        messages.error(request, "You can only delete your own expenses.")
        return redirect("spends")
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted.")
        return redirect("dashboard")
    return render(request, "expenses/expense_confirm_delete.html", {"expense": expense})


@login_required
@login_required
def profile(request):
    """Profile page: change password."""
    member = _get_member(request)
    if request.method == "POST":
        pw_form = PasswordChangeForm(request.user, request.POST)
        if pw_form.is_valid():
            user = pw_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password updated successfully.")
            return redirect("profile")
    else:
        pw_form = PasswordChangeForm(request.user)
    return render(request, "expenses/profile.html", {
        "pw_form": pw_form,
        "member": member,
        "is_admin": _is_admin(request),
    })


@login_required
def category_list(request):
    categories = Category.objects.annotate(
        total=Sum("expenses__amount"), count=Count("expenses"),
    ).order_by("name")
    return render(request, "expenses/category_list.html", {
        "categories": categories,
        "cat_color_map": get_category_color_map(),
    })


@login_required
def category_create(request):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can add categories.")
        return redirect("category_list")
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect("category_list")
    else:
        form = CategoryForm()
    return render(request, "expenses/category_form.html", {"form": form, "title": "Add Category"})


@login_required
def category_delete(request, pk):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can delete categories.")
        return redirect("category_list")
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect("category_list")
    return render(request, "expenses/category_confirm_delete.html", {"category": category})


# ── Family Member CRUD ──────────────────────────────────────────

@login_required
def family_list(request):
    members = FamilyMember.objects.filter(is_active=True).select_related("user").annotate(
        total=Sum("expenses__amount"),
        count=Count("expenses"),
    ).order_by("name")
    today = date.today()
    member_data = []
    for m in members:
        this_month = Expense.objects.filter(
            spent_by=m, date__year=today.year, date__month=today.month
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        top_cat = (
            Expense.objects.filter(spent_by=m)
            .values("category__name").annotate(t=Sum("amount")).order_by("-t").first()
        )
        member_data.append({
            "member": m,
            "total": m.total or Decimal("0"),
            "count": m.count or 0,
            "this_month": this_month,
            "top_category": top_cat["category__name"] if top_cat else "—",
        })
    return render(request, "expenses/family_list.html", {
        "member_data": member_data,
        "chart_colors": json.dumps(CHART_COLORS),
    })


@login_required
def family_create(request):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can add members.")
        return redirect("family_list")
    if request.method == "POST":
        form = FamilyMemberForm(request.POST)
        if form.is_valid():
            fm = form.save()
            _save_member_credentials(fm, form)
            messages.success(request, f"Family member '{form.cleaned_data['name']}' added.")
            return redirect("family_list")
    else:
        form = FamilyMemberForm()
    return render(request, "expenses/family_form.html", {"form": form, "title": "Add Family Member"})


@login_required
def family_edit(request, pk):
    member = get_object_or_404(FamilyMember, pk=pk)
    current_member = _get_member(request)
    is_admin = _is_admin(request)
    is_own = current_member and current_member.pk == member.pk

    if not is_admin and not is_own:
        messages.error(request, "You can only edit your own profile.")
        return redirect("family_list")

    if request.method == "POST":
        if is_admin:
            form = FamilyMemberForm(request.POST, instance=member)
        else:
            form = FamilyMemberForm(request.POST, instance=member)
        if form.is_valid():
            fm = form.save()
            _save_member_credentials(fm, form)
            messages.success(request, f"'{member.name}' updated.")
            return redirect("family_list")
    else:
        form = FamilyMemberForm(instance=member)

    if not is_admin:
        for field_name in ["relationship", "is_active"]:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

    return render(request, "expenses/family_form.html", {
        "form": form, "title": f"Edit {member.name}", "member": member,
        "is_admin": is_admin, "is_own": is_own,
    })


@login_required
def family_delete(request, pk):
    if not _is_admin(request):
        messages.error(request, "Only the family admin can remove members.")
        return redirect("family_list")
    member = get_object_or_404(FamilyMember, pk=pk)
    if request.method == "POST":
        member.is_active = False
        member.save()
        messages.success(request, f"'{member.name}' deactivated.")
        return redirect("family_list")
    return render(request, "expenses/family_confirm_delete.html", {"member": member})


# ── Advanced Export System (V2) ─────────────────────────────────

@login_required
def export_preview(request):
    """AJAX endpoint: returns filtered expense preview + count as JSON."""
    qs = _build_export_queryset(request)
    count = qs.count()
    preview = []
    for e in qs[:10]:
        preview.append({
            "date": e.date.isoformat(),
            "title": e.title,
            "category": e.category.name if e.category else "",
            "spent_by": e.spent_by.name if e.spent_by else "",
            "amount": str(e.amount),
            "payment_method": e.get_payment_method_display(),
        })
    return JsonResponse({"count": count, "preview": preview})


@login_required
def export_download(request):
    """Download filtered expenses in CSV, JSON, or PDF format."""
    qs = _build_export_queryset(request)
    fmt = request.GET.get("format", "csv")
    filename = request.GET.get("filename", "expenses").strip() or "expenses"
    filename = "".join(c for c in filename if c.isalnum() or c in "-_ ")

    if fmt == "json":
        return _export_json(qs, filename)
    elif fmt == "pdf":
        return _export_pdf(qs, filename)
    return _export_csv_v2(qs, filename)


def _build_export_queryset(request):
    """Build filtered queryset from export request params."""
    qs = Expense.objects.select_related("category", "spent_by").order_by("-date")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    categories = request.GET.getlist("categories")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if categories:
        qs = qs.filter(category__pk__in=categories)
    return qs


def _export_csv_v2(qs, filename):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Spent By", "Amount", "Payment Method", "Recurrence", "Notes"])
    for e in qs:
        writer.writerow([
            e.date, e.title, e.category.name if e.category else "",
            e.spent_by.name if e.spent_by else "", e.amount,
            e.get_payment_method_display(), e.get_recurrence_display(), e.notes,
        ])
    return response


def _export_json(qs, filename):
    data = []
    for e in qs:
        data.append({
            "date": e.date.isoformat(),
            "title": e.title,
            "category": e.category.name if e.category else "",
            "spent_by": e.spent_by.name if e.spent_by else "",
            "amount": float(e.amount),
            "payment_method": e.get_payment_method_display(),
            "recurrence": e.get_recurrence_display(),
            "notes": e.notes or "",
        })
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
    return response


def _export_pdf(qs, filename):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"OurMoneyTrail — Expense Export", styles["Title"]))
    elements.append(Paragraph(f"{qs.count()} records", styles["Normal"]))
    elements.append(Spacer(1, 8*mm))

    header = ["Date", "Title", "Category", "Spent By", "Amount", "Payment", "Notes"]
    table_data = [header]
    for e in qs:
        table_data.append([
            str(e.date), e.title[:30],
            (e.category.name if e.category else "")[:20],
            (e.spent_by.name if e.spent_by else "")[:15],
            f"₹{e.amount:,.2f}",
            e.get_payment_method_display()[:15],
            (e.notes or "")[:25],
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)

    doc.build(elements)
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response
