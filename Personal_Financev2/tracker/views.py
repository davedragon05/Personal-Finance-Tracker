import csv
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


def ajax_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper

from .models import (
    FinancialPillar, SubCategory, TransactionLog,
    MonthlyBudgetTarget, SavingsGoal, DebtBalanceHistory,
    RecurringTransaction, AuditLog, Account,
)


def log_audit(request, action, model_name, object_id=None, details=None):
    AuditLog.objects.create(
        user=request.user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details,
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
            account_id=body.get('account_id'),
            payment_mode=body.get('payment_mode', ''),
            debt_history_id=body.get('debt_history_id'),
        )
        return JsonResponse({
            'status': 'ok',
            'transaction': {
                'id': txn.id, 'date': str(txn.date),
                'detail': txn.detail, 'amount': str(txn.amount),
                'category': txn.category.name if txn.category else None,
                'subcategory': txn.subcategory.name if txn.subcategory else None,
                'payment_mode': txn.payment_mode,
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['GET'])
def api_transactions(request):
    qs = TransactionLog.objects.filter(user=request.user).select_related('category', 'subcategory', 'account')
    year = request.GET.get('year')
    month = request.GET.get('month')
    subcategory_id = request.GET.get('subcategory_id')
    debt_history_id = request.GET.get('debt_history_id')
    if year:
        qs = qs.filter(date__year=int(year))
    if month:
        qs = qs.filter(date__month=int(month))
    if subcategory_id:
        qs = qs.filter(subcategory_id=int(subcategory_id))
    if debt_history_id:
        qs = qs.filter(debt_history_id=int(debt_history_id))
    qs = qs.order_by('-date', '-created_at')

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 0))
    if page_size > 0:
        total = qs.count()
        start = (page - 1) * page_size
        qs = qs[start:start + page_size]
    else:
        total = 0

    debt_ids = [t.debt_history_id for t in qs if t.debt_history_id]
    debt_map = {}
    if debt_ids:
        for d in DebtBalanceHistory.objects.filter(id__in=debt_ids).only('id', 'outstanding_balance', 'is_receivable'):
            debt_map[d.id] = d

    data = []
    for t in qs:
        debt_info = debt_map.get(t.debt_history_id) if t.debt_history_id else None
        data.append({
            'id': t.id, 'date': str(t.date), 'detail': t.detail,
            'amount': str(t.amount),
            'category': t.category.name if t.category else None,
            'category_id': t.category_id,
            'subcategory': t.subcategory.name if t.subcategory else None,
            'subcategory_id': t.subcategory_id,
            'card_credit_type': t.card_credit_type.name if t.card_credit_type else None,
            'account': t.account.name if t.account else None,
            'account_id': t.account_id,
            'payment_mode': t.payment_mode,
            'debt_history_id': t.debt_history_id,
            'debt_outstanding_balance': str(debt_info.outstanding_balance) if debt_info else None,
        })
    if page_size > 0:
        return JsonResponse({'results': data, 'count': total, 'page': page, 'page_size': page_size})
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['DELETE', 'POST'])
def api_transaction_delete(request, txn_id):
    try:
        txn = TransactionLog.objects.get(id=txn_id, user=request.user)
        txn.is_deleted = True
        txn.save(update_fields=['is_deleted'])
        log_audit(request, 'delete', 'TransactionLog', txn_id)
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
        if 'payment_mode' in body:
            txn.payment_mode = body['payment_mode']
        txn.save()
        return JsonResponse({'status': 'ok', 'transaction': {
            'id': txn.id, 'date': str(txn.date), 'detail': txn.detail,
            'amount': str(txn.amount),
            'category': txn.category.name if txn.category else None,
            'subcategory': txn.subcategory.name if txn.subcategory else None,
            'payment_mode': txn.payment_mode,
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

    net_worth = []
    cumulative = 0
    savings_pillar = FinancialPillar.objects.get(name='SAVINGS_INVESTMENTS')
    for m in months:
        inc = income_data[m - 1]
        exp = expense_data[m - 1]
        sav = TransactionLog.objects.filter(
            user=request.user, date__year=year, date__month=m,
            category=savings_pillar
        ).aggregate(s=Sum('amount'))['s'] or 0
        cumulative += inc - exp
        net_worth.append(round(cumulative - debt_data[m - 1] + float(sav), 2))

    return JsonResponse({
        'income_vs_expenses': {'labels': list(range(1, 13)), 'income': income_data, 'expenses': expense_data},
        'expense_dispersal': {'labels': expense_labels, 'values': expense_values},
        'debt_track': {'labels': list(range(1, 13)), 'debt': debt_data},
        'net_worth_over_time': {'labels': list(range(1, 13)), 'net_worth': net_worth},
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
    qs = DebtBalanceHistory.objects.filter(
        user=request.user
    ).select_related('subcategory')
    year = request.GET.get('year')
    if year:
        qs = qs.filter(year=int(year))
    data = []
    for d in qs:
        data.append({
            'id': d.id, 'subcategory_id': d.subcategory_id,
            'subcategory_name': d.subcategory.name,
            'date': d.date.isoformat(),
            'year': d.year, 'month': d.month,
            'outstanding_balance': str(d.outstanding_balance),
            'payment_made': str(d.payment_made),
            'payment_mode': d.payment_mode,
            'is_receivable': d.is_receivable,
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['POST'])
def api_debt_history_update(request):
    try:
        body = json.loads(request.body)
        dt = body.get('date')
        if not dt:
            return JsonResponse({'status': 'error', 'message': 'date required'}, status=400)
        if body.get('is_edit') and body.get('id'):
            obj = DebtBalanceHistory.objects.get(id=body['id'], user=request.user)
            obj.date = dt
            obj.year = int(dt[:4])
            obj.month = int(dt[5:7])
            obj.outstanding_balance = body['outstanding_balance']
            obj.payment_made = body.get('payment_made', 0)
            obj.payment_mode = body.get('payment_mode', '')
            obj.is_receivable = body.get('is_receivable', False)
            obj.save()
        else:
            parsed_date = dt if isinstance(dt, str) else dt.isoformat()
            obj, _ = DebtBalanceHistory.objects.update_or_create(
                user=request.user,
                subcategory_id=body['subcategory_id'],
                date=parsed_date,
                defaults={
                    'year': int(parsed_date[:4]),
                    'month': int(parsed_date[5:7]),
                    'outstanding_balance': body['outstanding_balance'],
                    'payment_made': body.get('payment_made', 0),
                    'payment_mode': body.get('payment_mode', ''),
                    'is_receivable': body.get('is_receivable', False),
                }
            )
        return JsonResponse({'status': 'ok', 'id': obj.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['POST'])
def api_debt_history_delete(request):
    try:
        body = json.loads(request.body)
        obj = DebtBalanceHistory.objects.get(id=body['id'], user=request.user)
        obj.delete()
        return JsonResponse({'status': 'ok'})
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


@ajax_login_required
def api_accounts(request):
    if request.method == 'GET':
        qs = Account.objects.filter(user=request.user)
        data = []
        for a in qs:
            balance = TransactionLog.objects.filter(
                user=request.user, account=a
            ).aggregate(b=Sum('amount'))['b'] or 0
            data.append({
                'id': a.id,
                'name': a.name,
                'account_type': a.account_type,
                'account_type_display': a.get_account_type_display(),
                'opening_balance': str(a.opening_balance),
                'balance': str(round(float(a.opening_balance) + float(balance), 2)),
                'is_active': a.is_active,
            })
        return JsonResponse(data, safe=False)
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            a = Account.objects.create(
                user=request.user,
                name=body['name'],
                account_type=body.get('account_type', 'checking'),
                opening_balance=body.get('opening_balance', 0),
            )
            log_audit(request, 'create', 'Account', a.id)
            return JsonResponse({'status': 'ok', 'id': a.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['DELETE', 'POST'])
def api_account_delete(request, account_id):
    try:
        a = Account.objects.get(id=account_id, user=request.user)
        a.delete()
        log_audit(request, 'delete', 'Account', account_id)
        return JsonResponse({'status': 'ok'})
    except Account.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


@ajax_login_required
def api_recurring_transactions(request):
    if request.method == 'GET':
        qs = RecurringTransaction.objects.filter(user=request.user).select_related('subcategory', 'subcategory__pillar')
        data = []
        for rt in qs:
            data.append({
                'id': rt.id,
                'subcategory_id': rt.subcategory_id,
                'subcategory_name': rt.subcategory.name,
                'pillar_name': rt.subcategory.pillar.name,
                'amount': str(rt.amount),
                'detail': rt.detail,
                'interval': rt.interval,
                'next_due_date': str(rt.next_due_date),
                'active': rt.active,
            })
        return JsonResponse(data, safe=False)
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            rt = RecurringTransaction.objects.create(
                user=request.user,
                subcategory_id=body['subcategory_id'],
                amount=body['amount'],
                detail=body.get('detail', ''),
                interval=body.get('interval', 'monthly'),
                next_due_date=body['next_due_date'],
            )
            return JsonResponse({'status': 'ok', 'id': rt.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['DELETE', 'POST'])
def api_recurring_transaction_delete(request, rt_id):
    try:
        rt = RecurringTransaction.objects.get(id=rt_id, user=request.user)
        rt.delete()
        return JsonResponse({'status': 'ok'})
    except RecurringTransaction.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


@ajax_login_required
@require_http_methods(['GET'])
def api_audit_log(request):
    qs = AuditLog.objects.filter(user=request.user)[:50]
    data = []
    for log in qs:
        data.append({
            'action': log.action,
            'model_name': log.model_name,
            'object_id': log.object_id,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_backup_export(request):
    from .models import Account, TransactionLog, MonthlyBudgetTarget, SavingsGoal, DebtBalanceHistory, RecurringTransaction, AuditLog
    export = {
        'version': 1,
        'exported_at': datetime.now().isoformat(),
        'accounts': list(Account.objects.filter(user=request.user).values('name', 'account_type', 'opening_balance', 'is_active')),
        'transactions': list(TransactionLog.all_objects.filter(user=request.user).values('date', 'detail', 'amount', 'category_id', 'subcategory_id', 'account_id', 'is_deleted')),
        'budget_targets': list(MonthlyBudgetTarget.objects.filter(user=request.user).values('subcategory_id', 'year', 'month', 'budgeted_amount')),
        'savings_goals': list(SavingsGoal.objects.filter(user=request.user).values('subcategory_id', 'target_goal', 'starting_amount', 'monthly_contribution_target')),
        'debt_history': list(DebtBalanceHistory.objects.filter(user=request.user).values('subcategory_id', 'year', 'month', 'outstanding_balance', 'payment_made')),
        'recurring': list(RecurringTransaction.objects.filter(user=request.user).values('subcategory_id', 'amount', 'detail', 'interval', 'next_due_date', 'active')),
    }
    for key in ('accounts', 'transactions', 'budget_targets', 'savings_goals', 'debt_history', 'recurring'):
        for item in export.get(key, []):
            for k, v in item.items():
                if isinstance(v, date):
                    item[k] = str(v)
                elif isinstance(v, Decimal):
                    item[k] = float(v)
    response = JsonResponse(export)
    response['Content-Disposition'] = f'attachment; filename="jarvis_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
    return response


@ajax_login_required
@require_http_methods(['POST'])
def api_backup_import(request):
    try:
        body = json.loads(request.body)
        from .models import Account, TransactionLog, MonthlyBudgetTarget, SavingsGoal, DebtBalanceHistory, RecurringTransaction
        for a_data in body.get('accounts', []):
            Account.objects.get_or_create(
                user=request.user, name=a_data['name'],
                defaults={'account_type': a_data.get('account_type', 'checking'), 'opening_balance': a_data.get('opening_balance', 0), 'is_active': a_data.get('is_active', True)}
            )
        txn_count = 0
        for t_data in body.get('transactions', []):
            TransactionLog.all_objects.create(
                user=request.user,
                date=date.fromisoformat(t_data['date']) if isinstance(t_data['date'], str) else t_data['date'],
                detail=t_data.get('detail', ''),
                amount=t_data['amount'],
                category_id=t_data.get('category_id'),
                subcategory_id=t_data.get('subcategory_id'),
                account_id=t_data.get('account_id'),
                is_deleted=t_data.get('is_deleted', False),
            )
            txn_count += 1
        for b_data in body.get('budget_targets', []):
            MonthlyBudgetTarget.objects.get_or_create(
                user=request.user,
                subcategory_id=b_data['subcategory_id'],
                year=b_data['year'],
                month=b_data['month'],
                defaults={'budgeted_amount': b_data.get('budgeted_amount', 0)}
            )
        for s_data in body.get('savings_goals', []):
            SavingsGoal.objects.get_or_create(
                user=request.user,
                subcategory_id=s_data['subcategory_id'],
                defaults={
                    'target_goal': s_data['target_goal'],
                    'starting_amount': s_data.get('starting_amount', 0),
                    'monthly_contribution_target': s_data.get('monthly_contribution_target', 0),
                }
            )
        for d_data in body.get('debt_history', []):
            DebtBalanceHistory.objects.get_or_create(
                user=request.user,
                subcategory_id=d_data['subcategory_id'],
                year=d_data['year'],
                month=d_data['month'],
                defaults={
                    'outstanding_balance': d_data['outstanding_balance'],
                    'payment_made': d_data.get('payment_made', 0),
                }
            )
        for r_data in body.get('recurring', []):
            RecurringTransaction.objects.get_or_create(
                user=request.user,
                subcategory_id=r_data['subcategory_id'],
                amount=r_data['amount'],
                defaults={
                    'detail': r_data.get('detail', ''),
                    'interval': r_data.get('interval', 'monthly'),
                    'next_due_date': date.fromisoformat(r_data['next_due_date']) if isinstance(r_data['next_due_date'], str) else r_data['next_due_date'],
                    'active': r_data.get('active', True),
                }
            )
        log_audit(request, 'import', 'Backup', details={'transactions': txn_count})
        return JsonResponse({'status': 'ok', 'transactions_imported': txn_count})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['POST'])
def api_transactions_import_csv(request):
    try:
        import csv, io
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'status': 'error', 'message': 'No file uploaded'}, status=400)
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        created = 0
        for row in reader:
            raw_date = row.get('Date', '').strip()
            if not raw_date:
                continue
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%Y-%m-%d'):
                    try:
                        parsed_date = datetime.strptime(raw_date, fmt).date()
                        break
                    except ValueError:
                        pass
                else:
                    continue
            detail = row.get('Detail', row.get('Description', '')).strip()
            raw_amount = row.get('Amount', '0').strip().replace(',', '').replace('₱', '').replace('PHP', '')
            try:
                amount = float(raw_amount)
            except ValueError:
                continue
            raw_category = row.get('Category', row.get('Pillar', '')).strip().upper()
            pillar = None
            subcategory = None
            if raw_category:
                pillar = FinancialPillar.objects.filter(name=raw_category).first()
                raw_sub = row.get('Subcategory', '').strip()
                if pillar and raw_sub:
                    subcategory = SubCategory.objects.filter(
                        user=request.user, pillar=pillar, name__iexact=raw_sub
                    ).first()
            TransactionLog.objects.create(
                user=request.user,
                date=parsed_date,
                detail=detail,
                amount=amount,
                category=pillar,
                subcategory=subcategory,
                payment_mode=row.get('Payment Mode', row.get('payment_mode', '')).strip(),
            )
            created += 1
        return JsonResponse({'status': 'ok', 'created': created})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@ajax_login_required
@require_http_methods(['GET'])
def api_upcoming_bills(request):
    today = date.today()
    end_date = today + timedelta(days=7)
    qs = RecurringTransaction.objects.filter(
        user=request.user, active=True,
        next_due_date__lte=end_date
    ).select_related('subcategory', 'subcategory__pillar').order_by('next_due_date')
    data = []
    for rt in qs:
        due_in = (rt.next_due_date - today).days
        data.append({
            'id': rt.id,
            'subcategory_name': rt.subcategory.name,
            'pillar_name': rt.subcategory.pillar.name,
            'amount': str(rt.amount),
            'detail': rt.detail,
            'next_due_date': str(rt.next_due_date),
            'due_in_days': due_in,
            'is_overdue': due_in < 0,
        })
    return JsonResponse(data, safe=False)


@ajax_login_required
@require_http_methods(['GET'])
def api_yoy_chart_data(request):
    year = int(request.GET.get('year', datetime.now().year))
    compare_year = year - 1

    income_pillar = FinancialPillar.objects.get(name='INCOME')
    expense_pillars = FinancialPillar.objects.filter(
        name__in=['BILLS', 'SUBSCRIPTIONS', 'EXPENSES']
    )
    debt_pillar = FinancialPillar.objects.get(name='DEBT')
    savings_pillar = FinancialPillar.objects.get(name='SAVINGS_INVESTMENTS')

    months = list(range(1, 13))

    def get_monthly_data(target_year):
        income = []
        expense = []
        debt = []
        net_worth_vals = []
        cumulative = 0
        for m in months:
            inc = TransactionLog.objects.filter(
                user=request.user, date__year=target_year, date__month=m,
                category=income_pillar
            ).aggregate(s=Sum('amount'))['s'] or 0
            exp = TransactionLog.objects.filter(
                user=request.user, date__year=target_year, date__month=m,
                category__in=expense_pillars
            ).aggregate(s=Sum('amount'))['s'] or 0
            d = TransactionLog.objects.filter(
                user=request.user, date__year=target_year, date__month=m,
                category=debt_pillar
            ).aggregate(s=Sum('amount'))['s'] or 0
            sav = TransactionLog.objects.filter(
                user=request.user, date__year=target_year, date__month=m,
                category=savings_pillar
            ).aggregate(s=Sum('amount'))['s'] or 0
            income.append(float(inc))
            expense.append(float(exp))
            debt.append(float(d))
            cumulative += float(inc) - float(exp)
            net_worth_vals.append(round(cumulative - float(d) + float(sav), 2))
        return {'income': income, 'expense': expense, 'debt': debt, 'net_worth': net_worth_vals}

    this_year = get_monthly_data(year)
    last_year = get_monthly_data(compare_year)

    return JsonResponse({
        'this_year': {
            'label': str(year),
            'income_vs_expenses': {'labels': months, 'income': this_year['income'], 'expenses': this_year['expense']},
            'debt_track': {'labels': months, 'debt': this_year['debt']},
            'net_worth_over_time': {'labels': months, 'net_worth': this_year['net_worth']},
        },
        'last_year': {
            'label': str(compare_year),
            'income_vs_expenses': {'labels': months, 'income': last_year['income'], 'expenses': last_year['expense']},
            'debt_track': {'labels': months, 'debt': last_year['debt']},
            'net_worth_over_time': {'labels': months, 'net_worth': last_year['net_worth']},
        },
    })


@ajax_login_required
@require_http_methods(['GET'])
def api_monthly_report_pdf(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))

    income_pillar = FinancialPillar.objects.get(name='INCOME')
    expense_pillars = FinancialPillar.objects.filter(
        name__in=['BILLS', 'SUBSCRIPTIONS', 'EXPENSES']
    )
    debt_pillar = FinancialPillar.objects.get(name='DEBT')
    savings_pillar = FinancialPillar.objects.get(name='SAVINGS_INVESTMENTS')

    total_income = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category=income_pillar
    ).aggregate(s=Sum('amount'))['s'] or 0

    total_expenses = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category__in=expense_pillars
    ).aggregate(s=Sum('amount'))['s'] or 0

    total_debt = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category=debt_pillar
    ).aggregate(s=Sum('amount'))['s'] or 0

    total_savings = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month,
        category=savings_pillar, amount__gt=0
    ).aggregate(s=Sum('amount'))['s'] or 0

    transactions = TransactionLog.objects.filter(
        user=request.user, date__year=year, date__month=month
    ).select_related('category', 'subcategory').order_by('date')

    transactions_by_category = {}
    for txn in transactions:
        cat = txn.category.name if txn.category else 'Uncategorized'
        if cat not in transactions_by_category:
            transactions_by_category[cat] = []
        transactions_by_category[cat].append({
            'date': txn.date,
            'detail': txn.detail,
            'amount': str(txn.amount),
            'subcategory': txn.subcategory.name if txn.subcategory else '',
        })

    month_name = datetime(year, month, 1).strftime('%B %Y')
    net = float(total_income) + float(total_savings) - float(total_expenses) - float(total_debt)

    html = render_to_string('tracker/report_monthly.html', {
        'month_name': month_name,
        'total_income': str(total_income),
        'total_expenses': str(total_expenses),
        'total_debt': str(total_debt),
        'total_savings': str(total_savings),
        'net': str(net),
        'transactions_by_category': transactions_by_category,
        'user': request.user,
    })

    if WEASYPRINT_AVAILABLE:
        pdf = HTML(string=html).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report_{year}_{month:02d}.pdf"'
        return response
    else:
        return HttpResponse(html, content_type='text/html')


@ajax_login_required
@require_http_methods(['GET'])
def api_transactions_export_csv(request):
    year = request.GET.get('year')
    month = request.GET.get('month')
    qs = TransactionLog.objects.filter(user=request.user).select_related('category', 'subcategory', 'account')
    if year:
        qs = qs.filter(date__year=int(year))
    if month:
        qs = qs.filter(date__month=int(month))
    qs = qs.order_by('date', 'created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{year or "all"}_{month or "all"}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Detail', 'Amount', 'Category', 'Subcategory', 'Payment Mode'])
    for t in qs:
        writer.writerow([
            t.date, t.detail, str(t.amount),
            t.category.name if t.category else '',
            t.subcategory.name if t.subcategory else '',
            t.payment_mode,
        ])
    return response
