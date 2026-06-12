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


class ActiveTransactionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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
    account = models.ForeignKey('Account', on_delete=models.SET_NULL, null=True, blank=True)
    payment_mode = models.CharField(max_length=30, blank=True, default='')
    debt_history_id = models.IntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveTransactionManager()
    all_objects = models.Manager()

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
    date = models.DateField()
    year = models.IntegerField()
    month = models.IntegerField()
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2)
    payment_made = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=30, blank=True, default='')
    is_receivable = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Debt Balance Histories'
        unique_together = ['user', 'subcategory', 'date']

    def __str__(self):
        return f"{self.subcategory.name} ({self.month}/{self.year})"


class Account(models.Model):
    ACCOUNT_TYPES = [
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('credit', 'Credit Card'),
        ('cash', 'Cash'),
        ('investment', 'Investment'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='checking')
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=50)
    object_id = models.IntegerField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name}#{self.object_id}"


class RecurringTransaction(models.Model):
    INTERVAL_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    detail = models.TextField(blank=True, default='')
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default='monthly')
    next_due_date = models.DateField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_due_date']

    def __str__(self):
        return f"{self.subcategory.name} — ₱{self.amount} ({self.interval})"
