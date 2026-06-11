from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/csrf/', views.api_get_csrf, name='api-csrf'),
    path('api/pillars/', views.api_pillars, name='api-pillars'),
    path('api/subcategories/', views.api_subcategories, name='api-subcategories'),
    path('api/subcategories/create/', views.api_subcategory_create, name='api-subcategory-create'),
    path('api/subcategories/<int:sub_id>/delete/', views.api_subcategory_delete, name='api-subcategory-delete'),
    path('api/transactions/', views.api_transactions, name='api-transactions'),
    path('api/transactions/create/', views.api_transaction_create, name='api-transaction-create'),
    path('api/transactions/<int:txn_id>/delete/', views.api_transaction_delete, name='api-transaction-delete'),
    path('api/transactions/<int:txn_id>/update/', views.api_transaction_update, name='api-transaction-update'),
    path('api/budget-targets/', views.api_budget_targets, name='api-budget-targets'),
    path('api/transaction-matrix/', views.api_transaction_matrix, name='api-transaction-matrix'),
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api-dashboard-stats'),
    path('api/dashboard/charts/', views.api_chart_data, name='api-chart-data'),
    path('api/savings-goals/', views.api_savings_goals, name='api-savings-goals'),
    path('api/savings-goals/create/', views.api_savings_goal_create, name='api-savings-goal-create'),
    path('api/savings-goals/<int:goal_id>/update/', views.api_savings_goal_update, name='api-savings-goal-update'),
    path('api/debt-history/', views.api_debt_history, name='api-debt-history'),
    path('api/debt-history/update/', views.api_debt_history_update, name='api-debt-history-update'),
    path('api/calendar/events/', views.api_calendar_events, name='api-calendar-events'),
    path('api/financial-pillars/summary/', views.api_financial_pillars_summary, name='api-pillars-summary'),
]
