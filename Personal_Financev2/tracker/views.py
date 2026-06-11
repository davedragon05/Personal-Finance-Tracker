import json
from datetime import datetime, date
from decimal import Decimal

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods


def ajax_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper

from .models import (
    FinancialPillar, SubCategory, TransactionLog,
    MonthlyBudgetTarget, SavingsGoal, DebtBalanceHistory
)


@ensure_csrf_cookie
def index(request):
    pillars = FinancialPillar.objects.all()
    return render(request, 'tracker/index.html', {
        'pillars': pillars,
        'year': datetime.now().year,
        'month': datetime.now().month,
    })


def api_get_csrf(request):
    return JsonResponse({'csrf': 'ok'})


@ajax_login_required
@require_http_methods(['GET'])
def api_pillars(request):
    data = []
    for p in FinancialPillar.objects.all():
        data.append({
            'id': p.id, 'name': p.name, 'slug': p.slug,
            'display': p.get_name_display(), 'sort_order': p.sort_order
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_subcategories(request):
    pillar_id = request.GET.get('pillar_id')
    qs = SubCategory.objects.filter(Q(user=request.user) | Q(is_global=True))
    if pillar_id:
        qs = qs.filter(pillar_id=pillar_id)
    data = []
    for s in qs:
        data.append({
            'id': s.id, 'name': s.name, 'pillar': s.pillar_id,
            'pillar_name': s.pillar.name, 'due_day': s.due_day,
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['POST'])
def api_transaction_create(request):
    try:
        body = json.loads(request.body)
        raw_date = body.get('date', date.today().isoformat())
        if isinstance(raw_date, str):
            parsed_date = date.fromisoformat(raw_date)
        else:
            parsed_date = raw_date
        txn = TransactionLog.objects.create(
            user=request.user,
            date=parsed_date,
            detail=body.get('detail', ''),
            amount=body['amount'],
            category_id=body['category_id'],
            subcategory_id=body.get('subcategory_id'),
            card_credit_type_id=body.get('card_credit_type_id'),
        )
        return JsonResponse({
            'status': 'ok',
            'transaction': {
                'id': txn.id, 'date': str(txn.date),
                'detail': txn.detail, 'amount': str(txn.amount),
                'category': txn.category.name if txn.category else None,
                'subcategory': txn.subcategory.name if txn.subcategory else None,
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['GET'])
def api_transactions(request):
    qs = TransactionLog.objects.filter(user=request.user).select_related('category', 'subcategory')
    year = request.GET.get('year')
    month = request.GET.get('month')
    subcategory_id = request.GET.get('subcategory_id')
    if year:
        qs = qs.filter(date__year=int(year))
    if month:
        qs = qs.filter(date__month=int(month))
    if subcategory_id:
        qs = qs.filter(subcategory_id=int(subcategory_id))
    limit = request.GET.get('limit', '100')
    if limit != 'all':
        qs = qs[:int(limit)]
    data = []
    for t in qs:
        data.append({
            'id': t.id, 'date': str(t.date), 'detail': t.detail,
            'amount': str(t.amount),
            'category': t.category.name if t.category else None,
            'category_id': t.category_id,
            'subcategory': t.subcategory.name if t.subcategory else None,
            'subcategory_id': t.subcategory_id,
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['DELETE', 'POST'])
def api_transaction_delete(request, txn_id):
    try:
        txn = TransactionLog.objects.get(id=txn_id, user=request.user)
        txn.delete()
        return JsonResponse({'status': 'ok'})
    except TransactionLog.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


@ajax_login_required
@require_http_methods(['POST'])
def api_transaction_update(request, txn_id):
    try:
        txn = TransactionLog.objects.get(id=txn_id, user=request.user)
        body = json.loads(request.body)
        if 'date' in body:
            txn.date = body['date']
        if 'detail' in body:
            txn.detail = body['detail']
        if 'amount' in body:
            txn.amount = body['amount']
        if 'category_id' in body:
            txn.category_id = body['category_id']
        if 'subcategory_id' in body:
            txn.subcategory_id = body['subcategory_id']
        txn.save()
        return JsonResponse({'status': 'ok', 'transaction': {
            'id': txn.id, 'date': str(txn.date), 'detail': txn.detail,
            'amount': str(txn.amount),
            'category': txn.category.name if txn.category else None,
            'subcategory': txn.subcategory.name if txn.subcategory else None,
        }})
    except TransactionLog.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['POST'])
def api_subcategory_create(request):
    try:
        body = json.loads(request.body)
        sub = SubCategory.objects.create(
            user=request.user,
            pillar_id=body['pillar_id'],
            name=body['name'],
            due_day=body.get('due_day'),
        )
        return JsonResponse({
            'status': 'ok', 'subcategory': {
                'id': sub.id, 'name': sub.name, 'pillar': sub.pillar_id,
                'due_day': sub.due_day,
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['POST'])
def api_subcategory_delete(request, sub_id):
    try:
        sub = SubCategory.objects.get(id=sub_id, user=request.user)
        sub.delete()
        return JsonResponse({'status': 'ok'})
    except SubCategory.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


@ajax_login_required
@require_http_methods(['GET', 'POST'])
def api_budget_targets(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            target, _ = MonthlyBudgetTarget.objects.update_or_create(
                user=request.user,
                subcategory_id=body['subcategory_id'],
                year=body['year'],
                month=body['month'],
                defaults={'budgeted_amount': body['budgeted_amount']}
            )
            return JsonResponse({
                'status': 'ok',
                'target': {
                    'id': target.id, 'subcategory_id': target.subcategory_id,
                    'year': target.year, 'month': target.month,
                    'budgeted_amount': str(target.budgeted_amount),
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    year = int(request.GET.get('year', datetime.now().year))
    month = request.GET.get('month')
    qs = MonthlyBudgetTarget.objects.filter(user=request.user, year=year)
    if month:
        qs = qs.filter(month=int(month))
    data = []
    for t in qs:
        data.append({
            'id': t.id, 'subcategory_id': t.subcategory_id,
            'subcategory_name': t.subcategory.name,
            'pillar': t.subcategory.pillar.name,
            'year': t.year, 'month': t.month,
            'budgeted_amount': str(t.budgeted_amount),
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_transaction_matrix(request):
    year = int(request.GET.get('year', datetime.now().year))
    expense_pillars = FinancialPillar.objects.filter(
        name__in=['INCOME', 'BILLS', 'SUBSCRIPTIONS', 'EXPENSES', 'SAVINGS_INVESTMENTS', 'DEBT', 'CREDIT']
    )
    rows = (
        TransactionLog.objects.filter(user=request.user, date__year=year, category__in=expense_pillars)
        .values('subcategory_id', 'subcategory__name', 'subcategory__pillar__name', 'date__month')
        .annotate(total=Sum('amount'))
        .order_by('date__month')
    )
    actuals = {}
    for r in rows:
        key = (r['subcategory_id'], r['date__month'])
        actuals[key] = {
            'subcategory_id': r['subcategory_id'],
            'subcategory_name': r['subcategory__name'],
            'pillar': r['subcategory__pillar__name'],
            'month': r['date__month'],
            'total': str(r['total']),
        }

    qs = MonthlyBudgetTarget.objects.filter(user=request.user, year=year)
    budgets = {}
    for t in qs:
        key = (t.subcategory_id, t.month)
        budgets[key] = {
            'subcategory_id': t.subcategory_id,
            'subcategory_name': t.subcategory.name,
            'pillar': t.subcategory.pillar.name,
            'month': t.month,
            'budgeted_amount': str(t.budgeted_amount),
        }

    all_keys = set(list(actuals.keys()) + list(budgets.keys()))
    data = []
    for key in sorted(all_keys):
        a = actuals.get(key, {})
        b = budgets.get(key, {})
        data.append({
            'subcategory_id': key[0],
            'month': key[1],
            'subcategory_name': a.get('subcategory_name') or b.get('subcategory_name'),
            'pillar': a.get('pillar') or b.get('pillar'),
            'actual': a.get('total', '0.00'),
            'budgeted': b.get('budgeted_amount', '0.00'),
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_dashboard_stats(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    income_pillar = FinancialPillar.objects.get(name='INCOME')
    total_income = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category=income_pillar
    ).aggregate(s=Sum('amount'))['s'] or 0

    expense_pillars = FinancialPillar.objects.filter(
        name__in=['BILLS', 'SUBSCRIPTIONS', 'EXPENSES']
    )
    total_outlays = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category__in=expense_pillars
    ).aggregate(s=Sum('amount'))['s'] or 0

    debt_pillar = FinancialPillar.objects.get(name='DEBT')
    total_debt = TransactionLog.objects.filter(
        user=request.user, category=debt_pillar
    ).aggregate(s=Sum('amount'))['s'] or 0

    savings_pillar = FinancialPillar.objects.get(name='SAVINGS_INVESTMENTS')
    total_savings = TransactionLog.objects.filter(
        user=request.user, category=savings_pillar, amount__gt=0
    ).aggregate(s=Sum('amount'))['s'] or 0

    all_income = TransactionLog.objects.filter(
        user=request.user, category=income_pillar
    ).aggregate(s=Sum('amount'))['s'] or 0

    all_outlays = TransactionLog.objects.filter(
        user=request.user, category__in=expense_pillars
    ).aggregate(s=Sum('amount'))['s'] or 0

    net_worth = all_income + total_savings - all_outlays - total_debt

    expense_txns = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category__in=expense_pillars
    )
    txn_count = expense_txns.count()
    variable_spend_velocity = round(float(total_outlays) / max(txn_count, 1), 2)

    debt_goals = DebtBalanceHistory.objects.filter(
        user=request.user, year=year, month=month
    ).aggregate(s=Sum('outstanding_balance'))['s'] or 0
    debt_paid = DebtBalanceHistory.objects.filter(
        user=request.user
    ).aggregate(s=Sum('payment_made'))['s'] or 0
    initial_debt = debt_goals + debt_paid
    debt_progress = round(
        (float(debt_paid) / float(max(initial_debt, 1))) * 100, 2
    ) if initial_debt > 0 else 0

    return JsonResponse({
        'net_worth': str(net_worth),
        'total_income': str(total_income),
        'total_outlays': str(total_outlays),
        'variable_spend_velocity': variable_spend_velocity,
        'total_debt': str(total_debt),
        'total_savings': str(total_savings),
        'debt_progress': debt_progress,
    })


@ajax_login_required
@require_http_methods(['GET'])
def api_chart_data(request):
    year = int(request.GET.get('year', datetime.now().year))

    income_pillar = FinancialPillar.objects.get(name='INCOME')
    expense_pillars = FinancialPillar.objects.filter(
        name__in=['BILLS', 'SUBSCRIPTIONS', 'EXPENSES']
    )

    months = list(range(1, 13))
    income_data = []
    expense_data = []

    for m in months:
        inc = TransactionLog.objects.filter(
            user=request.user, date__year=year, date__month=m,
            category=income_pillar
        ).aggregate(s=Sum('amount'))['s'] or 0
        exp = TransactionLog.objects.filter(
            user=request.user, date__year=year, date__month=m,
            category__in=expense_pillars
        ).aggregate(s=Sum('amount'))['s'] or 0
        income_data.append(float(inc))
        expense_data.append(float(exp))

    expense_cats = TransactionLog.objects.filter(
        user=request.user, date__year=year,
        category__in=expense_pillars
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')

    expense_labels = []
    expense_values = []
    for ec in expense_cats:
        expense_labels.append(ec['category__name'])
        expense_values.append(float(ec['total']))

    debt_pillar = FinancialPillar.objects.get(name='DEBT')
    debt_data = []
    for m in months:
        d = TransactionLog.objects.filter(
            user=request.user, date__year=year, date__month=m,
            category=debt_pillar
        ).aggregate(s=Sum('amount'))['s'] or 0
        debt_data.append(float(d))

    return JsonResponse({
        'income_vs_expenses': {'labels': list(range(1, 13)), 'income': income_data, 'expenses': expense_data},
        'expense_dispersal': {'labels': expense_labels, 'values': expense_values},
        'debt_track': {'labels': list(range(1, 13)), 'debt': debt_data},
    })


@ajax_login_required
@require_http_methods(['GET'])
def api_savings_goals(request):
    qs = SavingsGoal.objects.filter(user=request.user).select_related('subcategory')
    data = []
    for g in qs:
        data.append({
            'id': g.id,
            'subcategory_id': g.subcategory_id,
            'subcategory_name': g.subcategory.name,
            'target_goal': str(g.target_goal),
            'starting_amount': str(g.starting_amount),
            'monthly_contribution_target': str(g.monthly_contribution_target),
            'total_saved': str(g.total_saved),
            'left_to_save': str(g.left_to_save),
            'progress_percent': g.progress_percent,
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['POST'])
def api_savings_goal_create(request):
    try:
        body = json.loads(request.body)
        goal = SavingsGoal.objects.create(
            user=request.user,
            subcategory_id=body['subcategory_id'],
            target_goal=body['target_goal'],
            starting_amount=body.get('starting_amount', 0),
            monthly_contribution_target=body.get('monthly_contribution_target', 0),
        )
        return JsonResponse({'status': 'ok', 'goal': {
            'id': goal.id, 'subcategory_id': goal.subcategory_id,
            'subcategory_name': goal.subcategory.name,
            'target_goal': str(goal.target_goal),
            'starting_amount': str(goal.starting_amount),
            'monthly_contribution_target': str(goal.monthly_contribution_target),
            'total_saved': str(goal.total_saved),
            'left_to_save': str(goal.left_to_save),
            'progress_percent': goal.progress_percent,
        }})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['POST'])
def api_savings_goal_update(request, goal_id):
    try:
        goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        body = json.loads(request.body)
        if 'target_goal' in body:
            goal.target_goal = body['target_goal']
        if 'starting_amount' in body:
            goal.starting_amount = body['starting_amount']
        if 'monthly_contribution_target' in body:
            goal.monthly_contribution_target = body['monthly_contribution_target']
        goal.save()
        return JsonResponse({
            'status': 'ok',
            'goal': {
                'id': goal.id,
                'total_saved': str(goal.total_saved),
                'left_to_save': str(goal.left_to_save),
                'progress_percent': goal.progress_percent,
            }
        })
    except SavingsGoal.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['GET'])
def api_debt_history(request):
    year = int(request.GET.get('year', datetime.now().year))
    qs = DebtBalanceHistory.objects.filter(
        user=request.user, year=year
    ).select_related('subcategory')
    data = []
    for d in qs:
        data.append({
            'id': d.id, 'subcategory_id': d.subcategory_id,
            'subcategory_name': d.subcategory.name,
            'year': d.year, 'month': d.month,
            'outstanding_balance': str(d.outstanding_balance),
            'payment_made': str(d.payment_made),
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['POST'])
def api_debt_history_update(request):
    try:
        body = json.loads(request.body)
        obj, _ = DebtBalanceHistory.objects.update_or_create(
            user=request.user,
            subcategory_id=body['subcategory_id'],
            year=body['year'],
            month=body['month'],
            defaults={
                'outstanding_balance': body['outstanding_balance'],
                'payment_made': body.get('payment_made', 0),
            }
        )
        return JsonResponse({'status': 'ok', 'id': obj.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['GET'])
def api_calendar_events(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    expense_pillars = FinancialPillar.objects.filter(
        name__in=['EXPENSES', 'BILLS', 'SUBSCRIPTIONS']
    )

    txns = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category__in=expense_pillars
    ).values('date').annotate(total=Sum('amount')).order_by('date')

    events = []
    for t in txns:
        events.append({
            'title': f"₱{t['total']}",
            'start': str(t['date']),
            'allDay': True,
            'backgroundColor': '#fb7185',
            'borderColor': '#fb7185',
            'textColor': '#fff',
            'display': 'background',
        })

    txn_dates = set(t['date'] for t in txns)
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    from datetime import timedelta
    d = start_date
    while d < end_date:
        if d not in txn_dates:
            events.append({
                'title': '✨ No Spend',
                'start': str(d),
                'allDay': True,
                'backgroundColor': '#34d399',
                'borderColor': '#34d399',
                'textColor': '#fff',
            })
        d += timedelta(days=1)

    return JsonResponse(events, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_financial_pillars_summary(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    data = []
    for pillar in FinancialPillar.objects.all():
        total = TransactionLog.objects.filter(
            user=request.user, category=pillar,
            date__year=year, date__month=month
        ).aggregate(s=Sum('amount'))['s'] or 0
        data.append({
            'id': pillar.id,
            'name': pillar.name,
            'display': pillar.get_name_display(),
            'total': str(total),
        })
    return JsonResponse(data, safe=False)
