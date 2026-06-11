import random
import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from tracker.models import FinancialPillar, SubCategory, TransactionLog, MonthlyBudgetTarget, DebtBalanceHistory, SavingsGoal


random.seed(42)

MONTHLY_PATTERNS = {
    'INCOME': {
        'Salary': {'amount': (50000, 60000), 'freq': '1st', 'detail': 'Monthly Salary'},
        'Salary (2nd)': {'amount': (20000, 30000), 'freq': '15th', 'detail': '2nd Salary'},
        'Interest': {'amount': (100, 500), 'freq': 'random', 'detail': 'Bank Interest'},
        'Payback': {'amount': (1000, 5000), 'freq': 'random', 'detail': 'Payback from friend'},
    },
    'BILLS': {
        'PLDT': {'amount': (2500, 2500), 'freq': 'monthly', 'detail': 'PLDT Fiber'},
    },
    'SUBSCRIPTIONS': {
        'Tinder': {'amount': (450, 450), 'freq': 'monthly', 'detail': 'Tinder Gold'},
        'Bumble': {'amount': (500, 500), 'freq': 'monthly', 'detail': 'Bumble Boost'},
        'Netflix (1st)': {'amount': (499, 499), 'freq': 'monthly', 'detail': 'Netflix UHD 1st'},
        'Netflix (2nd)': {'amount': (499, 499), 'freq': 'monthly', 'detail': 'Netflix UHD 2nd'},
        'Disney': {'amount': (399, 399), 'freq': 'monthly', 'detail': 'Disney+'},
    },
    'EXPENSES': {
        'Facebook': {'amount': (500, 2000), 'freq': 'random', 'detail': 'Facebook Ads'},
        'Google Platform': {'amount': (200, 1000), 'freq': 'random', 'detail': 'Google Cloud'},
        'Personal': {'amount': (2000, 5000), 'freq': 'random', 'detail': 'Personal expenses'},
        'Split Payment': {'amount': (1000, 4000), 'freq': 'random', 'detail': 'Split'},
        'Installment': {'amount': (1000, 3000), 'freq': 'monthly', 'detail': 'Monthly installment'},
        'Shoppe': {'amount': (300, 1500), 'freq': 'random', 'detail': 'Shopee purchase'},
        'Mom credit': {'amount': (1000, 3000), 'freq': 'random', 'detail': 'Allowance for Mom'},
        'Tita Maite Credit': {'amount': (500, 2000), 'freq': 'random', 'detail': 'Support for Tita Maite'},
        'Travel': {'amount': (3000, 15000), 'freq': 'quarterly', 'detail': 'Travel expenses'},
    },
    'SAVINGS_INVESTMENTS': {
        'BDO Saving Personal': {'amount': (5000, 10000), 'freq': 'monthly', 'detail': 'BDO savings deposit'},
        'EastWest Saving Personal': {'amount': (3000, 8000), 'freq': 'monthly', 'detail': 'EastWest savings deposit'},
    },
    'DEBT': {
        'Loan (Mom)': {'amount': (3000, 5000), 'freq': 'monthly', 'detail': 'Loan payment to Mom'},
        'Loan 1st': {'amount': (4000, 5000), 'freq': 'monthly', 'detail': 'Loan 1st payment'},
        'Loan 2nd': {'amount': (3000, 4000), 'freq': 'monthly', 'detail': 'Loan 2nd payment'},
        'Loan 3rd': {'amount': (2000, 3000), 'freq': 'monthly', 'detail': 'Loan 3rd payment'},
    },
    'CREDIT': {
        'Credit Card BDO': {'amount': (5000, 15000), 'freq': 'monthly', 'detail': 'BDO credit card bill'},
        'Credit Card Atome': {'amount': (2000, 5000), 'freq': 'monthly', 'detail': 'Atome payment'},
        'Credit Card EastWest': {'amount': (3000, 8000), 'freq': 'monthly', 'detail': 'EastWest credit card bill'},
        'Credit UnionBank': {'amount': (2000, 6000), 'freq': 'monthly', 'detail': 'UnionBank credit card bill'},
        'Credit Card EastWest Acer': {'amount': (1000, 3000), 'freq': 'monthly', 'detail': 'EastWest Acer card'},
        'Credit Card SM Store dept': {'amount': (500, 2000), 'freq': 'monthly', 'detail': 'SM Store dept'},
        'Credit Card Store dept Fili': {'amount': (500, 1500), 'freq': 'monthly', 'detail': 'Store dept Fili'},
        'Credit Card Store dept 2nd - Fili': {'amount': (500, 1500), 'freq': 'monthly', 'detail': 'Store dept 2nd Fili'},
        'Credit Card MAC Apple': {'amount': (1000, 3000), 'freq': 'monthly', 'detail': 'MAC Apple Installment'},
    },
}

