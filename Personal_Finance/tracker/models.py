from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


PILLAR_CHOICES = [
    ('INCOME', 'Income'),
    ('BILLS', 'Bills'),
    ('SUBSCRIPTIONS', 'Subscriptions'),
    ('EXPENSES', 'Expenses'),
    ('SAVINGS_INVESTMENTS', 'Savings & Investments'),
    ('DEBT', 'Debt'),
    ('CREDIT', 'Credit'),
]


class FinancialPillar(models.Model):
    name = models.CharField(max_length=50, choices=PILLAR_CHOICES, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.get_name_display()


class SubCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subcategories')
    pillar = models.ForeignKey(FinancialPillar, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    due_day = models.IntegerField(null=True, blank=True, help_text="Optional recurring due day (1-31)")

    class Meta:
        verbose_name_plural = 'Sub Categories'
        unique_together = ['user', 'pillar', 'name']
        ordering = ['pillar', 'name']

    def __str__(self):
        return f"{self.pillar.get_name_display()} \u2192 {self.name}"


class TransactionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    detail = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(FinancialPillar, on_delete=models.PROTECT, related_name='transactions')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name='transactions')
    card_credit_type = models.ForeignKey(
        SubCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='credit_card_transactions',
        help_text="Credit/Debt subcategory if funded via plastic/loans"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category']),
        ]

    def __str__(self):
        return f"{self.date} | {self.subcategory.name} | \u20b1{self.amount}"


class MonthlyBudgetTarget(models.Model):
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='budget_targets')
    year = models.IntegerField()
    month = models.IntegerField()
    budgeted_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ['subcategory', 'year', 'month']
        ordering = ['year', 'month', 'subcategory__pillar', 'subcategory__name']

    def __str__(self):
        return f"{self.subcategory.name} ({self.month:02d}/{self.year})"


class SavingsGoal(models.Model):
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='savings_goals')
    target_goal = models.DecimalField(max_digits=12, decimal_places=2)
    starting_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_contribution_target = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['subcategory__pillar', 'subcategory__name']

    def __str__(self):
        return f"Goal: {self.subcategory.name} \u2192 \u20b1{self.target_goal}"


class SavingsContribution(models.Model):
    savings_goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='contributions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.savings_goal.subcategory.name}: \u20b1{self.amount} ({self.date})"


class DebtBalanceHistory(models.Model):
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='debt_balances')
    year = models.IntegerField()
    month = models.IntegerField()
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name_plural = 'Debt Balance Histories'
        unique_together = ['subcategory', 'year', 'month']
        ordering = ['year', 'month', 'subcategory__name']

    def __str__(self):
        return f"{self.subcategory.name} ({self.month:02d}/{self.year}) \u20b1{self.remaining_balance}"
