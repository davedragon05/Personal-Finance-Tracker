from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import FinancialPillar, SubCategory


PILLAR_CATEGORIES = {
    'INCOME': [
        'Salary', 'Salary (2nd)', 'Saving (previous)', 'Top-up (income)',
        'Interest', 'Payback',
    ],
    'BILLS': [
        'PLDT',
    ],
    'SUBSCRIPTIONS': [
        'Tinder', 'Bumble', 'Netflix (1st)', 'Netflix (2nd)', 'Disney',
    ],
    'EXPENSES': [
        'Facebook', 'Google Platform', 'Personal', 'Split Payment',
        'Installment', 'Shoppe', 'Mom credit', 'Tita Maite Credit', 'Travel',
    ],
    'SAVINGS_INVESTMENTS': [
        'BDO Saving Personal', 'EastWest Saving Personal',
    ],
    'DEBT': [
        'Loan (Mom)', 'Loan 1st', 'Loan 2nd', 'Loan 3rd',
    ],
    'CREDIT': [
        'Credit Card BDO', 'Credit Card Atome', 'Credit Card EastWest',
        'Credit UnionBank', 'Credit Card EastWest Acer',
        'Credit Card SM Store dept', 'Credit Card Store dept Fili',
        'Credit Card Store dept 2nd - Fili', 'Credit Card MAC Apple',
    ],
}


class Command(BaseCommand):
    help = 'Seeds the database with Financial Pillars and SubCategories'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Financial Pillars and SubCategories...')

        pillars = {}
        for pillar_name in PILLAR_CATEGORIES:
            pillar, created = FinancialPillar.objects.get_or_create(name=pillar_name)
            pillars[pillar_name] = pillar
            if created:
                self.stdout.write(f'  Created pillar: {pillar.get_name_display()}')

        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'Admin@123')
            self.stdout.write(f'  Created superuser: admin / Admin@123')

        for pillar_name, subcategories in PILLAR_CATEGORIES.items():
            for sc_name in subcategories:
                sc, created = SubCategory.objects.get_or_create(
                    user=admin_user,
                    pillar=pillars[pillar_name],
                    name=sc_name,
                )
                if created:
                    self.stdout.write(f'  Created subcategory: {pillar_name} -> {sc_name}')

        self.stdout.write(self.style.SUCCESS('Seed data created successfully!'))
