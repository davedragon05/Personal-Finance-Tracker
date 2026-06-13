from django.conf import settings
from django.db import migrations, models
from datetime import date


def populate_dates(apps, schema_editor):
    DebtBalanceHistory = apps.get_model('tracker', 'DebtBalanceHistory')
    for obj in DebtBalanceHistory.objects.all():
        obj.date = date(obj.year, obj.month, 1)
        obj.save(update_fields=['date'])


def reverse_dates(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_backfill_debt_payment_mode'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='debtbalancehistory',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='debtbalancehistory',
            name='date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(populate_dates, reverse_dates),
        migrations.AlterField(
            model_name='debtbalancehistory',
            name='date',
            field=models.DateField(blank=False, null=False),
        ),
        migrations.AlterUniqueTogether(
            name='debtbalancehistory',
            unique_together={('user', 'subcategory', 'date')},
        ),
    ]
