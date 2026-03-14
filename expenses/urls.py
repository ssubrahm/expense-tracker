from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="expenses/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("", views.dashboard, name="dashboard"),
    path("spends/", views.spends, name="spends"),
    path("analytics/", views.analytics, name="analytics"),

    path("export/csv/", views.export_csv, name="export_csv"),
    path("export/dashboard-csv/", views.dashboard_export_csv, name="dashboard_export_csv"),
    path("expenses/add/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("budgets/", views.budget_list, name="budget_list"),
    path("budgets/add/", views.budget_create, name="budget_create"),
    path("budgets/<int:pk>/edit/", views.budget_edit, name="budget_edit"),
    path("budgets/<int:pk>/delete/", views.budget_delete, name="budget_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("family/", views.family_list, name="family_list"),
    path("family/add/", views.family_create, name="family_create"),
    path("family/<int:pk>/edit/", views.family_edit, name="family_edit"),
    path("family/<int:pk>/delete/", views.family_delete, name="family_delete"),
]
