from django.contrib import admin
from .models import FinancialPillar, SubCategory, TransactionLog, MonthlyBudgetTarget, SavingsGoal, DebtBalanceHistory


@admin.register(FinancialPillar)
class FinancialPillarAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'pillar', 'user', 'due_day']
    list_filter = ['pillar', 'user']
    search_fields = ['name']


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'subcategory', 'amount', 'category', 'user']
    list_filter = ['category', 'subcategory', 'date', 'user']
    search_fields = ['detail']
    date_hierarchy = 'date'


@admin.register(MonthlyBudgetTarget)
class MonthlyBudgetTargetAdmin(admin.ModelAdmin):
    list_display = ['subcategory', 'year', 'month', 'budgeted_amount']
    list_filter = ['year', 'month', 'subcategory__pillar']


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['subcategory', 'target_goal', 'starting_amount', 'monthly_contribution_target']


@admin.register(DebtBalanceHistory)
class DebtBalanceHistoryAdmin(admin.ModelAdmin):
    list_display = ['subcategory', 'year', 'month', 'remaining_balance']
    list_filter = ['year', 'month', 'subcategory']
