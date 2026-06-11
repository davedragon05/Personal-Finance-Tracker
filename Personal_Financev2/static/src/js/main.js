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
    loading: 0,
    pageLabels: {
      dashboard: 'Mission Control',
      ledger: 'Transaction Ledger',
      matrix: '12-Month Matrix',
      debt: 'Debt Tracker',
      savings: 'Savings Matrix',
      calendar: 'No-Spend Radar',
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
    },

    filter: {
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      category_id: '',
    },

    matrixFilter: {
      year: new Date().getFullYear(),
      pillar_id: '',
    },

    lastCategoryId: '',
    lastSubcategoryId: '',
    newSubCategory: { pillar_id: '', name: '', due_day: '' },
    budgetModal: { subcategory_id: '', year: 0, month: 0, budgeted_amount: '' },
    debtModal: { subcategory_id: '', year: 0, month: 0, outstanding_balance: '', payment_made: 0 },
    savingsEdit: { target_goal: '', starting_amount: '', monthly_contribution_target: '' },
    newGoal: { subcategory_id: '', target_goal: '', starting_amount: '', monthly_contribution_target: '' },
    contribute: { subcategory_id: '', subcategory_name: '', amount: '', date: new Date().toISOString().slice(0, 10), detail: '' },
    goalHistory: [],
    editTxn: { id: null, date: '', detail: '', amount: '', category_id: '', subcategory_id: '' },
    editGoalId: null,

    calendars: [],

    init() {
      this.loadPillars();
      this.loadDashboard();
      this.loadTransactions();
      this.listenForSync();
      this.$watch('sidebarCollapsed', val => {
        localStorage.setItem('jarvis_sidebar', val ? 'collapsed' : 'expanded');
      });
      window.addEventListener('api-start', () => this.loading++);
      window.addEventListener('api-end', () => this.loading--);
      document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '7') {
          e.preventDefault();
          const pages = ['dashboard', 'ledger', 'matrix', 'debt', 'savings', 'calendar', 'settings'];
          this.navigate(pages[parseInt(e.key) - 1]);
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

    async loadDashboard() {
      this.stats = await apiFetch(`/api/dashboard/stats/?year=${this.year}&month=${this.month}`);
      this.loadCharts();
      this.loadSavingsGoals();
      this.loadBudgetTargets();
      this.loadDebtHistory();
    },

    async loadTransactions() {
      this.transactions = await apiFetch(`/api/transactions/?year=${this.year}&month=${this.month}&limit=all`);
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
      this.debtHistory = await apiFetch(`/api/debt-history/?year=${this.year}`);
    },

    async handleTransactionSubmit() {
      const payload = {
        date: this.form.date,
        detail: this.form.detail,
        amount: this.form.amount,
        category_id: this.form.category_id,
        subcategory_id: this.form.subcategory_id || null,
        card_credit_type_id: this.form.card_credit_type_id || null,
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
      await apiFetch('/api/debt-history/update/', {
        method: 'POST',
        body: JSON.stringify(this.debtModal),
      });
      this.debtModal = { subcategory_id: '', year: 0, month: 0, outstanding_balance: '', payment_made: 0 };
      await this.loadDebtHistory();
      this.showToast('Debt entry saved', 'success');
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
      const result = await apiFetch(`/api/subcategories/${subId}/delete/`, { method: 'POST' });
      if (result.status === 'ok') {
        await this.loadSubcategories();
        this.showToast('Sub-category deleted', 'success');
      }
    },

    navigate(page) {
      this.activePage = page;
      this.loadPillars();
      if (page === 'dashboard') this.loadDashboard();
      if (page === 'ledger') { this.loadTransactions(); this.loadSubcategories(); }
      if (page === 'matrix') { this.loadBudgetTargets(); this.loadSubcategories(); }
      if (page === 'savings') { this.loadSavingsGoals(); this.loadSubcategories(); }
      if (page === 'debt') { this.loadDebtHistory(); this.loadSubcategories(); }
      if (page === 'settings') { this.loadSubcategories(); }
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

    showToast(msg, type = 'success') {
      const toast = document.getElementById('jarvis-toast');
      if (!toast) return;
      const msgEl = toast.querySelector('.toast-message');
      if (msgEl) msgEl.textContent = msg;
      toast.className = `fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg backdrop-blur-md border text-sm font-mono transition-all duration-500 ${
        type === 'success'
          ? 'bg-emerald-900/60 border-emerald-500/50 text-emerald-300'
          : 'bg-rose-900/60 border-rose-500/50 text-rose-300'
      }`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 3000);
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
