import json
import calendar
from datetime import datetime, date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction

from .models import (
    FinancialPillar, SubCategory, TransactionLog,
    MonthlyBudgetTarget, SavingsGoal, SavingsContribution, DebtBalanceHistory
)


def get_default_year_month():
    now = datetime.now()
    return now.year, now.month


def serialize_transaction(t):
    return {
        'id': t.id,
        'date': t.date.isoformat(),
        'detail': t.detail,
        'amount': float(t.amount),
        'category_id': t.category_id,
        'category_name': t.category.get_name_display(),
        'subcategory_id': t.subcategory_id,
        'subcategory_name': t.subcategory.name,
        'card_credit_type_id': t.card_credit_type_id,
        'card_credit_type_name': t.card_credit_type.name if t.card_credit_type else None,
    }


def serialize_budget(b):
    return {
        'id': b.id,
        'subcategory_id': b.subcategory_id,
        'subcategory_name': b.subcategory.name,
        'pillar_id': b.subcategory.pillar_id,
        'pillar_name': b.subcategory.pillar.get_name_display(),
        'year': b.year,
        'month': b.month,
        'budgeted_amount': float(b.budgeted_amount),
    }


def serialize_subcategory(sc):
    return {
        'id': sc.id,
        'name': sc.name,
        'pillar_id': sc.pillar_id,
        'pillar_name': sc.pillar.get_name_display(),
        'due_day': sc.due_day,
    }


def serialize_pillar(p):
    return {
        'id': p.id,
        'name': p.name,
        'display_name': p.get_name_display(),
    }


# --- Page Views ---

