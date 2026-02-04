(function(){
  const tg = window.Telegram?.WebApp;
  tg && tg.expand();

  const qs = new URLSearchParams(window.location.search);
  const masterTelegramId = qs.get('mid');

  if (!masterTelegramId) {
    document.body.innerHTML = '<p style="padding:20px;">Ошибка: не указан мастер</p>';
    return;
  }

  // Home button - update href with mid parameter
  const homeBtn = document.querySelector('.home-btn');
  if (homeBtn) {
    homeBtn.href = `/webapp-master/master.html?mid=${encodeURIComponent(masterTelegramId)}`;
  }

  // Calendar state
  const cal = {
    current: new Date(),
    mode: 'period-start', // or 'period-end', 'expense'
    selectedDate: null
  };

  // DOM elements
  const periodBtns = document.querySelectorAll('.period-btn');
  const customPeriodSection = document.getElementById('custom-period');
  const startDateInput = document.getElementById('start-date');
  const endDateInput = document.getElementById('end-date');
  const applyPeriodBtn = document.getElementById('apply-period');
  
  const totalRevenueEl = document.getElementById('total-revenue');
  const appointmentsCountEl = document.getElementById('appointments-count');
  const totalExpensesEl = document.getElementById('total-expenses');
  const expensesCountEl = document.getElementById('expenses-count');
  const totalProfitEl = document.getElementById('total-profit');
  const profitMarginEl = document.getElementById('profit-margin');
  
  const expensesList = document.getElementById('expenses-list');
  const addExpenseBtn = document.getElementById('add-expense-btn');
  const expenseModal = document.getElementById('expense-modal');
  const modalClose = document.getElementById('modal-close');
  const modalTitle = document.getElementById('modal-title');
  const saveExpenseBtn = document.getElementById('save-expense');
  const cancelExpenseBtn = document.getElementById('cancel-expense');
  
  let currentPeriod = 'week';
  let currentStartDate, currentEndDate;
  let revenueChart, expensesChart;

  // Helper functions
  function api(path) { return fetch(path).then(r => r.json()); }
  
  function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
  }
  
  function getCategoryName(category) {
    const names = {
      'materials': 'Материалы',
      'rent': 'Аренда',
      'advertising': 'Реклама',
      'transport': 'Транспорт',
      'education': 'Обучение',
      'equipment': 'Оборудование',
      'other': 'Другое'
    };
    return names[category] || category;
  }
  
  function getPeriodDates(period) {
    const now = new Date();
    let start, end;
    
    if (period === 'week') {
      start = new Date(now);
      start.setDate(now.getDate() - 7);
      end = now;
    } else if (period === 'month') {
      start = new Date(now);
      start.setMonth(now.getMonth() - 1);
      end = now;
    } else if (period === 'year') {
      start = new Date(now);
      start.setFullYear(now.getFullYear() - 1);
      end = now;
    }
    
    return { start, end };
  }
  
  function setCurrentPeriod(period) {
    currentPeriod = period;
    
    if (period === 'custom') {
      customPeriodSection.classList.remove('hidden');
      return;
    } else {
      customPeriodSection.classList.add('hidden');
      const { start, end } = getPeriodDates(period);
      currentStartDate = start;
      currentEndDate = end;
      loadFinancialData();
    }
  }

  // Period selector
  periodBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      periodBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setCurrentPeriod(btn.dataset.period);
    });
  });
  
  applyPeriodBtn.addEventListener('click', () => {
    if (!startDateInput.value || !endDateInput.value) {
      alert('Выберите обе даты');
      return;
    }
    currentStartDate = new Date(startDateInput.value);
    currentEndDate = new Date(endDateInput.value);
    loadFinancialData();
  });

  // Load financial analytics
  async function loadFinancialData() {
    if (!currentStartDate || !currentEndDate) return;
    
    const start = currentStartDate.toISOString();
    const end = currentEndDate.toISOString();
    
    try {
      const data = await api(`/api/master/analytics/financial?mid=${masterTelegramId}&start_date=${start}&end_date=${end}`);
      
      // Update summary cards
      totalRevenueEl.textContent = formatNumber(data.revenue.total) + ' ₽';
      appointmentsCountEl.textContent = `${data.revenue.appointments_count} записей`;
      
      totalExpensesEl.textContent = formatNumber(data.expenses.total) + ' ₽';
      expensesCountEl.textContent = `${data.expenses.by_category.length} категорий`;
      
      totalProfitEl.textContent = formatNumber(data.profit) + ' ₽';
      const margin = data.revenue.total > 0 ? ((data.profit / data.revenue.total) * 100).toFixed(1) : 0;
      profitMarginEl.textContent = `${margin}% маржа`;
      
      // Update charts
      updateRevenueChart(data.revenue.by_service);
      updateExpensesChart(data.expenses.by_category);
      
    } catch (e) {
      console.error('Error loading financial data:', e);
    }
    
    // Load expenses list
    loadExpenses();
  }
  
  // Update revenue chart
  function updateRevenueChart(data) {
    const ctx = document.getElementById('revenue-chart');
    if (!ctx) return;
    
    if (revenueChart) {
      revenueChart.destroy();
    }
    
    const labels = data.map(d => d.service_name);
    const values = data.map(d => d.revenue);
    
    revenueChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Выручка (₽)',
          data: values,
          backgroundColor: 'rgba(75, 192, 192, 0.6)',
          borderColor: 'rgba(75, 192, 192, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }
  
  // Update expenses chart
  function updateExpensesChart(data) {
    const ctx = document.getElementById('expenses-chart');
    if (!ctx) return;
    
    if (expensesChart) {
      expensesChart.destroy();
    }
    
    const labels = data.map(d => getCategoryName(d.category));
    const values = data.map(d => d.total);
    
    expensesChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: [
            'rgba(255, 99, 132, 0.6)',
            'rgba(54, 162, 235, 0.6)',
            'rgba(255, 206, 86, 0.6)',
            'rgba(75, 192, 192, 0.6)',
            'rgba(153, 102, 255, 0.6)',
            'rgba(255, 159, 64, 0.6)',
            'rgba(199, 199, 199, 0.6)'
          ],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }
  
  // Load expenses list
  async function loadExpenses() {
    if (!currentStartDate || !currentEndDate) return;
    
    const start = currentStartDate.toISOString();
    const end = currentEndDate.toISOString();
    
    try {
      const data = await api(`/api/master/expenses?mid=${masterTelegramId}&start_date=${start}&end_date=${end}`);
      
      expensesList.innerHTML = '';
      
      if (!data.expenses || data.expenses.length === 0) {
        expensesList.innerHTML = '<p class="empty-state">Нет расходов за выбранный период</p>';
        return;
      }
      
      data.expenses.forEach(expense => {
        const div = document.createElement('div');
        div.className = 'expense-item';
        
        const date = new Date(expense.expense_date);
        const dateStr = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
        
        const editIcon = '<svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;stroke-width:2;fill:none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
        const deleteIcon = '<svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;stroke-width:2;fill:none"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';
        
        div.innerHTML = `
          <div class="expense-info">
            <div class="expense-category">${getCategoryName(expense.category)}</div>
            <div class="expense-description">${expense.description || '—'}</div>
            <div class="expense-date">${dateStr}</div>
          </div>
          <div class="expense-amount">${formatNumber(expense.amount)} ₽</div>
          <div class="expense-actions">
            <button class="btn-action-icon btn-edit" data-id="${expense.id}">${editIcon}</button>
            <button class="btn-action-icon danger btn-delete" data-id="${expense.id}">${deleteIcon}</button>
          </div>
        `;
        
        expensesList.appendChild(div);
      });
      
      // Add event listeners
      document.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', () => editExpense(parseInt(btn.dataset.id)));
      });
      
      document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', () => deleteExpense(parseInt(btn.dataset.id)));
      });
      
    } catch (e) {
      console.error('Error loading expenses:', e);
    }
  }
  
  // Add expense
  addExpenseBtn.addEventListener('click', () => {
    document.getElementById('expense-id').value = '';
    modalTitle.textContent = 'Новый расход';
    document.getElementById('expense-category').value = 'materials';
    document.getElementById('expense-amount').value = '';
    const today = new Date();
    document.getElementById('expense-date').value = formatDate(today);
    document.getElementById('expense-description').value = '';
    expenseModal.classList.remove('hidden');
  });
  
  // Close modal
  function closeModal() {
    expenseModal.classList.add('hidden');
  }
  
  modalClose.addEventListener('click', closeModal);
  cancelExpenseBtn.addEventListener('click', closeModal);
  
  // Save expense
  saveExpenseBtn.addEventListener('click', async () => {
    const expenseId = document.getElementById('expense-id').value;
    const category = document.getElementById('expense-category').value;
    const amount = parseInt(document.getElementById('expense-amount').value);
    const expenseDateStr = document.getElementById('expense-date').value;
    const description = document.getElementById('expense-description').value;
    
    if (!category || !amount || !expenseDateStr) {
      alert('Заполните все обязательные поля');
      return;
    }

    const expenseDate = parseDate(expenseDateStr);
    if(!expenseDate){
      alert('Неверный формат даты');
      return;
    }
    
    try {
      let url, data;
      
      if (expenseId) {
        // Update existing
        url = '/api/master/expense/update';
        data = {
          mid: masterTelegramId,
          expense_id: parseInt(expenseId),
          category,
          amount,
          expense_date: new Date(expenseDate).toISOString(),
          description
        };
      } else {
        // Create new
        url = '/api/master/expense/create';
        data = {
          mid: masterTelegramId,
          category,
          amount,
          expense_date: new Date(expenseDate).toISOString(),
          description
        };
      }
      
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      const result = await res.json();
      
      if (result.ok || result.expense) {
        closeModal();
        loadFinancialData();
      } else {
        alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
      }
    } catch (e) {
      alert('Ошибка сохранения: ' + e.message);
    }
  });
  
  // Edit expense
  async function editExpense(expenseId) {
    const start = currentStartDate.toISOString();
    const end = currentEndDate.toISOString();
    
    try {
      const data = await api(`/api/master/expenses?mid=${masterTelegramId}&start_date=${start}&end_date=${end}`);
      const expense = data.expenses.find(e => e.id === expenseId);
      
      if (!expense) {
        alert('Расход не найден');
        return;
      }
      
      document.getElementById('expense-id').value = expense.id;
      modalTitle.textContent = 'Редактировать расход';
      document.getElementById('expense-category').value = expense.category;
      document.getElementById('expense-amount').value = expense.amount;
      document.getElementById('expense-date').value = formatDate(new Date(expense.expense_date));
      document.getElementById('expense-description').value = expense.description || '';
      expenseModal.classList.remove('hidden');
    } catch (e) {
      alert('Ошибка загрузки расхода');
    }
  }
  
  // Delete expense
  async function deleteExpense(expenseId) {
    if (!confirm('Удалить этот расход?')) return;
    
    try {
      const res = await fetch('/api/master/expense/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mid: masterTelegramId,
          expense_id: expenseId
        })
      });
      
      const result = await res.json();
      
      if (result.ok) {
        loadFinancialData();
      } else {
        alert('Ошибка удаления: ' + (result.error || ''));
      }
    } catch (e) {
      alert('Ошибка удаления: ' + e.message);
    }
  }

  // Custom Calendar Logic
  function renderCalendar(gridId, titleId, mode) {
    const grid = document.getElementById(gridId);
    const title = document.getElementById(titleId);
    if(!grid || !title) return;

    const year = cal.current.getFullYear();
    const month = cal.current.getMonth();
    title.textContent = new Date(year, month).toLocaleDateString('ru-RU', {month:'long', year:'numeric'});

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month+1, 0).getDate();
    const startDay = firstDay === 0 ? 6 : firstDay - 1;

    grid.innerHTML = '';
    for(let i = 0; i < startDay; i++) grid.appendChild(document.createElement('div'));

    const today = new Date();
    for(let day = 1; day <= daysInMonth; day++){
      const cell = document.createElement('div');
      cell.className = 'day-cell';
      cell.textContent = day;
      const cellDate = new Date(year, month, day);
      
      if(cellDate.toDateString() === today.toDateString()) cell.classList.add('today');
      
      cell.addEventListener('click', () => {
        if(mode === 'period-start'){
          document.getElementById('start-date').value = formatDate(cellDate);
          document.getElementById('period-calendar-section').classList.add('hidden');
        } else if(mode === 'period-end'){
          document.getElementById('end-date').value = formatDate(cellDate);
          document.getElementById('period-calendar-section').classList.add('hidden');
        } else if(mode === 'expense'){
          document.getElementById('expense-date').value = formatDate(cellDate);
          cal.selectedDate = cellDate;
          document.getElementById('expense-calendar-section').classList.add('hidden');
        }
      });
      grid.appendChild(cell);
    }
  }

  function formatDate(date) {
    const d = date.getDate().toString().padStart(2,'0');
    const m = (date.getMonth()+1).toString().padStart(2,'0');
    const y = date.getFullYear();
    return `${d}.${m}.${y}`;
  }

  function parseDate(str) {
    if(!str) return null;
    const parts = str.split('.');
    if(parts.length !== 3) return null;
    return new Date(parts[2], parts[1]-1, parts[0]);
  }

  // Period calendar controls
  document.getElementById('start-date').addEventListener('click', () => {
    cal.mode = 'period-start';
    cal.current = new Date();
    renderCalendar('period-calendar-grid', 'period-cal-title', 'period-start');
    document.getElementById('period-calendar-section').classList.remove('hidden');
  });

  document.getElementById('end-date').addEventListener('click', () => {
    cal.mode = 'period-end';
    cal.current = new Date();
    renderCalendar('period-calendar-grid', 'period-cal-title', 'period-end');
    document.getElementById('period-calendar-section').classList.remove('hidden');
  });

  document.getElementById('period-calendar-close').addEventListener('click', () => {
    document.getElementById('period-calendar-section').classList.add('hidden');
  });

  document.getElementById('period-cal-prev').addEventListener('click', () => {
    cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()-1, 1);
    renderCalendar('period-calendar-grid', 'period-cal-title', cal.mode);
  });

  document.getElementById('period-cal-next').addEventListener('click', () => {
    cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()+1, 1);
    renderCalendar('period-calendar-grid', 'period-cal-title', cal.mode);
  });

  // Expense calendar controls
  document.getElementById('expense-date').addEventListener('click', () => {
    cal.mode = 'expense';
    cal.current = new Date();
    renderCalendar('expense-calendar-grid', 'expense-cal-title', 'expense');
    document.getElementById('expense-calendar-section').classList.remove('hidden');
  });

  document.getElementById('expense-calendar-close').addEventListener('click', () => {
    document.getElementById('expense-calendar-section').classList.add('hidden');
  });

  document.getElementById('expense-cal-prev').addEventListener('click', () => {
    cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()-1, 1);
    renderCalendar('expense-calendar-grid', 'expense-cal-title', 'expense');
  });

  document.getElementById('expense-cal-next').addEventListener('click', () => {
    cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()+1, 1);
    renderCalendar('expense-calendar-grid', 'expense-cal-title', 'expense');
  });

  // Update applyPeriodBtn to use new format
  const originalApplyPeriodClick = applyPeriodBtn.onclick;
  applyPeriodBtn.onclick = null;
  applyPeriodBtn.addEventListener('click', () => {
    const startVal = document.getElementById('start-date').value;
    const endVal = document.getElementById('end-date').value;
    if (!startVal || !endVal) {
      alert('Выберите обе даты');
      return;
    }
    currentStartDate = parseDate(startVal);
    currentEndDate = parseDate(endVal);
    if(!currentStartDate || !currentEndDate){
      alert('Неверный формат даты');
      return;
    }
    loadFinancialData();
  });

  // Initialize
  setCurrentPeriod('week');
})();