MONTHLY_BILLS_SUBCATS = ['PLDT']
MONTHLY_SUBSCRIPTION_SUBCATS = ['Tinder', 'Bumble', 'Netflix (1st)', 'Netflix (2nd)', 'Disney']
MONTHLY_SAVINGS_SUBCATS = ['BDO Saving Personal', 'EastWest Saving Personal']
MONTHLY_DEBT_SUBCATS = ['Loan (Mom)', 'Loan 1st', 'Loan 2nd', 'Loan 3rd']
MONTHLY_CREDIT_SUBCATS = [
    'Credit Card BDO', 'Credit Card Atome', 'Credit Card EastWest',
    'Credit UnionBank', 'Credit Card EastWest Acer',
    'Credit Card SM Store dept', 'Credit Card Store dept Fili',
    'Credit Card Store dept 2nd - Fili', 'Credit Card MAC Apple',
]


def random_amount(min_v, max_v):
    return Decimal(str(round(random.uniform(min_v, max_v), 2)))


def pick_random_day(year, month):
    _, days = calendar.monthrange(year, month)
    return random.randint(1, days)


def pick_day_in_range(year, month, day_start, day_end):
    _, days = calendar.monthrange(year, month)
    return random.randint(max(1, day_start), min(days, day_end))


class Command(BaseCommand):
    help = 'Seeds sample transaction data for the admin user across 12 months'

    def handle(self, *args, **options):
        self.stdout.write('Seeding sample transaction data...')

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR('No admin user found. Run seed_data first.'))
            return

        sc_cache = {}
        pillar_cache = {}

        for pillar in FinancialPillar.objects.all():
            pillar_cache[pillar.name] = pillar
            for sc in SubCategory.objects.filter(user=admin, pillar=pillar):
                sc_cache[(pillar.name, sc.name)] = sc

        if not sc_cache:
            self.stdout.write(self.style.ERROR('No subcategories found. Run seed_data first.'))
            return

        # Clear existing data
        TransactionLog.objects.filter(user=admin).delete()
        MonthlyBudgetTarget.objects.filter(subcategory__user=admin).delete()
        DebtBalanceHistory.objects.filter(subcategory__user=admin).delete()
        SavingsGoal.objects.filter(subcategory__user=admin).delete()
        self.stdout.write('  Cleared existing transaction/budget/debt/goal data')

        now = date.today()
        end_year, end_month = now.year, now.month
        if end_month == 1:
            start_year, start_month = end_year - 1, 1
        else:
            start_year, start_month = end_year, (end_month - 12) if end_month >= 12 else (end_year - 1, end_month + 1) if end_year > now.year - 1 else (now.year - 1, 1)
            if isinstance(start_year, tuple):
                start_year, start_month = start_year

        # Generate 12 months of data ending at the current month
        total_months = 12
        txns_created = 0

        with transaction.atomic():
            # Generate transactions for each month
            for offset in range(total_months):
                m = end_month - offset
                y = end_year
                while m <= 0:
                    m += 12
                    y -= 1

                _, days_in_month = calendar.monthrange(y, m)

                self.stdout.write(f'  Generating {calendar.month_name[m]} {y}...')

                # --- Income ---
                # Salary on 1st
                sc = sc_cache.get(('INCOME', 'Salary'))
                if sc:
                    amt = random_amount(55000, 58000)
                    TransactionLog.objects.create(
                        user=admin, date=date(y, m, 1), detail='Monthly Salary',
                        amount=amt, category=pillar_cache['INCOME'], subcategory=sc
                    )
                    txns_created += 1

                # Salary (2nd) on 15th
                sc = sc_cache.get(('INCOME', 'Salary (2nd)'))
                if sc and random.random() < 0.9:
                    amt = random_amount(22000, 28000)
                    TransactionLog.objects.create(
                        user=admin, date=date(y, m, pick_day_in_range(y, m, 14, 16)), detail='2nd Salary',
                        amount=amt, category=pillar_cache['INCOME'], subcategory=sc
                    )
                    txns_created += 1

                # Interest - occasional
                sc = sc_cache.get(('INCOME', 'Interest'))
                if sc and random.random() < 0.7:
                    TransactionLog.objects.create(
                        user=admin, date=date(y, m, pick_random_day(y, m)), detail='Bank Interest',
                        amount=random_amount(100, 500), category=pillar_cache['INCOME'], subcategory=sc
                    )
                    txns_created += 1

                # Payback - occasional
                sc = sc_cache.get(('INCOME', 'Payback'))
                if sc and random.random() < 0.3:
                    TransactionLog.objects.create(
                        user=admin, date=date(y, m, pick_random_day(y, m)), detail='Payback from friend',
                        amount=random_amount(1000, 5000), category=pillar_cache['INCOME'], subcategory=sc
                    )
                    txns_created += 1

                # --- Bills (monthly) ---
                sc = sc_cache.get(('BILLS', 'PLDT'))
                if sc:
                    TransactionLog.objects.create(
                        user=admin, date=date(y, m, pick_day_in_range(y, m, 5, 10)), detail='PLDT Fiber',
                        amount=Decimal('2500.00'), category=pillar_cache['BILLS'], subcategory=sc
                    )
                    txns_created += 1

                # --- Subscriptions (monthly) ---
                for sc_name in MONTHLY_SUBSCRIPTION_SUBCATS:
                    sc = sc_cache.get(('SUBSCRIPTIONS', sc_name))
                    if sc:
                        pattern = MONTHLY_PATTERNS['SUBSCRIPTIONS'][sc_name]
                        TransactionLog.objects.create(
                            user=admin, date=date(y, m, pick_day_in_range(y, m, 1, 5)),
                            detail=pattern['detail'],
                            amount=Decimal(str(pattern['amount'][0])),
                            category=pillar_cache['SUBSCRIPTIONS'], subcategory=sc
                        )
                        txns_created += 1

                # --- Expenses (random pattern) ---
                for sc_name, pattern in MONTHLY_PATTERNS['EXPENSES'].items():
                    sc = sc_cache.get(('EXPENSES', sc_name))
                    if not sc:
                        continue
                    freq = pattern['freq']
                    if freq == 'monthly':
                        amt = random_amount(*pattern['amount'])
                        TransactionLog.objects.create(
                            user=admin, date=date(y, m, pick_random_day(y, m)),
                            detail=pattern['detail'], amount=amt,
                            category=pillar_cache['EXPENSES'], subcategory=sc
                        )
                        txns_created += 1
                    elif freq == 'quarterly':
                        if random.random() < 0.33:
                            amt = random_amount(*pattern['amount'])
                            TransactionLog.objects.create(
                                user=admin, date=date(y, m, pick_random_day(y, m)),
                                detail=pattern['detail'], amount=amt,
                                category=pillar_cache['EXPENSES'], subcategory=sc
                            )
                            txns_created += 1
                    elif freq == 'random':
                        # 2-4 random expense transactions per month for each
                        num_txns = random.randint(1, 3)
                        for _ in range(num_txns):
                            amt = random_amount(*pattern['amount'])
                            TransactionLog.objects.create(
                                user=admin, date=date(y, m, pick_random_day(y, m)),
                                detail=pattern['detail'], amount=amt,
                                category=pillar_cache['EXPENSES'], subcategory=sc
                            )
                            txns_created += 1

                # --- Savings (monthly) ---
                for sc_name in MONTHLY_SAVINGS_SUBCATS:
                    sc = sc_cache.get(('SAVINGS_INVESTMENTS', sc_name))
                    if sc:
                        amt = random_amount(5000, 10000) if 'BDO' in sc_name else random_amount(3000, 8000)
                        TransactionLog.objects.create(
                            user=admin, date=date(y, m, pick_day_in_range(y, m, 20, 28)),
                            detail=f'{sc_name.replace("Saving Personal", "savings")} deposit',
                            amount=amt, category=pillar_cache['SAVINGS_INVESTMENTS'], subcategory=sc
                        )
                        txns_created += 1

                # --- Debt (monthly) ---
                for sc_name in MONTHLY_DEBT_SUBCATS:
                    sc = sc_cache.get(('DEBT', sc_name))
                    if sc:
                        pattern = MONTHLY_PATTERNS['DEBT'][sc_name]
                        amt = random_amount(*pattern['amount'])
                        TransactionLog.objects.create(
                            user=admin, date=date(y, m, pick_day_in_range(y, m, 10, 20)),
                            detail=pattern['detail'], amount=amt,
                            category=pillar_cache['DEBT'], subcategory=sc
                        )
                        txns_created += 1

                # --- Credit (monthly) ---
                for sc_name in MONTHLY_CREDIT_SUBCATS:
                    sc = sc_cache.get(('CREDIT', sc_name))
                    if sc:
                        pattern = MONTHLY_PATTERNS['CREDIT'][sc_name]
                        amt = random_amount(*pattern['amount'])
                        TransactionLog.objects.create(
                            user=admin, date=date(y, m, pick_day_in_range(y, m, 1, 10)),
                            detail=pattern['detail'], amount=amt,
                            category=pillar_cache['CREDIT'], subcategory=sc
                        )
                        txns_created += 1

            self.stdout.write(self.style.SUCCESS(f'  Created {txns_created} transactions'))

            # --- Budget Targets (current year) ---
            budget_count = 0
            for sc in SubCategory.objects.filter(user=admin).select_related('pillar'):
                for m in range(1, 13):
                    # Set realistic budget amounts
                    pattern_lookup = MONTHLY_PATTERNS.get(sc.pillar.name, {}).get(sc.name, {})
                    if pattern_lookup:
                        avg_amt = sum(pattern_lookup['amount']) / 2
                        # Scale down monthly amounts for income
                        if sc.pillar.name == 'INCOME':
                            avg_amt = avg_amt * 1.1  # budget slightly above actual
                        elif sc.pillar.name in ('BILLS', 'SUBSCRIPTIONS'):
                            pass  # exact amount
                        else:
                            avg_amt = avg_amt * 1.05  # budget slightly above actual

                        MonthlyBudgetTarget.objects.create(
                            subcategory=sc,
                            year=now.year,
                            month=m,
                            budgeted_amount=Decimal(str(round(avg_amt, 2))),
                        )
                        budget_count += 1

            self.stdout.write(self.style.SUCCESS(f'  Created {budget_count} budget targets for {now.year}'))

            # --- Debt Balance History (trailing balances over 12 months) ---
            debt_scs = SubCategory.objects.filter(
                user=admin, pillar__name='DEBT'
            ).select_related('pillar')

            # Starting balances
            remaining = {
                'Loan (Mom)': 60000,
                'Loan 1st': 80000,
                'Loan 2nd': 50000,
                'Loan 3rd': 30000,
            }

            debt_history_count = 0
            # Go forward month by month, decreasing balances
            for offset in reversed(range(total_months)):
                m = end_month - offset
                y = end_year
                while m <= 0:
                    m += 12
                    y -= 1

                for sc in debt_scs:
                    if sc.name in remaining:
                        # Decrease balance by roughly the payment amount
                        payment = random_amount(3000, 5000)
                        remaining[sc.name] = max(0, remaining[sc.name] - float(payment))
                        DebtBalanceHistory.objects.create(
                            subcategory=sc,
                            year=y,
                            month=m,
                            remaining_balance=Decimal(str(round(remaining[sc.name], 2))),
                        )
                        debt_history_count += 1

            self.stdout.write(self.style.SUCCESS(f'  Created {debt_history_count} debt balance history entries'))

            # --- Savings Goals ---
            savings_scs = SubCategory.objects.filter(
                user=admin, pillar__name='SAVINGS_INVESTMENTS'
            ).select_related('pillar')

            goals_created = 0
            for sc in savings_scs:
                SavingsGoal.objects.create(
                    subcategory=sc,
                    target_goal=Decimal('500000.00'),
                    starting_amount=Decimal('50000.00'),
                    monthly_contribution_target=Decimal('10000.00'),
                )
                goals_created += 1

            self.stdout.write(self.style.SUCCESS(f'  Created {goals_created} savings goals'))

        self.stdout.write(self.style.SUCCESS('Sample data seeded successfully!'))
