from django.db import migrations


def backfill_payment_mode(apps, schema_editor):
    DebtBalanceHistory = apps.get_model('tracker', 'DebtBalanceHistory')
    TransactionLog = apps.get_model('tracker', 'TransactionLog')
    FinancialPillar = apps.get_model('tracker', 'FinancialPillar')

    try:
        debt_pillar = FinancialPillar.objects.get(name='DEBT')
    except FinancialPillar.DoesNotExist:
        return

    for debt in DebtBalanceHistory.objects.filter(payment_mode=''):
        txn = TransactionLog.objects.filter(
            user=debt.user,
            subcategory=debt.subcategory,
            category=debt_pillar,
            date__year=debt.year,
            date__month=debt.month,
            detail='Debt payment',
        ).exclude(payment_mode='').first()
        if txn:
            debt.payment_mode = txn.payment_mode
            debt.save(update_fields=['payment_mode'])


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0005_debtbalancehistory_payment_mode'),
    ]

    operations = [
        migrations.RunPython(backfill_payment_mode, migrations.RunPython.noop),
    ]