@login_required
@ensure_csrf_cookie
def dashboard(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')

    # Default to latest year/month that has data, fall back to current date
    latest_data_date = TransactionLog.objects.filter(
        user=request.user
    ).values_list('date', flat=True).order_by('-date').first()
    if latest_data_date:
        year, month = latest_data_date.year, latest_data_date.month
    else:
        year, month = get_default_year_month()

    # Contiguous year range for the dropdown (min data year .. max data year + 1)
    raw_years = sorted(TransactionLog.objects.filter(
        user=request.user
    ).values_list('date__year', flat=True).distinct())
    min_y = raw_years[0] if raw_years else year
    max_y = max(raw_years[-1] if raw_years else year, year) + 1
    data_years = list(range(min_y, max_y + 1))

    return render(request, 'tracker/dashboard.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'data_years': data_years,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


# --- Individual Page Views ---

@login_required
@ensure_csrf_cookie
def ledger_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    year, month = get_default_year_month()
    return render(request, 'tracker/ledger.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


@login_required
@ensure_csrf_cookie
def budget_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    year, month = get_default_year_month()
    return render(request, 'tracker/budget.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


@login_required
@ensure_csrf_cookie
def overview_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    year, month = get_default_year_month()
    return render(request, 'tracker/overview.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


@login_required
@ensure_csrf_cookie
def analytics_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    year, month = get_default_year_month()
    return render(request, 'tracker/analytics.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


@login_required
@ensure_csrf_cookie
def savings_goals_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    return render(request, 'tracker/savings_goals.html', {
        'pillars': pillars,
        'subcategories': subcategories,
    })


@login_required
@ensure_csrf_cookie
def calendar_page(request):
    pillars = FinancialPillar.objects.all()
    subcategories = SubCategory.objects.filter(user=request.user).select_related('pillar')
    year, month = get_default_year_month()
    return render(request, 'tracker/calendar.html', {
        'pillars': pillars,
        'subcategories': subcategories,
        'current_year': year,
        'current_month': month,
        'months': [{'num': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
    })


# --- Transaction Endpoints ---

@login_required
@require_http_methods(['GET'])
def transaction_list(request):
    raw_year = request.GET.get('year')
    raw_month = request.GET.get('month')
    category_id = request.GET.get('category_id')
    search = request.GET.get('search', '')
    page = request.GET.get('page', 1)
    page_size = request.GET.get('page_size', 25)

    qs = TransactionLog.objects.filter(user=request.user).select_related(
        'category', 'subcategory', 'card_credit_type'
    )

    if raw_year:
        qs = qs.filter(date__year=int(raw_year))
    if raw_month:
        month = int(raw_month)
        if month:
            qs = qs.filter(date__month=month)
    if category_id:
        qs = qs.filter(category_id=int(category_id))
    if search:
        qs = qs.filter(
            Q(detail__icontains=search) |
            Q(subcategory__name__icontains=search) |
            Q(category__name__icontains=search)
        )

    paginator = Paginator(qs, page_size)

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return JsonResponse({
        'transactions': [serialize_transaction(t) for t in page_obj.object_list],
        'total': paginator.count,
        'page': page_obj.number,
        'num_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    })


@login_required
@require_http_methods(['POST'])
def transaction_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    category_id = data.get('category_id')
    subcategory_id = data.get('subcategory_id')
    amount = data.get('amount')
    date_str = data.get('date')
    detail = data.get('detail', '')
    card_credit_type_id = data.get('card_credit_type_id')

    if not all([category_id, subcategory_id, amount, date_str]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    try:
        category = FinancialPillar.objects.get(id=category_id)
        subcategory = SubCategory.objects.get(id=subcategory_id, user=request.user)

        card_credit_type = None
        if card_credit_type_id:
            card_credit_type = SubCategory.objects.get(id=card_credit_type_id, user=request.user)

        txn = TransactionLog.objects.create(
            user=request.user,
            date=date.fromisoformat(date_str),
            detail=detail,
            amount=Decimal(str(amount)),
            category=category,
            subcategory=subcategory,
            card_credit_type=card_credit_type,
        )

        return JsonResponse({
            'success': True,
            'transaction': serialize_transaction(txn),
        }, status=201)

    except (FinancialPillar.DoesNotExist, SubCategory.DoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(['PATCH', 'DELETE'])
def transaction_detail(request, txn_id):
    txn = get_object_or_404(TransactionLog, id=txn_id, user=request.user)

    if request.method == 'DELETE':
        txn.delete()
        return JsonResponse({'success': True, 'deleted': txn_id})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if 'amount' in data:
        txn.amount = Decimal(str(data['amount']))
    if 'detail' in data:
        txn.detail = data['detail']
    if 'date' in data:
        txn.date = date.fromisoformat(data['date'])
    if 'category_id' in data:
        txn.category = FinancialPillar.objects.get(id=data['category_id'])
    if 'subcategory_id' in data:
        txn.subcategory = SubCategory.objects.get(id=data['subcategory_id'], user=request.user)
    if 'card_credit_type_id' in data:
        if data['card_credit_type_id']:
            txn.card_credit_type = SubCategory.objects.get(id=data['card_credit_type_id'], user=request.user)
        else:
            txn.card_credit_type = None

    txn.save()

    return JsonResponse({
        'success': True,
        'transaction': serialize_transaction(txn),
    })


# --- SubCategory Endpoints ---

@login_required
@require_http_methods(['GET'])
def subcategory_list(request):
    pillar_id = request.GET.get('pillar_id')
    qs = SubCategory.objects.filter(user=request.user).select_related('pillar')
    if pillar_id:
        qs = qs.filter(pillar_id=int(pillar_id))
    return JsonResponse({
        'subcategories': [serialize_subcategory(sc) for sc in qs]
    })


@login_required
@require_http_methods(['POST'])
def subcategory_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    pillar_id = data.get('pillar_id')

    if not name or not pillar_id:
        return JsonResponse({'error': 'Name and pillar are required'}, status=400)

    try:
        pillar = FinancialPillar.objects.get(id=pillar_id)
    except FinancialPillar.DoesNotExist:
        return JsonResponse({'error': 'Pillar not found'}, status=404)

    sc, created = SubCategory.objects.get_or_create(
        user=request.user,
        pillar=pillar,
        name=name,
    )

    if not created:
        return JsonResponse({'error': 'Subcategory already exists'}, status=409)

    return JsonResponse({
        'success': True,
        'subcategory': serialize_subcategory(sc),
    }, status=201)


@login_required
@require_http_methods(['DELETE'])
def subcategory_delete(request, sc_id):
    sc = get_object_or_404(SubCategory, id=sc_id, user=request.user)
    sc.delete()
    return JsonResponse({'success': True, 'deleted': sc_id})


@login_required
@require_http_methods(['GET'])
def pillar_list(request):
    pillars = FinancialPillar.objects.all()
    return JsonResponse({
        'pillars': [serialize_pillar(p) for p in pillars]
    })


# --- Budget Target Endpoints ---

@login_required
@require_http_methods(['GET'])
def budget_target_list(request):
    raw_year = request.GET.get('year')
    raw_month = request.GET.get('month')

    qs = MonthlyBudgetTarget.objects.filter(
        subcategory__user=request.user
    ).select_related('subcategory__pillar')

    if raw_year:
        qs = qs.filter(year=int(raw_year))
    if raw_month:
        month = int(raw_month)
        if month:
            qs = qs.filter(month=month)

    return JsonResponse({
        'budgets': [serialize_budget(b) for b in qs]
    })


@login_required
@require_http_methods(['POST'])
def budget_target_upsert(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    subcategory_id = data.get('subcategory_id')
    year = data.get('year')
    month = data.get('month')
    budgeted_amount = data.get('budgeted_amount')

    if not all([subcategory_id, year, month, budgeted_amount is not None]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    subcategory = get_object_or_404(SubCategory, id=subcategory_id, user=request.user)

    budget, created = MonthlyBudgetTarget.objects.update_or_create(
        subcategory=subcategory,
        year=int(year),
        month=int(month),
        defaults={'budgeted_amount': Decimal(str(budgeted_amount))},
    )

    total_budgeted = MonthlyBudgetTarget.objects.filter(
        subcategory__user=request.user,
        year=int(year),
        month=int(month),
    ).aggregate(total=Sum('budgeted_amount'))['total'] or 0

    income_budgeted = MonthlyBudgetTarget.objects.filter(
        subcategory__user=request.user,
        subcategory__pillar__name='INCOME',
        year=int(year),
        month=int(month),
    ).aggregate(total=Sum('budgeted_amount'))['total'] or 0

    left_to_budget = float(income_budgeted - total_budgeted)

    return JsonResponse({
        'success': True,
        'created': created,
        'budget': serialize_budget(budget),
        'total_budgeted': float(total_budgeted),
        'income_budgeted': float(income_budgeted),
        'left_to_budget': left_to_budget,
    })


# --- Monthly Overview Endpoints ---

@login_required
@require_http_methods(['GET'])
def monthly_overview(request):
    raw_year = request.GET.get('year', '')
    raw_month = request.GET.get('month', '')
    has_year = 'year' in request.GET
    has_month = 'month' in request.GET
    year = int(raw_year) if raw_year else 0
    month = int(raw_month) if raw_month else 0

    if not has_year and not has_month:
        year = datetime.now().year
        month = datetime.now().month

    qs = TransactionLog.objects.filter(user=request.user)
    if year:
        qs = qs.filter(date__year=year)
    if month:
        qs = qs.filter(date__month=month)
    transactions = qs

    income_total = transactions.filter(
        category__name='INCOME'
    ).aggregate(total=Sum('amount'))['total'] or 0

    expense_total = transactions.filter(
        category__name__in=['EXPENSES', 'BILLS', 'SUBSCRIPTIONS']
    ).aggregate(total=Sum('amount'))['total'] or 0

    savings_total = transactions.filter(
        category__name='SAVINGS_INVESTMENTS'
    ).aggregate(total=Sum('amount'))['total'] or 0

    debt_total = transactions.filter(
        category__name='DEBT'
    ).aggregate(total=Sum('amount'))['total'] or 0

    budget_filter = {'subcategory__user': request.user}
    if year:
        budget_filter['year'] = year
    if month:
        budget_filter['month'] = month
    budget_targets = MonthlyBudgetTarget.objects.filter(**budget_filter)

    total_budgeted = budget_targets.aggregate(total=Sum('budgeted_amount'))['total'] or 0
    income_budgeted = budget_targets.filter(
        subcategory__pillar__name='INCOME'
    ).aggregate(total=Sum('budgeted_amount'))['total'] or 0

    category_breakdown = []
    for pillar in FinancialPillar.objects.all():
        actual = transactions.filter(category=pillar).aggregate(total=Sum('amount'))['total'] or 0
        budgeted = budget_targets.filter(
            subcategory__pillar=pillar
        ).aggregate(total=Sum('budgeted_amount'))['total'] or 0
        variance = float(budgeted) - float(actual)
        category_breakdown.append({
            'pillar_id': pillar.id,
            'pillar_name': pillar.get_name_display(),
            'actual': float(actual),
            'budgeted': float(budgeted),
            'variance': variance,
        })

    # subcategory-level breakdown for progress bars
    subcategory_breakdown = []
    for sc in SubCategory.objects.filter(user=request.user).select_related('pillar'):
        actual = transactions.filter(subcategory=sc).aggregate(total=Sum('amount'))['total'] or 0
        budget = budget_targets.filter(subcategory=sc).first()
        budgeted = float(budget.budgeted_amount) if budget else 0
        pct = round((float(actual) / budgeted * 100), 1) if budgeted > 0 else 0
        subcategory_breakdown.append({
            'subcategory_id': sc.id,
            'subcategory_name': sc.name,
            'pillar_name': sc.pillar.get_name_display(),
            'actual': float(actual),
            'budgeted': budgeted,
            'variance': budgeted - float(actual),
            'percentage': pct,
        })

    return JsonResponse({
        'year': year or 0,
        'month': month or 0,
        'month_name': calendar.month_name[month] if month else 'All',
        'income_total': float(income_total),
        'expense_total': float(expense_total),
        'savings_total': float(savings_total),
        'debt_total': float(debt_total),
        'net_cash_flow': float(income_total - expense_total - savings_total - debt_total),
        'total_budgeted': float(total_budgeted),
        'income_budgeted': float(income_budgeted),
        'category_breakdown': category_breakdown,
        'subcategory_breakdown': subcategory_breakdown,
    })


# --- Analytics Endpoints ---

@login_required
@require_http_methods(['GET'])
def analytics_income_vs_expenses(request):
    raw_year = request.GET.get('year', '')
    year = int(raw_year) if raw_year else 0

    if not year:
        year = TransactionLog.objects.filter(
            user=request.user
        ).dates('date', 'year', order='DESC').first()
        year = year.year if year else datetime.now().year

    months_data = []
    for m in range(1, 13):
        txn = TransactionLog.objects.filter(
            user=request.user,
            date__year=year,
            date__month=m,
        )

        income = float(txn.filter(category__name='INCOME').aggregate(total=Sum('amount'))['total'] or 0)
        expenses = float(txn.filter(
            category__name__in=['EXPENSES', 'BILLS', 'SUBSCRIPTIONS']
        ).aggregate(total=Sum('amount'))['total'] or 0)

        months_data.append({
            'month': m,
            'month_name': calendar.month_abbr[m],
            'income': income,
            'expenses': expenses,
        })

    return JsonResponse({
        'year': year,
        'months': months_data,
    })


@login_required
@require_http_methods(['GET'])
def analytics_expense_dispersal(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    expenses = TransactionLog.objects.filter(
        user=request.user,
        category__name='EXPENSES',
        date__year=year,
        date__month=month,
    ).values('subcategory__name').annotate(
        total=Sum('amount')
    ).order_by('-total')

    data = []
    for item in expenses:
        data.append({
            'label': item['subcategory__name'],
            'value': float(item['total']),
        })

    return JsonResponse({
        'year': year,
        'month': month,
        'dispersal': data,
    })


@login_required
@require_http_methods(['GET'])
def analytics_debt_trajectory(request):
    histories = DebtBalanceHistory.objects.filter(
        subcategory__user=request.user,
    ).select_related('subcategory').order_by('year', 'month')

    debts_by_subcategory = {}
    for h in histories:
        key = h.subcategory.name
        if key not in debts_by_subcategory:
            debts_by_subcategory[key] = []
        debts_by_subcategory[key].append({
            'year': h.year,
            'month': h.month,
            'label': f"{calendar.month_abbr[h.month]} {h.year}",
            'balance': float(h.remaining_balance),
        })

    return JsonResponse({
        'debts': debts_by_subcategory,
    })


# --- Calendar / No-Spend Day Endpoints ---

@login_required
@require_http_methods(['GET'])
def calendar_events(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    _, days_in_month = calendar.monthrange(year, month)

    expense_txns = TransactionLog.objects.filter(
        user=request.user,
        category__name__in=['EXPENSES'],
        date__year=year,
        date__month=month,
    ).values('date').annotate(
        total=Sum('amount')
    ).order_by('date')

    expense_dates = set()
    expense_amounts = {}
    for item in expense_txns:
        d = item['date']
        expense_dates.add(d)
        expense_amounts[d] = float(item['total'])

    events = []
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        is_spend_day = d in expense_dates
        events.append({
            'title': f"\u20b1{expense_amounts[d]:,.2f}" if is_spend_day else "No Spend",
            'start': d.isoformat(),
            'allDay': True,
            'backgroundColor': '#EF4444' if is_spend_day else '#22C55E',
            'borderColor': '#EF4444' if is_spend_day else '#16A34A',
            'textColor': '#FFFFFF',
            'className': 'spend-day' if is_spend_day else 'no-spend-day',
            'extendedProps': {
                'is_spend_day': is_spend_day,
                'total': expense_amounts.get(d, 0),
            }
        })

    return JsonResponse(events, safe=False)


@login_required
@require_http_methods(['GET'])
def calendar_day_detail(request):
    date_str = request.GET.get('date', '')
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date'}, status=400)

    txns = TransactionLog.objects.filter(
        user=request.user,
        date=day,
    ).select_related('category', 'subcategory').order_by('category__name', 'subcategory__name')

    total = 0
    categories = {}
    for t in txns:
        amt = float(t.amount)
        total += amt
        cat_name = t.category.get_name_display()
        if cat_name not in categories:
            categories[cat_name] = {'category_name': cat_name, 'items': [], 'subtotal': 0}
        categories[cat_name]['items'].append({
            'id': t.id,
            'subcategory': t.subcategory.name,
            'amount': amt,
            'detail': t.detail,
        })
        categories[cat_name]['subtotal'] += amt

    return JsonResponse({
        'date': day.isoformat(),
        'total': total,
        'categories': list(categories.values()),
    })


# --- Savings Goal Endpoints ---

def serialize_savings_goal(sg):
    contributions_qs = sg.contributions.all()
    total_contributions = float(sum(c.amount for c in contributions_qs))
    current_amount = float(sg.starting_amount) + total_contributions
    target = float(sg.target_goal)
    return {
        'id': sg.id,
        'subcategory_id': sg.subcategory_id,
        'subcategory_name': sg.subcategory.name,
        'pillar_name': sg.subcategory.pillar.get_name_display(),
        'target_goal': target,
        'starting_amount': float(sg.starting_amount),
        'current_amount': current_amount,
        'total_contributions': total_contributions,
        'monthly_contribution_target': float(sg.monthly_contribution_target),
        'progress': round(min(current_amount / target * 100, 100), 1) if target else 0,
        'contributions': [
            {
                'id': c.id,
                'amount': float(c.amount),
                'date': c.date.isoformat(),
                'note': c.note,
            }
            for c in contributions_qs
        ],
    }


@login_required
@require_http_methods(['GET'])
def savings_goal_list(request):
    goals = SavingsGoal.objects.filter(
        subcategory__user=request.user
    ).select_related('subcategory__pillar')
    return JsonResponse({
        'goals': [serialize_savings_goal(sg) for sg in goals]
    })


@login_required
@require_http_methods(['POST'])
def savings_goal_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    subcategory_id = data.get('subcategory_id')
    target_goal = data.get('target_goal')
    starting_amount = data.get('starting_amount', 0)
    monthly_contribution_target = data.get('monthly_contribution_target')

    if not all([subcategory_id, target_goal, monthly_contribution_target]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    subcategory = get_object_or_404(SubCategory, id=subcategory_id, user=request.user)

    goal = SavingsGoal.objects.create(
        subcategory=subcategory,
        target_goal=Decimal(str(target_goal)),
        starting_amount=Decimal(str(starting_amount)),
        monthly_contribution_target=Decimal(str(monthly_contribution_target)),
    )

    return JsonResponse({
        'success': True,
        'goal': serialize_savings_goal(goal),
    }, status=201)


@login_required
@require_http_methods(['PATCH', 'DELETE'])
def savings_goal_detail(request, goal_id):
    goal = get_object_or_404(SavingsGoal, id=goal_id, subcategory__user=request.user)

    if request.method == 'DELETE':
        goal.delete()
        return JsonResponse({'success': True, 'deleted': goal_id})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if 'target_goal' in data:
        goal.target_goal = Decimal(str(data['target_goal']))
    if 'starting_amount' in data:
        goal.starting_amount = Decimal(str(data['starting_amount']))
    if 'monthly_contribution_target' in data:
        goal.monthly_contribution_target = Decimal(str(data['monthly_contribution_target']))

    goal.save()
    return JsonResponse({
        'success': True,
        'goal': serialize_savings_goal(goal),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def savings_goal_contributions(request, goal_id):
    goal = get_object_or_404(SavingsGoal, id=goal_id, subcategory__user=request.user)

    if request.method == 'GET':
        contributions = goal.contributions.all()
        return JsonResponse({
            'contributions': [
                {
                    'id': c.id,
                    'amount': float(c.amount),
                    'date': c.date.isoformat(),
                    'note': c.note,
                }
                for c in contributions
            ]
        })

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    amount = data.get('amount')
    date_str = data.get('date')
    note = data.get('note', '')

    if not amount:
        return JsonResponse({'error': 'Amount is required'}, status=400)

    try:
        amount = Decimal(str(amount))
        cont = SavingsContribution.objects.create(
            savings_goal=goal,
            amount=amount,
            date=datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today(),
            note=note,
        )
        return JsonResponse({
            'success': True,
            'contribution': {
                'id': cont.id,
                'amount': float(cont.amount),
                'date': cont.date.isoformat(),
                'note': cont.note,
            }
        }, status=201)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid amount or date'}, status=400)


@login_required
@require_http_methods(['DELETE'])
def savings_contribution_detail(request, contribution_id):
    contribution = get_object_or_404(SavingsContribution, id=contribution_id, savings_goal__subcategory__user=request.user)
    contribution.delete()
    return JsonResponse({'success': True, 'deleted': contribution_id})


# --- Search / Quick Stats Endpoints ---

@login_required
@require_http_methods(['GET'])
def quick_stats(request):
    raw_year = request.GET.get('year', '')
    raw_month = request.GET.get('month', '')
    has_year = 'year' in request.GET
    has_month = 'month' in request.GET
    year = int(raw_year) if raw_year else 0
    month = int(raw_month) if raw_month else 0

    # Only fallback to default when neither param is provided at all
    if not has_year and not has_month:
        year, month = get_default_year_month()

    total_income = TransactionLog.objects.filter(
        user=request.user,
        category__name='INCOME',
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = TransactionLog.objects.filter(
        user=request.user,
        category__name='EXPENSES',
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_savings = TransactionLog.objects.filter(
        user=request.user,
        category__name='SAVINGS_INVESTMENTS',
    ).aggregate(total=Sum('amount'))['total'] or 0

    qs = TransactionLog.objects.filter(user=request.user)
    if year:
        qs = qs.filter(date__year=year)
    if month:
        qs = qs.filter(date__month=month)

    current_month_income = qs.filter(
        category__name='INCOME',
    ).aggregate(total=Sum('amount'))['total'] or 0

    current_month_expenses = qs.filter(
        category__name__in=['EXPENSES', 'BILLS', 'SUBSCRIPTIONS'],
    ).aggregate(total=Sum('amount'))['total'] or 0

    return JsonResponse({
        'total_income': float(total_income),
        'total_expenses': float(total_expenses),
        'total_savings': float(total_savings),
        'current_month_income': float(current_month_income),
        'current_month_expenses': float(current_month_expenses),
        'current_surplus': float(current_month_income - current_month_expenses),
        'year': year or 0,
        'month': month or 0,
    })
