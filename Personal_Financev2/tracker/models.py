from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class FinancialPillar(models.Model):
    PILLAR_CHOICES = [
        ('INCOME', 'Income'),
        ('BILLS', 'Bills'),
        ('SUBSCRIPTIONS', 'Subscriptions'),
        ('EXPENSES', 'Expenses'),
        ('SAVINGS_INVESTMENTS', 'Savings & Investments'),
        ('DEBT', 'Debt'),
        ('CREDIT', 'Credit'),
    ]
    name = models.CharField(max_length=50, choices=PILLAR_CHOICES, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return self.get_name_display()


class SubCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    pillar = models.ForeignKey(FinancialPillar, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    due_day = models.IntegerField(null=True, blank=True)
    is_global = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Sub Categories'
        unique_together = ['user', 'pillar', 'name']

    def __str__(self):
        return f"{self.pillar.get_name_display()} → {self.name}"


class TransactionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    detail = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(FinancialPillar, on_delete=models.SET_NULL, null=True)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True)
    card_credit_type = models.ForeignKey(
        SubCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='credit_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.detail[:50]} | ₱{self.amount}"


class MonthlyBudgetTarget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    budgeted_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ['user', 'subcategory', 'year', 'month']

    def __str__(self):
        return f"{self.subcategory.name} ({self.month}/{self.year}): ₱{self.budgeted_amount}"


class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(
        SubCategory, on_delete=models.CASCADE,
        limit_choices_to={'pillar__name': 'SAVINGS_INVESTMENTS'}
    )
    target_goal = models.DecimalField(max_digits=12, decimal_places=2)
    starting_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_contribution_target = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ['user', 'subcategory']

    @property
    def total_saved(self):
        from django.db.models import Sum
        txns = TransactionLog.objects.filter(
            user=self.user, subcategory=self.subcategory, amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or 0
        return self.starting_amount + txns

    @property
    def left_to_save(self):
        remaining = self.target_goal - self.total_saved
        return max(remaining, 0)

    @property
    def progress_percent(self):
        if self.target_goal == 0:
            return 0
        pct = (self.total_saved / self.target_goal) * 100
        return round(min(pct, 100), 2)

    def __str__(self):
        return f"{self.subcategory.name}: ₱{self.total_saved}/₱{self.target_goal}"


class DebtBalanceHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2)
    payment_made = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = 'Debt Balance Histories'
        unique_together = ['user', 'subcategory', 'year', 'month']

    def __str__(self):
        return f"{self.subcategory.name} ({self.month}/{self.year})"
