from django.core.management.base import BaseCommand
from tracker.models import FinancialPillar, SubCategory


PILLARS = [
    {'name': 'INCOME', 'slug': 'income', 'sort_order': 1},
    {'name': 'BILLS', 'slug': 'bills', 'sort_order': 2},
    {'name': 'SUBSCRIPTIONS', 'slug': 'subscriptions', 'sort_order': 3},
    {'name': 'EXPENSES', 'slug': 'expenses', 'sort_order': 4},
    {'name': 'SAVINGS_INVESTMENTS', 'slug': 'savings', 'sort_order': 5},
    {'name': 'DEBT', 'slug': 'debt', 'sort_order': 6},
    {'name': 'CREDIT', 'slug': 'credit', 'sort_order': 7},
]

SUBCATEGORIES = {
    'INCOME': [
        'Salary', 'Salary (2nd)', 'Saving (previous)',
        'Top-up (income)', 'Interest', 'Payback',
    ],
    'BILLS': [
        'PLDT',
    ],
    'SUBSCRIPTIONS': [
        'Tinder', 'Bumble', 'Netflix (1st)',
        'Netflix (2nd)', 'Disney',
    ],
    'EXPENSES': [
        'Facebook', 'Google Platform', 'Personal',
        'Split Payment', 'Installment', 'Shoppe',
        'Mom credit', 'Tita Maite Credit', 'Travel',
    ],
    'SAVINGS_INVESTMENTS': [
        'BDO Saving Personal', 'EastWest Saving Personal',
    ],
    'DEBT': [
        'Loan (Mom)', 'Loan 1st', 'Loan 2nd', 'Loan 3rd',
    ],
    'CREDIT': [
        'Credit Card BDO', 'Credit Card Atome',
        'Credit Card EastWest', 'Credit UnionBank',
        'Credit Card EastWest Acer', 'Credit Card SM Store dept',
        'Credit Card Store dept Fili',
        'Credit Card Store dept 2nd - Fili',
        'Credit Card MAC Apple',
    ],
}


class Command(BaseCommand):
    help = 'Seed the database with Financial Pillars and Sub Categories'

    def handle(self, *args, **options):
        created_pillars = {}
        for pdata in PILLARS:
            pillar, created = FinancialPillar.objects.get_or_create(
                name=pdata['name'],
                defaults={'slug': pdata['slug'], 'sort_order': pdata['sort_order']}
            )
            if not created:
                pillar.slug = pdata['slug']
                pillar.sort_order = pdata['sort_order']
                pillar.save()
            created_pillars[pdata['name']] = pillar
            self.stdout.write(self.style.SUCCESS(f"Pillar: {pillar.get_name_display()}"))

        for pillar_name, subs in SUBCATEGORIES.items():
            pillar = created_pillars[pillar_name]
            for sub_name in subs:
                sub, created = SubCategory.objects.get_or_create(
                    pillar=pillar, name=sub_name, is_global=True,
                    defaults={'user': None}
                )
                if created:
                    self.stdout.write(f"  SubCategory: {sub_name}")

        self.stdout.write(self.style.SUCCESS('Seed complete: all pillars and sub-categories loaded.'))
