from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    # Page Views (redirect dashboard to ledger)
    path('', views.dashboard, name='dashboard'),
    path('ledger/', views.ledger_page, name='ledger'),
    path('budget/', views.budget_page, name='budget'),
    path('overview/', views.overview_page, name='overview'),
    path('analytics/', views.analytics_page, name='analytics'),
    path('calendar/', views.calendar_page, name='calendar'),
    path('savings-goals/', views.savings_goals_page, name='savings-goals'),

    # Transaction Endpoints
    path('api/transactions/', views.transaction_list, name='transaction-list'),
    path('api/transactions/create/', views.transaction_create, name='transaction-create'),
    path('api/transactions/<int:txn_id>/', views.transaction_detail, name='transaction-detail'),

    # SubCategory / Pillar Endpoints
    path('api/subcategories/', views.subcategory_list, name='subcategory-list'),
    path('api/subcategories/create/', views.subcategory_create, name='subcategory-create'),
    path('api/subcategories/<int:sc_id>/', views.subcategory_delete, name='subcategory-delete'),
    path('api/pillars/', views.pillar_list, name='pillar-list'),

    # Budget Target Endpoints
    path('api/budget-targets/', views.budget_target_list, name='budget-target-list'),
    path('api/budget-targets/upsert/', views.budget_target_upsert, name='budget-target-upsert'),

    # Monthly Overview
    path('api/monthly-overview/', views.monthly_overview, name='monthly-overview'),

    # Analytics Endpoints
    path('api/analytics/income-vs-expenses/', views.analytics_income_vs_expenses, name='analytics-income-expenses'),
    path('api/analytics/expense-dispersal/', views.analytics_expense_dispersal, name='analytics-expense-dispersal'),
    path('api/analytics/debt-trajectory/', views.analytics_debt_trajectory, name='analytics-debt-trajectory'),

    # Calendar Endpoints
    path('api/calendar/events/', views.calendar_events, name='calendar-events'),
    path('api/calendar/day/', views.calendar_day_detail, name='calendar-day-detail'),

    # Savings Goal Endpoints
    path('api/savings-goals/', views.savings_goal_list, name='savings-goal-list'),
    path('api/savings-goals/create/', views.savings_goal_create, name='savings-goal-create'),
    path('api/savings-goals/<int:goal_id>/', views.savings_goal_detail, name='savings-goal-detail'),
    path('api/savings-goals/<int:goal_id>/contributions/', views.savings_goal_contributions, name='savings-goal-contributions'),
    path('api/contributions/<int:contribution_id>/', views.savings_contribution_detail, name='savings-contribution-detail'),

    # Quick Stats
    path('api/quick-stats/', views.quick_stats, name='quick-stats'),
]
