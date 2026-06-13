import '../css/styles.css';
import 'flowbite';
import Alpine from 'alpinejs';
import Chart from 'chart.js/auto';
import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

window.Alpine = Alpine;
window.Chart = Chart;
window.FullCalendar = { Calendar, dayGridPlugin, interactionPlugin };

function getCSRFToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

function todayLocal() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

async function apiFetch(url, options = {}) {
  window.dispatchEvent(new CustomEvent('api-start'));
  const config = {
    headers: {
      'X-CSRFToken': getCSRFToken(),
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };
  try {
    const response = await fetch(url, config);
    if (response.status === 401) {
      window.location.href = '/login/';
      throw new Error('Authentication required');
    }
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      throw new Error('Expected JSON response, got ' + contentType);
    }
    return await response.json();
  } finally {
    window.dispatchEvent(new CustomEvent('api-end'));
  }
}

function playSyncChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = 'sine';
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.15);
  } catch (e) { /* silent */ }
}

window.getCSRFToken = getCSRFToken;
window.apiFetch = apiFetch;

document.addEventListener('alpine:init', () => {
  Alpine.data('jarvisApp', () => ({
    activePage: 'dashboard',
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
    sidebarCollapsed: localStorage.getItem('jarvis_sidebar') === 'collapsed',
    sidebarOpen: false,
    loading: 0,
    pageLabels: {
      dashboard: 'Mission Control',
      ledger: 'Transaction Ledger',
      matrix: '12-Month Matrix',
      debt: 'Debt Tracker',
      savings: 'Savings Matrix',
      calendar: 'No-Spend Radar',
      reports: 'Reports',
      insights: 'Insights',
      networth: 'Net Worth',
      notifications: 'Notifications',
      settings: 'System Settings',
    },

    pillars: [],
    subcategories: [],
    transactions: [],
    budgetTargets: [],
    matrixActuals: [],
    savingsGoals: [],
    debtHistory: [],
    calendarEvents: [],

    stats: {
      net_worth: '0',
      total_income: '0',
      total_outlays: '0',
      variable_spend_velocity: 0,
      total_debt: '0',
      total_savings: '0',
      debt_progress: 0,
    },

    chartInstances: {},
    receiptPreview: null,
    upcomingBills: [],
    yoyData: null,
    insights: null,
    notifications: [],
    netWorthTrajectory: [],
    spendingByDay: [],
    fullPieData: null,
    reportYear: new Date().getFullYear(),
    reportMonth: new Date().getMonth() + 1,
    reportData: null,
    selectedTxnIds: [],
    searchQuery: '',
    darkMode: true,

    modalOpen: null,

    openModal(name) {
      if (name === 'txn-modal' && this.lastCategoryId) {
        this.form.category_id = this.lastCategoryId;
        this.form.subcategory_id = this.lastSubcategoryId;
        this.loadSubcategories(this.lastCategoryId);
      }
      this.modalOpen = name;
    },
    closeModal() { this.modalOpen = null; },

    form: {
      date: todayLocal(),
      detail: '',
      amount: '',
      category_id: '',
      subcategory_id: '',
      card_credit_type_id: '',
      account_id: '',
      payment_mode: '',
    },

    filter: {
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      category_id: '',
      account_id: '',
    },

    matrixFilter: {
      year: new Date().getFullYear(),
      pillar_id: '',
    },

    settingsFilter: {
      pillar_id: '',
      search: '',
    },

    lastCategoryId: '',
    lastSubcategoryId: '',
    newSubCategory: { pillar_id: '', name: '', due_day: '' },
    budgetModal: { subcategory_id: '', year: 0, month: 0, budgeted_amount: '' },
      debtModal: { id: null, subcategory_id: '', year: 0, month: 0, date: '', outstanding_balance: '', payment_made: 0, payment_mode: '', is_edit: false, is_receivable: false, _manualOverride: false, _paymentMode: false },
    savingsEdit: { target_goal: '', starting_amount: '', monthly_contribution_target: '' },
    newGoal: { subcategory_id: '', target_goal: '', starting_amount: '', monthly_contribution_target: '' },
    contribute: { subcategory_id: '', subcategory_name: '', amount: '', date: new Date().toISOString().slice(0, 10), detail: '' },
    goalHistory: [],
    editTxn: { id: null, date: '', detail: '', amount: '', category_id: '', subcategory_id: '', payment_mode: '' },
    editGoalId: null,

    recurringList: [],
    recurringForm: { subcategory_id: '', amount: '', detail: '', next_due_date: new Date().toISOString().slice(0, 10) },
    accounts: [],
    accountForm: { name: '', account_type: 'checking', opening_balance: '' },
    auditLogs: [],

    calendars: [],

    showScrollBtn: false,

    init() {
      this.showScrollBtn = false;
      this.darkMode = localStorage.getItem('jarvis_theme') !== 'light';
      if (!this.darkMode) {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
      }
      const scrollEl = document.querySelector('main');
      if (scrollEl) {
        scrollEl.addEventListener('scroll', () => {
          this.showScrollBtn = scrollEl.scrollTop > 400;
        });
      }
      this.loadPillars();
      const saved = localStorage.getItem('jarvis_page');
      if (saved && saved !== 'dashboard') {
        this.activePage = saved;
        this.loadPageData(saved);
        if (saved === 'calendar') setTimeout(() => this.initCalendar(), 100);
      } else {
        this.loadDashboard();
        this.loadTransactions();
      }
      this.listenForSync();
      this.$watch('sidebarCollapsed', val => {
        localStorage.setItem('jarvis_sidebar', val ? 'collapsed' : 'expanded');
      });
      window.addEventListener('api-start', () => this.loading++);
      window.addEventListener('api-end', () => this.loading--);
      document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '9') {
          e.preventDefault();
          const pages = ['dashboard', 'ledger', 'matrix', 'debt', 'savings', 'calendar', 'reports', 'insights', 'networth'];
          this.navigate(pages[parseInt(e.key) - 1]);
        }
        if ((e.ctrlKey || e.metaKey) && e.key === '0') {
          e.preventDefault();
          this.navigate('notifications');
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'n' && this.activePage === 'ledger') {
          e.preventDefault();
          this.openModal('txn-modal');
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
          e.preventDefault();
          document.querySelector('[x-ref="searchInput"]')?.focus();
        }
      });
    },

    listenForSync() {
      window.addEventListener('jarvis-sync', () => {
        this.loadDashboard();
        this.loadTransactions();
        this.loadSavingsGoals();
        this.loadBudgetTargets();
      });
    },

    async loadPillars() {
      this.pillars = await apiFetch('/api/pillars/');
    },

    async loadSubcategories(pillarId = null) {
      let url = '/api/subcategories/';
      if (pillarId) url += `?pillar_id=${pillarId}`;
      this.subcategories = await apiFetch(url);
      return this.subcategories;
    },

    getFilteredSubcategories() {
      if (!this.form.category_id) return [];
      return this.subcategories.filter(s => s.pillar == this.form.category_id);
    },
    getFilteredSubcategoriesForEdit() {
      if (!this.editTxn.category_id) return [];
      return this.subcategories.filter(s => s.pillar == this.editTxn.category_id);
    },

    async loadDashboard() {
      this.stats = await apiFetch(`/api/dashboard/stats/?year=${this.year}&month=${this.month}`);
      this.loadCharts();
      this.loadYoYCharts();
      this.loadSavingsGoals();
      this.loadBudgetTargets();
      this.loadDebtHistory();
      this.loadUpcomingBills();
    },

    async loadUpcomingBills() {
      this.upcomingBills = await apiFetch('/api/recurring/upcoming/');
    },

    async uploadReceipt(txnId, event) {
      const file = event.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('receipt', file);
      try {
        const resp = await fetch(`/api/transactions/${txnId}/upload-receipt/`, {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCSRFToken() },
        });
        const result = await resp.json();
        if (result.status === 'ok') {
          const txn = this.transactions.find(t => t.id === txnId);
          if (txn) txn.receipt_url = result.receipt_url;
          this.showToast('Receipt uploaded', 'success');
        } else {
          this.showToast(result.message || 'Upload failed', 'error');
        }
      } catch (e) {
        this.showToast('Upload failed: ' + e.message, 'error');
      }
      event.target.value = '';
    },

    async deleteReceipt(txnId) {
      if (!confirm('Remove this receipt?')) return;
      const result = await apiFetch(`/api/transactions/${txnId}/delete-receipt/`, { method: 'POST' });
      if (result.status === 'ok') {
        const txn = this.transactions.find(t => t.id === txnId);
        if (txn) txn.receipt_url = null;
        this.showToast('Receipt removed', 'success');
      }
    },

    async loadInsights() {
      this.insights = await apiFetch(`/api/analytics/insights/?year=${this.year}`);
      this.spendingByDay = await apiFetch(`/api/analytics/spending-by-day/?year=${this.year}`);
      this.fullPieData = await apiFetch(`/api/analytics/full-pie-chart/?year=${this.year}`);
      setTimeout(() => {
        this.renderDayOfWeekChart();
        this.renderFullPieChart();
      }, 200);
    },

    async loadNetWorthTrajectory() {
      this.netWorthTrajectory = await apiFetch('/api/analytics/net-worth-trajectory/');
      setTimeout(() => this.renderNetWorthTrajectoryChart(), 200);
    },

    async loadReportData() {
      const data = await apiFetch(`/api/dashboard/stats/?year=${this.reportYear}&month=${this.reportMonth}`);
      this.reportData = data;
    },

    async loadNotifications() {
      this.notifications = await apiFetch('/api/analytics/notifications/');
    },

    toggleTheme() {
      this.darkMode = !this.darkMode;
      const html = document.documentElement;
      if (this.darkMode) {
        html.classList.remove('light');
        html.classList.add('dark');
        localStorage.setItem('jarvis_theme', 'dark');
      } else {
        html.classList.remove('dark');
        html.classList.add('light');
        localStorage.setItem('jarvis_theme', 'light');
      }
    },

    toggleSelectTxn(id) {
      const idx = this.selectedTxnIds.indexOf(id);
      if (idx > -1) this.selectedTxnIds.splice(idx, 1);
      else this.selectedTxnIds.push(id);
    },

    toggleSelectAll() {
      if (this.selectedTxnIds.length === this.filteredTransactions.length) {
        this.selectedTxnIds = [];
      } else {
        this.selectedTxnIds = this.filteredTransactions.map(t => t.id);
      }
    },

    async bulkDelete() {
      if (!this.selectedTxnIds.length || !confirm(`Delete ${this.selectedTxnIds.length} transaction(s)?`)) return;
      await apiFetch('/api/transactions/bulk-delete/', {
        method: 'POST',
        body: JSON.stringify({ ids: this.selectedTxnIds }),
      });
      this.selectedTxnIds = [];
      window.dispatchEvent(new CustomEvent('jarvis-sync'));
      this.showToast('Transactions deleted', 'success');
    },

    get filteredTransactions() {
      if (!this.searchQuery) return this.transactions;
      const q = this.searchQuery.toLowerCase();
      return this.transactions.filter(t =>
        (t.detail && t.detail.toLowerCase().includes(q)) ||
        (t.subcategory_name && t.subcategory_name.toLowerCase().includes(q)) ||
        (t.category && t.category.toLowerCase().includes(q))
      );
    },

    get accountOptions() {
      return [{ id: '', name: 'All Accounts' }, ...this.accounts.map(a => ({ id: a.id, name: a.name }))];
    },

    async loadYoYCharts() {
      this.yoyData = await apiFetch(`/api/dashboard/charts/yoy/?year=${this.year}`);
      setTimeout(() => {
        this.renderYoYIncomeChart();
        this.renderYoYDebtChart();
        this.renderYoYNetWorthChart();
      }, 200);
    },

    downloadMonthlyReport() {
      const y = this.year;
      const m = this.month;
      window.open(`/api/reports/monthly/?year=${y}&month=${m}`, '_blank');
    },

    txnPage: 1,
    txnPageSize: 50,
    txnTotal: 0,

    async loadTransactions() {
      const y = this.filter?.year || this.year;
      const m = this.filter?.month || this.month;
      const a = this.filter?.account_id || '';
      const resp = await apiFetch(`/api/transactions/?year=${y}&month=${m}&account_id=${a}&page=${this.txnPage}&page_size=${this.txnPageSize}`);
      if (Array.isArray(resp)) {
        this.transactions = resp;
        this.txnTotal = resp.length;
      } else {
        this.transactions = resp.results || [];
        this.txnTotal = resp.count || 0;
      }
    },

    async loadBudgetTargets() {
      const y = this.matrixFilter?.year || this.year;
      this.budgetTargets = await apiFetch(`/api/budget-targets/?year=${y}`);
      this.matrixActuals = await apiFetch(`/api/transaction-matrix/?year=${y}`);
    },

    async loadSavingsGoals() {
      this.savingsGoals = await apiFetch('/api/savings-goals/');
    },

    async loadDebtHistory() {
      this.debtHistory = await apiFetch('/api/debt-history/');
    },

    groupedDebtData() {
      const groups = {};
      for (const entry of this.debtHistory) {
        const key = entry.subcategory_name;
        if (!groups[key]) groups[key] = { name: key, entries: [], total_collected: 0, is_receivable: entry.is_receivable };
        groups[key].entries.push(entry);
        groups[key].total_collected += parseFloat(entry.payment_made);
        if (entry.is_receivable) groups[key].is_receivable = true;
      }
      const result = [];
      for (const key in groups) {
        const g = groups[key];
        const sorted = g.entries.sort((a, b) => a.year - b.year || a.month - b.month);
        const latest = sorted[sorted.length - 1];
        const current_balance = parseFloat(latest.outstanding_balance);
        const total_tracked = current_balance + g.total_collected;
        const progress = total_tracked > 0 ? (g.total_collected / total_tracked) * 100 : 0;
        result.push({
          name: key,
          entries: sorted,
          total_tracked: total_tracked,
          total_collected: g.total_collected,
          current_balance: current_balance,
          progress: Math.min(progress, 100),
          is_paid: current_balance <= 0,
          is_receivable: g.is_receivable,
        });
      }
      return result.sort((a, b) => a.name.localeCompare(b.name));
    },

    yearDebtStats(entries) {
      const y = this.filter?.year || new Date().getFullYear();
      const filtered = entries.filter(e => e.year === y);
      if (filtered.length === 0) return { total_collected: 0, current_balance: 0 };
      const sorted = filtered.sort((a, b) => a.month - b.month);
      const latest = sorted[sorted.length - 1];
      return {
        total_collected: filtered.reduce((s, e) => s + parseFloat(e.payment_made), 0),
        current_balance: parseFloat(latest.outstanding_balance),
      };
    },

    autoFillOutstanding() {
      if (this.debtModal.is_edit || this.debtModal._manualOverride) return;
      const subId = this.debtModal.subcategory_id;
      const payment = parseFloat(this.debtModal.payment_made);
      if (!subId || !payment || payment <= 0) return;
      const prev = this.debtHistory
        .filter(e => e.subcategory_id == subId)
        .sort((a, b) => b.id - a.id);
      if (prev.length === 0) return;
      const prevBal = parseFloat(prev[0].outstanding_balance);
      this.debtModal.outstanding_balance = Math.max(prevBal - payment, 0);
    },
    markManualOverride() {
      this.debtModal._manualOverride = true;
    },

    async handleTransactionSubmit() {
      const payload = {
        date: this.form.date,
        detail: this.form.detail,
        amount: this.form.amount,
        category_id: this.form.category_id,
        subcategory_id: this.form.subcategory_id || null,
        card_credit_type_id: this.form.card_credit_type_id || null,
        account_id: this.form.account_id || null,
        payment_mode: this.form.payment_mode,
      };
      const result = await apiFetch('/api/transactions/create/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (result.status === 'ok') {
        playSyncChime();
        this.lastCategoryId = this.form.category_id;
        this.lastSubcategoryId = this.form.subcategory_id;
        this.form = {
          date: todayLocal(),
          detail: '',
          amount: '',
          category_id: '',
          subcategory_id: '',
          card_credit_type_id: '',
          account_id: '',
          payment_mode: '',
        };
        window.dispatchEvent(new CustomEvent('jarvis-sync'));
        this.showToast('Transaction logged successfully', 'success');
      } else {
        this.showToast(result.message || 'Error logging transaction', 'error');
      }
    },

    async deleteTransaction(txnId) {
      if (!confirm('Delete this transaction?')) return;
      await apiFetch(`/api/transactions/${txnId}/delete/`, { method: 'POST' });
      window.dispatchEvent(new CustomEvent('jarvis-sync'));
      this.showToast('Transaction deleted', 'success');
    },

    cloneTransaction(txn) {
      this.form.date = txn.date;
      this.form.detail = txn.detail;
      this.form.amount = txn.amount;
      this.form.category_id = txn.category_id;
      this.form.subcategory_id = txn.subcategory_id;
      this.form.payment_mode = txn.payment_mode || '';
      this.loadSubcategories(txn.category_id);
      this.lastCategoryId = txn.category_id;
      this.lastSubcategoryId = txn.subcategory_id;
      this.openModal('txn-modal');
    },

    async saveBudgetTarget() {
      await apiFetch('/api/budget-targets/', {
        method: 'POST',
        body: JSON.stringify({
          subcategory_id: this.budgetModal.subcategory_id,
          year: this.budgetModal.year,
          month: this.budgetModal.month,
          budgeted_amount: this.budgetModal.budgeted_amount,
        }),
      });
      this.budgetModal = { subcategory_id: '', year: 0, month: 0, budgeted_amount: '' };
      await this.loadBudgetTargets();
      this.showToast('Budget target saved', 'success');
    },

    inlineEditBudget(target, field, event) {
      const val = event.target.textContent.replace(/[₱,]/g, '') || '0';
      apiFetch('/api/budget-targets/', {
        method: 'POST',
        body: JSON.stringify({
          subcategory_id: target.subcategory_id,
          year: target.year,
          month: target.month,
          budgeted_amount: val,
        }),
      }).then(() => {
        this.loadBudgetTargets();
        this.loadDashboard();
      });
    },

    async saveDebtEntry() {
      const payload = { ...this.debtModal };
      payload.is_receivable = payload.is_receivable === true || payload.is_receivable === 'true';
      if (!payload.is_edit && payload.subcategory_id) {
        const hasNewBalance = parseFloat(payload.outstanding_balance) > 0;
        const manualBalance = payload._manualOverride === true;
        if (hasNewBalance && manualBalance) {
          const sub = this.subcategories.find(s => s.id == payload.subcategory_id);
          const name = sub ? sub.name : 'this loan';
          const dup = this.debtHistory.find(e => String(e.subcategory_id) === String(payload.subcategory_id));
          if (dup) {
            let newName = name;
            let attempt = 1;
            while (this.subcategories.some(s => s.name === newName && s.pillar_name === 'DEBT')) {
              attempt++;
              newName = name + ' ' + attempt;
            }
            if (!confirm(`"${name}" already has entries. Create a new DEBT subcategory "${newName}" instead?`)) { return; }
            const debtPillar = this.pillars.find(p => p.name === 'DEBT');
            if (!debtPillar) { this.showToast('Pillar data not loaded yet', 'error'); return; }
            const result = await apiFetch('/api/subcategories/create/', {
              method: 'POST',
              body: JSON.stringify({ pillar_id: debtPillar.id, name: newName }),
            });
            if (result.status !== 'ok') {
              this.showToast(result.message || 'Failed to create subcategory', 'error');
              return;
            }
            payload.subcategory_id = result.subcategory.id;
            await this.loadSubcategories();
          }
        }
      }
      const resp = await apiFetch('/api/debt-history/update/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (resp.status !== 'ok') {
        this.showToast(resp.message || 'Error saving debt entry', 'error');
        return;
      }
      const debtHistoryId = payload.is_edit ? payload.id : resp.id;
      const payment = parseFloat(payload.payment_made) || 0;
      const balance = parseFloat(payload.outstanding_balance) || 0;
      const debtPillar = this.pillars.find(p => p.name === 'DEBT');
      const incomePillar = this.pillars.find(p => p.name === 'INCOME');
      let effectiveAmount, effectivePillar, detail;
      if (payload.is_receivable && payment === 0 && balance > 0) {
        effectiveAmount = balance;
        effectivePillar = debtPillar;
        detail = 'Loan given';
      } else if (payload.is_receivable && payment > 0) {
        effectiveAmount = payment;
        effectivePillar = incomePillar;
        detail = 'Debt repayment received';
      } else {
        effectiveAmount = payment;
        effectivePillar = debtPillar;
        detail = 'Debt payment';
      }
      const txns = await apiFetch(`/api/transactions/?debt_history_id=${debtHistoryId}&limit=all`);
      const existingTxn = Array.isArray(txns) ? txns[0] : (txns.results || [])[0];
      if (effectiveAmount > 0) {
        if (existingTxn) {
          await apiFetch(`/api/transactions/${existingTxn.id}/update/`, {
            method: 'POST',
            body: JSON.stringify({
              amount: effectiveAmount,
              payment_mode: payload.payment_mode,
              date: payload.date,
              detail: detail,
              category_id: effectivePillar.id,
              subcategory_id: payload.subcategory_id,
            }),
          });
        } else {
          await apiFetch('/api/transactions/create/', {
            method: 'POST',
            body: JSON.stringify({
              date: payload.date,
              detail: detail,
              amount: effectiveAmount,
              category_id: effectivePillar.id,
              subcategory_id: payload.subcategory_id,
              payment_mode: payload.payment_mode,
              debt_history_id: debtHistoryId,
            }),
          });
        }
        window.dispatchEvent(new CustomEvent('jarvis-sync'));
      } else if (existingTxn) {
        await apiFetch(`/api/transactions/${existingTxn.id}/delete/`, { method: 'POST' });
        window.dispatchEvent(new CustomEvent('jarvis-sync'));
      }
      this.debtModal = { id: null, subcategory_id: '', year: 0, month: 0, date: '', outstanding_balance: '', payment_made: 0, payment_mode: '', is_edit: false, is_receivable: false, _manualOverride: false, _paymentMode: false };
      await this.loadDebtHistory();
      this.showToast('Debt entry saved', 'success');
    },

    async deleteDebtEntry(id) {
      if (!confirm('Delete this debt entry?')) return;
      const txns = await apiFetch(`/api/transactions/?debt_history_id=${id}&limit=all`);
      const txnList = Array.isArray(txns) ? txns : (txns.results || []);
      for (const txn of txnList) {
        await apiFetch(`/api/transactions/${txn.id}/delete/`, { method: 'POST' });
      }
      await apiFetch('/api/debt-history/delete/', {
        method: 'POST',
        body: JSON.stringify({ id }),
      });
      await this.loadDebtHistory();
      this.showToast('Debt entry deleted', 'success');
    },

    async loadGoalHistory(subcategoryId) {
      this.goalHistory = await apiFetch(`/api/transactions/?subcategory_id=${subcategoryId}&limit=all`);
    },

    async editTransaction(txnId) {
      const payload = {};
      if (this.editTxn.date) payload.date = this.editTxn.date;
      if (this.editTxn.detail !== undefined) payload.detail = this.editTxn.detail;
      if (this.editTxn.amount) payload.amount = this.editTxn.amount;
      if (this.editTxn.category_id) payload.category_id = this.editTxn.category_id;
      if (this.editTxn.subcategory_id) payload.subcategory_id = this.editTxn.subcategory_id;
      if (this.editTxn.payment_mode !== undefined) payload.payment_mode = this.editTxn.payment_mode;
      const result = await apiFetch(`/api/transactions/${txnId}/update/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (result.status === 'ok') {
        this.loadGoalHistory(this.editTxn.subcategory_id);
        this.loadSavingsGoals();
        window.dispatchEvent(new CustomEvent('jarvis-sync'));
        this.closeModal();
        this.showToast('Transaction updated', 'success');
      } else {
        this.showToast(result.message || 'Error updating transaction', 'error');
      }
    },

    async contributeToGoal() {
      const savingsPillar = this.pillars.find(p => p.name === 'SAVINGS_INVESTMENTS');
      const result = await apiFetch('/api/transactions/create/', {
        method: 'POST',
        body: JSON.stringify({
          date: this.contribute.date,
          detail: this.contribute.detail || 'Savings contribution',
          amount: this.contribute.amount,
          category_id: savingsPillar.id,
          subcategory_id: this.contribute.subcategory_id,
        }),
      });
      if (result.status === 'ok') {
        playSyncChime();
        this.contribute = { subcategory_id: '', subcategory_name: '', amount: '', date: new Date().toISOString().slice(0, 10), detail: '' };
        window.dispatchEvent(new CustomEvent('jarvis-sync'));
        this.loadSavingsGoals();
        this.closeModal();
        this.showToast('Contribution added', 'success');
      } else {
        this.showToast(result.message || 'Error adding contribution', 'error');
      }
    },

    async createSavingsGoal() {
      const result = await apiFetch('/api/savings-goals/create/', {
        method: 'POST',
        body: JSON.stringify(this.newGoal),
      });
      if (result.status === 'ok') {
        this.newGoal = { subcategory_id: '', target_goal: '', starting_amount: '', monthly_contribution_target: '' };
        await this.loadSavingsGoals();
        this.closeModal();
        this.showToast('Savings goal created', 'success');
      } else {
        this.showToast(result.message || 'Error creating goal', 'error');
      }
    },

    async updateSavingsGoal(goalId) {
      const payload = {};
      if (this.savingsEdit.target_goal) payload.target_goal = this.savingsEdit.target_goal;
      if (this.savingsEdit.starting_amount) payload.starting_amount = this.savingsEdit.starting_amount;
      if (this.savingsEdit.monthly_contribution_target) payload.monthly_contribution_target = this.savingsEdit.monthly_contribution_target;
      await apiFetch(`/api/savings-goals/${goalId}/update/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      this.savingsEdit = { target_goal: '', starting_amount: '', monthly_contribution_target: '' };
      await this.loadSavingsGoals();
      window.dispatchEvent(new CustomEvent('jarvis-sync'));
      this.showToast('Savings goal updated', 'success');
    },

    async addSubCategory() {
      const result = await apiFetch('/api/subcategories/create/', {
        method: 'POST',
        body: JSON.stringify(this.newSubCategory),
      });
      if (result.status === 'ok') {
        this.newSubCategory = { pillar_id: '', name: '', due_day: '' };
        await this.loadSubcategories();
        this.showToast('Sub-category added', 'success');
      } else {
        this.showToast(result.message || 'Error adding sub-category', 'error');
      }
    },

    async deleteSubCategory(subId) {
      if (!confirm('Delete this sub-category?')) return;
      const result = await apiFetch(`/api/subcategories/${subId}/delete/`, { method: 'POST' });
      if (result.status === 'ok') {
        await this.loadSubcategories();
        this.showToast('Sub-category deleted', 'success');
      }
    },

    filteredSubcategories() {
      return this.subcategories.filter(sub => {
        if (this.settingsFilter.pillar_id && sub.pillar != this.settingsFilter.pillar_id) return false;
        if (this.settingsFilter.search && !sub.name.toLowerCase().includes(this.settingsFilter.search.toLowerCase())) return false;
        return true;
      });
    },

    runningBalance(txnId) {
      const sorted = [...this.transactions].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
      let bal = 0;
      for (const t of sorted) {
        const amt = parseFloat(t.amount);
        if (t.category === 'INCOME') bal += amt;
        else bal -= amt;
        if (t.id === txnId) return bal;
      }
      return 0;
    },

    perAccountBalance(accountId) {
      const a = this.accounts.find(ac => ac.id === accountId);
      return a ? a.balance : null;
    },

    async loadRecurring() {
      this.recurringList = await apiFetch('/api/recurring/');
    },

    async addRecurring() {
      const result = await apiFetch('/api/recurring/', {
        method: 'POST',
        body: JSON.stringify(this.recurringForm),
      });
      if (result.status === 'ok') {
        this.recurringForm = { subcategory_id: '', amount: '', detail: '', next_due_date: new Date().toISOString().slice(0, 10) };
        await this.loadRecurring();
        this.showToast('Recurring transaction added', 'success');
      } else {
        this.showToast(result.message || 'Error adding recurring transaction', 'error');
      }
    },

    async deleteRecurring(id) {
      if (!confirm('Delete this recurring transaction?')) return;
      await apiFetch(`/api/recurring/${id}/delete/`, { method: 'POST' });
      await this.loadRecurring();
      this.showToast('Recurring transaction deleted', 'success');
    },

    async loadAccounts() {
      this.accounts = await apiFetch('/api/accounts/');
    },

    async loadAuditLog() {
      this.auditLogs = await apiFetch('/api/audit-log/');
    },

    async addAccount() {
      const result = await apiFetch('/api/accounts/', {
        method: 'POST',
        body: JSON.stringify(this.accountForm),
      });
      if (result.status === 'ok') {
        this.accountForm = { name: '', account_type: 'checking', opening_balance: '' };
        await this.loadAccounts();
        this.showToast('Account added', 'success');
      } else {
        this.showToast(result.message || 'Error adding account', 'error');
      }
    },

    async deleteAccount(id) {
      if (!confirm('Delete this account?')) return;
      await apiFetch(`/api/accounts/${id}/delete/`, { method: 'POST' });
      await this.loadAccounts();
      this.showToast('Account deleted', 'success');
    },

    backupExport() {
      window.open('/api/backup/export/', '_blank');
    },

    async backupImport(event) {
      const file = event.target.files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const result = await apiFetch('/api/backup/import/', {
          method: 'POST',
          body: text,
        });
        if (result.status === 'ok') {
          this.showToast(`Restored ${result.transactions_imported} transaction(s)`, 'success');
        } else {
          this.showToast(result.message || 'Restore failed', 'error');
        }
      } catch (e) {
        this.showToast('Restore failed: ' + e.message, 'error');
      }
      event.target.value = '';
    },

    async importCSV(event) {
      const file = event.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      try {
        const resp = await fetch('/api/transactions/import/csv/', {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCSRFToken() },
        });
        const result = await resp.json();
        if (result.status === 'ok') {
          await this.loadTransactions();
          this.showToast(`Imported ${result.created} transaction(s)`, 'success');
        } else {
          this.showToast(result.message || 'Import failed', 'error');
        }
      } catch (e) {
        this.showToast('Import failed: ' + e.message, 'error');
      }
      event.target.value = '';
    },

    toggleMobileSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    },
    closeMobileSidebar() {
      this.sidebarOpen = false;
    },

    loadPageData(page) {
      if (page === 'dashboard') { this.loadDashboard(); this.loadAccounts(); }
      if (page === 'ledger') { this.loadTransactions(); this.loadSubcategories(); this.loadAccounts(); }
      if (page === 'matrix') { this.loadBudgetTargets(); this.loadSubcategories(); }
      if (page === 'savings') { this.loadSavingsGoals(); this.loadSubcategories(); }
      if (page === 'debt') { this.loadDebtHistory(); this.loadSubcategories(); }
      if (page === 'reports') { this.loadReportData(); }
      if (page === 'insights') { this.loadInsights(); }
      if (page === 'networth') { this.loadDashboard(); this.loadAccounts(); this.loadNetWorthTrajectory(); }
      if (page === 'notifications') { this.loadNotifications(); this.loadUpcomingBills(); }
      if (page === 'settings') { this.loadSubcategories(); this.loadRecurring(); this.loadAccounts(); this.loadAuditLog(); }
    },
    navigate(page) {
      this.activePage = page;
      localStorage.setItem('jarvis_page', page);
      this.loadPillars();
      this.loadPageData(page);
      setTimeout(() => this.initCalendar(), 100);
    },

    initCalendar() {
      if (this.activePage !== 'calendar') return;
      const el = document.getElementById('nospend-calendar');
      if (!el) return;

      this.calendars.forEach(c => c.destroy());
      this.calendars = [];

      const cal = new FullCalendar.Calendar(el, {
        plugins: [FullCalendar.dayGridPlugin, FullCalendar.interactionPlugin],
        initialView: 'dayGridMonth',
        initialDate: `${this.year}-${String(this.month).padStart(2, '0')}-01`,
        headerToolbar: {
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth',
        },
        height: 'auto',
        themeSystem: 'standard',
        eventSources: [{
          url: `/api/calendar/events/?year=${this.year}&month=${this.month}`,
          method: 'GET',
          extraParams: { _: Date.now() },
        }],
        eventDidMount: (info) => {
          if (info.event.display === 'background') {
            info.el.style.opacity = '0.3';
          }
        },
      });
      cal.render();
      this.calendars.push(cal);
    },

    async loadCharts() {
      const data = await apiFetch(`/api/dashboard/charts/?year=${this.year}`);
      setTimeout(() => {
        this.renderIncomeChart(data);
        this.renderExpenseChart(data);
        this.renderDebtChart(data);
        this.renderNetWorthChart(data);
      }, 100);
    },

    renderIncomeChart(data) {
      const el = document.getElementById('chart-income-expense');
      if (!el) return;
      if (this.chartInstances.income) this.chartInstances.income.destroy();
      this.chartInstances.income = new Chart(el, {
        type: 'bar',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [
            {
              label: 'Income',
              data: data.income_vs_expenses.income,
              backgroundColor: 'rgba(52, 211, 153, 0.6)',
              borderColor: 'rgba(52, 211, 153, 1)',
              borderWidth: 1,
            },
            {
              label: 'Expenses',
              data: data.income_vs_expenses.expenses,
              backgroundColor: 'rgba(251, 113, 133, 0.6)',
              borderColor: 'rgba(251, 113, 133, 1)',
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderExpenseChart(data) {
      const el = document.getElementById('chart-expense-dispersal');
      if (!el) return;
      if (this.chartInstances.expense) this.chartInstances.expense.destroy();
      const colors = ['#fb7185', '#fbbf24', '#a78bfa', '#34d399', '#f472b6', '#f97316'];
      this.chartInstances.expense = new Chart(el, {
        type: 'doughnut',
        data: {
          labels: data.expense_dispersal.labels,
          datasets: [{
            data: data.expense_dispersal.values,
            backgroundColor: colors.slice(0, data.expense_dispersal.labels.length),
            borderColor: '#0f172a',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' }, padding: 12 },
            },
          },
        },
      });
    },

    renderDebtChart(data) {
      const el = document.getElementById('chart-debt-track');
      if (!el) return;
      if (this.chartInstances.debt) this.chartInstances.debt.destroy();
      this.chartInstances.debt = new Chart(el, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [{
            label: 'Debt Payments',
            data: data.debt_track.debt,
            borderColor: 'rgba(251, 113, 133, 1)',
            backgroundColor: 'rgba(251, 113, 133, 0.1)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: 'rgba(251, 113, 133, 0.8)',
            pointRadius: 3,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderYoYIncomeChart() {
      const el = document.getElementById('chart-yoy-income');
      if (!el || !this.yoyData) return;
      if (this.chartInstances.yoyIncome) this.chartInstances.yoyIncome.destroy();
      const d = this.yoyData;
      this.chartInstances.yoyIncome = new Chart(el, {
        type: 'bar',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [
            {
              label: d.this_year.label + ' Income',
              data: d.this_year.income_vs_expenses.income,
              backgroundColor: 'rgba(52, 211, 153, 0.6)',
              borderColor: 'rgba(52, 211, 153, 1)',
              borderWidth: 1,
              borderRadius: 2,
            },
            {
              label: d.this_year.label + ' Expenses',
              data: d.this_year.income_vs_expenses.expenses,
              backgroundColor: 'rgba(251, 113, 133, 0.6)',
              borderColor: 'rgba(251, 113, 133, 1)',
              borderWidth: 1,
              borderRadius: 2,
            },
            {
              label: d.last_year.label + ' Income',
              data: d.last_year.income_vs_expenses.income,
              backgroundColor: 'rgba(52, 211, 153, 0.2)',
              borderColor: 'rgba(52, 211, 153, 0.6)',
              borderWidth: 1,
              borderRadius: 2,
              borderDash: [4, 3],
            },
            {
              label: d.last_year.label + ' Expenses',
              data: d.last_year.income_vs_expenses.expenses,
              backgroundColor: 'rgba(251, 113, 133, 0.2)',
              borderColor: 'rgba(251, 113, 133, 0.6)',
              borderWidth: 1,
              borderRadius: 2,
              borderDash: [4, 3],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' }, boxWidth: 12, padding: 8 } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderYoYDebtChart() {
      const el = document.getElementById('chart-yoy-debt');
      if (!el || !this.yoyData) return;
      if (this.chartInstances.yoyDebt) this.chartInstances.yoyDebt.destroy();
      const d = this.yoyData;
      this.chartInstances.yoyDebt = new Chart(el, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [
            {
              label: d.this_year.label + ' Debt',
              data: d.this_year.debt_track.debt,
              borderColor: 'rgba(251, 113, 133, 1)',
              backgroundColor: 'rgba(251, 113, 133, 0.1)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: 'rgba(251, 113, 133, 0.8)',
              pointRadius: 3,
            },
            {
              label: d.last_year.label + ' Debt',
              data: d.last_year.debt_track.debt,
              borderColor: 'rgba(251, 113, 133, 0.4)',
              backgroundColor: 'rgba(251, 113, 133, 0.02)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: 'rgba(251, 113, 133, 0.3)',
              pointRadius: 3,
              borderDash: [4, 3],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' }, boxWidth: 12, padding: 8 } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderYoYNetWorthChart() {
      const el = document.getElementById('chart-yoy-networth');
      if (!el || !this.yoyData) return;
      if (this.chartInstances.yoyNetWorth) this.chartInstances.yoyNetWorth.destroy();
      const d = this.yoyData;
      this.chartInstances.yoyNetWorth = new Chart(el, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [
            {
              label: d.this_year.label + ' Net Worth',
              data: d.this_year.net_worth_over_time.net_worth,
              borderColor: 'rgba(52, 211, 153, 1)',
              backgroundColor: 'rgba(52, 211, 153, 0.1)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: 'rgba(52, 211, 153, 0.8)',
              pointRadius: 3,
            },
            {
              label: d.last_year.label + ' Net Worth',
              data: d.last_year.net_worth_over_time.net_worth,
              borderColor: 'rgba(52, 211, 153, 0.4)',
              backgroundColor: 'rgba(52, 211, 153, 0.02)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: 'rgba(52, 211, 153, 0.3)',
              pointRadius: 3,
              borderDash: [4, 3],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' }, boxWidth: 12, padding: 8 } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderDayOfWeekChart() {
      const el = document.getElementById('chart-day-of-week');
      if (!el) return;
      if (this.chartInstances.dayOfWeek) this.chartInstances.dayOfWeek.destroy();
      const colors = ['#fb7185', '#fbbf24', '#a78bfa', '#34d399', '#f472b6', '#60a5fa', '#f97316'];
      this.chartInstances.dayOfWeek = new Chart(el, {
        type: 'bar',
        data: {
          labels: this.spendingByDay.map(d => d.day),
          datasets: [{
            label: 'Total Spent',
            data: this.spendingByDay.map(d => d.total),
            backgroundColor: colors.slice(0, this.spendingByDay.length),
            borderColor: colors.slice(0, this.spendingByDay.length).map(c => c.replace('0.', '1.')),
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderFullPieChart() {
      const el = document.getElementById('chart-full-pie');
      if (!el || !this.fullPieData) return;
      if (this.chartInstances.fullPie) this.chartInstances.fullPie.destroy();
      const colors = ['#34d399', '#fb7185', '#fbbf24', '#a78bfa', '#60a5fa', '#f472b6', '#f97316'];
      this.chartInstances.fullPie = new Chart(el, {
        type: 'doughnut',
        data: {
          labels: this.fullPieData.labels,
          datasets: [{
            data: this.fullPieData.values,
            backgroundColor: colors.slice(0, this.fullPieData.labels.length),
            borderColor: '#0f172a',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' }, padding: 12 },
            },
          },
        },
      });
    },

    renderNetWorthTrajectoryChart() {
      const el = document.getElementById('chart-net-worth-trajectory');
      if (!el) return;
      if (this.chartInstances.netWorthTrajectory) this.chartInstances.netWorthTrajectory.destroy();
      this.chartInstances.netWorthTrajectory = new Chart(el, {
        type: 'line',
        data: {
          labels: this.netWorthTrajectory.map(d => d.month),
          datasets: [{
            label: 'Net Worth',
            data: this.netWorthTrajectory.map(d => d.net_worth),
            borderColor: 'rgba(52, 211, 153, 1)',
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: 'rgba(52, 211, 153, 0.8)',
            pointRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } } } },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    renderNetWorthChart(data) {
      const el = document.getElementById('chart-net-worth');
      if (!el) return;
      if (this.chartInstances.netWorth) this.chartInstances.netWorth.destroy();
      this.chartInstances.netWorth = new Chart(el, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          datasets: [{
            label: 'Net Worth',
            data: data.net_worth_over_time.net_worth,
            borderColor: 'rgba(52, 211, 153, 1)',
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
            fill: true,
            tension: 0.4,
            pointBackgroundColor: 'rgba(52, 211, 153, 0.8)',
            pointRadius: 3,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'JetBrains Mono, monospace' } } },
          },
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(100, 116, 139, 0.1)' } },
          },
        },
      });
    },

    showToast(msg, type = 'success') {
      const toast = document.getElementById('jarvis-toast');
      if (!toast) return;
      const msgEl = toast.querySelector('.toast-message');
      if (msgEl) msgEl.textContent = msg;
      toast.className = `fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg backdrop-blur-md border text-sm font-mono transition-all duration-500 translate-x-0 opacity-100 ${
        type === 'success'
          ? 'bg-emerald-900/80 border-emerald-500/60 text-emerald-300 shadow-[0_0_16px_rgba(52,211,153,0.15)]'
          : 'bg-rose-900/80 border-rose-500/60 text-rose-300 shadow-[0_0_16px_rgba(251,113,133,0.15)]'
      }`;
      toast.classList.remove('hidden');
      setTimeout(() => {
        toast.classList.add('translate-x-4', 'opacity-0');
        setTimeout(() => {
          toast.classList.add('hidden');
          toast.classList.remove('translate-x-4', 'opacity-0');
        }, 400);
      }, 2800);
    },

    formatCurrency(val) {
      const num = parseFloat(val) || 0;
      return '₱' + num.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    numberWithCommas(x) {
      if (!x && x !== 0) return '0.00';
      return parseFloat(x).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    getMonthName(m) {
      const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return names[m - 1] || '';
    },

    formatShortDate(dateStr) {
      if (!dateStr) return '';
      const d = new Date(dateStr + 'T00:00:00');
      return this.getMonthName(d.getMonth() + 1) + ' ' + d.getDate() + ', ' + d.getFullYear();
    },

    months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],

    getBudget(subcategoryId, month) {
      const t = this.budgetTargets.find(b => b.subcategory_id === subcategoryId && b.month === month);
      return t ? t.budgeted_amount : '0.00';
    },

    totalBudgetForMonth(month) {
      return this.budgetTargets
        .filter(b => b.month === month)
        .reduce((sum, b) => sum + (parseFloat(b.budgeted_amount) || 0), 0);
    },

    totalBudgetAllMonths() {
      return this.budgetTargets
        .reduce((sum, b) => sum + (parseFloat(b.budgeted_amount) || 0), 0);
    },

    monthlyIncome() {
      return parseFloat(this.stats.total_income) || 0;
    },
  }));
});

Alpine.start();
