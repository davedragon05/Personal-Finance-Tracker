import calendar
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from tracker.models import RecurringTransaction, TransactionLog


def add_months(dt, n):
    month = dt.month - 1 + n
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Command(BaseCommand):
    help = 'Processes due recurring transactions and creates transaction logs'

    def handle(self, *args, **options):
        today = date.today()
        due = RecurringTransaction.objects.filter(active=True, next_due_date__lte=today)
        created = 0
        for rt in due:
            TransactionLog.objects.create(
                user=rt.user,
                date=rt.next_due_date,
                detail=rt.detail,
                amount=rt.amount,
                category=rt.subcategory.pillar,
                subcategory=rt.subcategory,
            )
            if rt.interval == 'monthly':
                rt.next_due_date = add_months(rt.next_due_date, 1)
            elif rt.interval == 'yearly':
                rt.next_due_date = add_months(rt.next_due_date, 12)
            rt.save()
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} recurring transaction(s)'))
