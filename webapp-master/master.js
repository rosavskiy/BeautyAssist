(function(){
  const tg = window.Telegram?.WebApp; tg && tg.expand();
  const qs = new URLSearchParams(window.location.search);
  const mid = qs.get('mid') || tg?.initDataUnsafe?.user?.id;
  const status = (msg, err) => console.log(msg || (err||''));

  if (!mid) {
    alert('Ошибка: не удалось определить мастера. Откройте кабинет через команду /menu в боте.');
    document.body.innerHTML = '<div style="padding: 20px; text-align: center;"><h2>❌ Ошибка</h2><p>Откройте кабинет через команду /menu в боте</p></div>';
    return;
  }

  async function api(path){ 
    try {
      const r = await fetch(path); 
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      }
      const text = await r.text();
      if (!text) return {};
      return JSON.parse(text);
    } catch(e) {
      console.error('API error:', e);
      throw e;
    }
  }

  let currentAppointmentId = null;
  let currentCancelAppointmentId = null;
  let currentServicePrice = 0;
  
  // Date navigation state
  let selectedDate = new Date(); // Start with today
  selectedDate.setHours(0, 0, 0, 0);

  // Calendar state
  const cal = {
    current: new Date(),
    onDatePick: null,
    mode: 'reschedule', // or 'dayoff'
    toggledOff: new Set(), // YYYY-MM-DD strings
  };

  async function openCalendar(onPick){
    cal.onDatePick = onPick;
    cal.mode = 'reschedule';
    // Загружаем расписание если ещё не загружено
    if (!window.__master_schedule || !window.__master_schedule._loaded) {
      try {
        const data = await api(`/api/master/appointments?mid=${encodeURIComponent(mid)}`);
        if (data && data.work_schedule) {
          window.__master_schedule = Object.assign({}, data.work_schedule, {_loaded: true});
        }
        if (data && data.referral_code) {
          window.__master_referral_code = data.referral_code;
        }
      } catch (e) {
        console.error('Failed to load schedule for calendar:', e);
      }
    }
    document.getElementById('calendar-section').classList.remove('hidden');
    renderCalendar();
  }
  function openCalendarDayOffMode(){
    if (!mid) {
      alert('Ошибка: ID мастера не определен');
      return;
    }
    try {
      document.getElementById('settings-section').classList.add('hidden');
      cal.onDatePick = null;
      cal.mode = 'dayoff';
      // Всегда загружаем актуальный график перед открытием режима дней офф
      api(`/api/master/appointments?mid=${encodeURIComponent(mid)}`).then(data => {
        if(data && data.work_schedule){ window.__master_schedule = Object.assign({}, data.work_schedule, {_loaded:true}); }
        cal.toggledOff = new Set((window.__master_schedule?.days_off_dates) || []);
        document.getElementById('slots-list').innerHTML = '';
        document.getElementById('calendar-section').classList.remove('hidden');
        renderCalendar();
        const slotsEl = document.getElementById('slots-list');
        const help = document.createElement('div'); help.className='muted'; help.textContent='Нажимайте на дни, чтобы отметить как нерабочие'; slotsEl.appendChild(help);
        const actions = document.createElement('div'); actions.className='slots-actions';
        const save = document.createElement('button'); save.className='nav-btn'; save.textContent='Сохранить';
        save.addEventListener('click', saveDayOffDates);
        actions.appendChild(save);
        slotsEl.appendChild(actions);
      }).catch(err => {
        alert('Ошибка загрузки данных: ' + err.message);
      });
    } catch(err) {
      alert('Ошибка открытия календаря: ' + err.message);
    }
    return;
  }
  function closeCalendar(){
    document.getElementById('calendar-section').classList.add('hidden');
    document.getElementById('slots-list').innerHTML = '';
    cal.onDatePick = null;
    cal.mode = 'reschedule';
  }
  function renderCalendar(){
    const cur = cal.current;
    const year = cur.getFullYear();
    const month = cur.getMonth();
    const title = new Date(year, month, 1).toLocaleDateString('ru-RU', {month:'long', year:'numeric'});
    document.getElementById('cal-title').textContent = title.charAt(0).toUpperCase()+title.slice(1);
    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';
    const firstDay = new Date(year, month, 1);
    const startWeekday = (firstDay.getDay()+6)%7; // make Monday=0
    const daysInMonth = new Date(year, month+1, 0).getDate();
    for(let i=0;i<startWeekday;i++){
      const filler = document.createElement('div'); filler.className='day-cell disabled'; filler.textContent=''; grid.appendChild(filler);
    }
    const pad = n => (n<10? '0'+n : ''+n);
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
    for(let d=1; d<=daysInMonth; d++){
      const cell = document.createElement('div'); cell.className='day-cell';
      const date = new Date(year, month, d);
      const dateStr = `${year}-${pad(month+1)}-${pad(d)}`;
      cell.textContent = d;
      if(dateStr === todayStr) cell.classList.add('today');
      // Highlight non-working days (based on master work_schedule if loaded)
      const weekdayIndex = (date.getDay()+6)%7; // 0..6 Mon..Sun
      const weekdayKey = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][weekdayIndex];
      const schedule = window.__master_schedule || null;
      // If schedule not yet loaded, do NOT mark as off by default
      let isWeekdayOff = false;
      if(schedule && Array.isArray(schedule[weekdayKey])){
        isWeekdayOff = schedule[weekdayKey].length === 0;
      }
      const isDateOff = cal.toggledOff.has(dateStr);
      if(isWeekdayOff || isDateOff){ cell.classList.add('off'); }
      cell.addEventListener('click', () => {
        if(cal.mode === 'reschedule'){
          // Disable clicks on non-working dates in reschedule mode
          if(cell.classList.contains('off')){ try{ alert('День отмечен как нерабочий'); }catch{} return; }
          if(typeof cal.onDatePick === 'function') cal.onDatePick(dateStr);
        } else {
          // Toggle per-date dayoff in dayoff mode
          if(cal.toggledOff.has(dateStr)){ cal.toggledOff.delete(dateStr); cell.classList.remove('off'); }
          else { cal.toggledOff.add(dateStr); cell.classList.add('off'); }
        }
      });
      grid.appendChild(cell);
    }
  }

  document.addEventListener('click', (ev) => {
    // Используем closest() для поддержки кликов по иконкам внутри кнопок
    const target = ev.target.closest('[id]');
    if (!target) return;
    const id = target.id;
    
    if(id === 'calendar-close') closeCalendar();
    if(id === 'cal-prev'){ cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()-1, 1); renderCalendar(); }
    if(id === 'cal-next'){ cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()+1, 1); renderCalendar(); }
    if(id === 'open-settings') document.getElementById('settings-section').classList.remove('hidden');
    if(id === 'settings-close') document.getElementById('settings-section').classList.add('hidden');
    if(id === 'open-clients'){ 
      const url = `/webapp/master/clients.html?mid=${encodeURIComponent(mid)}`;
      window.location.href = url;
    }
    if(id === 'open-services'){ 
      const url = `/webapp/master/services.html?mid=${encodeURIComponent(mid)}`;
      window.location.href = url;
    }
    if(id === 'open-finances'){ 
      const url = `/webapp-master/finances.html?mid=${encodeURIComponent(mid)}`;
      window.location.href = url;
    }
    if(id === 'add-service-btn') openServiceEdit(null);
    if(id === 'service-edit-close') document.getElementById('service-edit-section').classList.add('hidden');
    if(id === 'service-save') saveService();
    if(id === 'service-delete') deleteService();
    if(id === 'daysoff-close') document.getElementById('daysoff-section').classList.add('hidden');
    if(id === 'daysoff-save') saveDaysOff();
    if(id === 'open-dayoff-calendar') openCalendarDayOffMode();
    if(id === 'open-hours') openHoursModal();
    if(id === 'hours-close') document.getElementById('hours-section').classList.add('hidden');
    if(id === 'hours-save') saveHours();
    if(id === 'complete-confirm-close') document.getElementById('complete-confirm-section').classList.add('hidden');
    if(id === 'complete-no') handleCompleteNo();
    if(id === 'complete-yes') handleCompleteYes();
    if(id === 'complete-payment-close') document.getElementById('complete-payment-section').classList.add('hidden');
    if(id === 'complete-save') handleCompleteSave();
    
    // Date navigation
    if(id === 'date-prev') changeDate(-1);
    if(id === 'date-today') changeDate('today');
    if(id === 'date-next') changeDate(1);
    if(id === 'date-calendar') openDatePickerCalendar();
    
    // Book client modal (handled by separate event listeners)
    if(id === 'open-book-client') { /* handled separately */ }
  });

  function changeDate(direction) {
    if (direction === 'today') {
      selectedDate = new Date();
      selectedDate.setHours(0, 0, 0, 0);
    } else {
      selectedDate.setDate(selectedDate.getDate() + direction);
    }
    loadAppointments();
  }

  function openDatePickerCalendar() {
    openCalendar((dateStr) => {
      const [year, month, day] = dateStr.split('-').map(Number);
      selectedDate = new Date(year, month - 1, day);
      selectedDate.setHours(0, 0, 0, 0);
      closeCalendar();
      loadAppointments();
    });
  }

  function formatDateTitle(date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const dateStr = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    
    if (date.getTime() === today.getTime()) {
      return `Записи на сегодня, ${dateStr}`;
    } else if (date.getTime() === tomorrow.getTime()) {
      return `Записи на завтра, ${dateStr}`;
    } else if (date.getTime() === yesterday.getTime()) {
      return `Записи на вчера, ${dateStr}`;
    } else {
      return `Записи на ${dateStr}`;
    }
  }

  async function loadAppointments(){
    try {
      // Format date as YYYY-MM-DD in LOCAL date (not influenced by time)
      // This ensures the date sent to server matches what user sees
      const year = selectedDate.getFullYear();
      const month = String(selectedDate.getMonth() + 1).padStart(2, '0');
      const day = String(selectedDate.getDate()).padStart(2, '0');
      const dateStr = `${year}-${month}-${day}`;
      
      const data = await api(`/api/master/appointments?mid=${encodeURIComponent(mid)}&date=${dateStr}`);
    
    // Update title
    const titleEl = document.getElementById('appointments-title');
    const count = data?.appointments?.length || 0;
    titleEl.textContent = `${formatDateTitle(selectedDate)} (${count})`;
    
    const el = document.getElementById('appointments');
    el.innerHTML = '';
    // Store schedule for calendar highlighting (с флагом _loaded)
    if(data && data.work_schedule){ window.__master_schedule = Object.assign({}, data.work_schedule, {_loaded: true}); }
    if(data && data.referral_code){ window.__master_referral_code = data.referral_code; }
    if(data && Array.isArray(data.appointments)){
      const apps = data.appointments;
      if(!apps.length){ el.textContent = 'На сегодня записей нет'; return; }
      apps.forEach(a => {
        const card = document.createElement('div'); 
        card.className='card';
        const when = new Date(a.start).toLocaleString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        
        // Translate status
        let statusText = a.status;
        if(a.status === 'scheduled') statusText = 'Запланирована';
        else if(a.status === 'confirmed') statusText = 'Подтверждена';
        else if(a.status === 'cancelled') statusText = '❌ Отменена';
        else if(a.status === 'completed') statusText = '✅ Завершена';
        else if(a.status === 'no_show') statusText = '⚠️ Не явился';
        
        // Visual styling for completed/cancelled appointments
        if(a.is_completed) {
          card.style.opacity = '0.6';
          card.style.background = 'linear-gradient(to right, #f0fdf4, #ffffff)';
        }
        if(a.status === 'cancelled') {
          card.style.opacity = '0.6';
          card.style.background = 'linear-gradient(to right, #fef2f2, #ffffff)';
        }
        
        // Build client info with links
        let clientLink = '';
        if(a.client.username) {
          clientLink = ` <a href="https://t.me/${a.client.username}" target="_blank">@${a.client.username}</a>`;
        } else if(a.client.telegram_id) {
          clientLink = ` <a href="tg://user?id=${a.client.telegram_id}">ID:${a.client.telegram_id}</a>`;
        }
        
        // Строка 1: Время, услуга, статус
        const line1 = document.createElement('div');
        line1.style.cssText = 'font-weight: 600; font-size: 15px; margin-bottom: 6px; width: 100%; white-space: normal;';
        line1.innerHTML = `${when} — ${a.service} <span style="color: #7C88A0; font-weight: 400; font-size: 13px;">(${statusText})</span>`;
        card.appendChild(line1);
        
        // Строка 2: Имя и ссылка
        const line2 = document.createElement('div');
        line2.style.cssText = 'font-size: 14px; margin-bottom: 4px; width: 100%; white-space: normal;';
        line2.innerHTML = `${a.client.name}${clientLink}`;
        card.appendChild(line2);
        
        // Строка 3: Телефон
        const line3 = document.createElement('div');
        line3.style.cssText = 'color: #7C88A0; font-size: 13px; margin-bottom: 12px; width: 100%; white-space: normal;';
        line3.textContent = a.client.phone;
        card.appendChild(line3);
        
        // Show action buttons only if not completed and not cancelled
        if(!a.is_completed && a.status !== 'cancelled'){
          const btnRow = document.createElement('div');
          btnRow.style.cssText = 'display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid #E8ECF1; flex-wrap: wrap;';
          btnRow.innerHTML = `
            <button data-id="${a.id}" class="action-btn btn-cancel">Отменить</button>
            <button data-id="${a.id}" data-start="${a.start}" data-service="${a.service_id}" class="action-btn btn-reschedule">Перенести</button>
            ${a.is_past ? `<button data-id="${a.id}" data-price="${a.service_price}" class="action-btn btn-complete">Завершить</button>` : ''}`;
          card.appendChild(btnRow);
        }
        
        el.appendChild(card);
      });
      
      // Use global currentCancelAppointmentId variable (declared at top of file)
      
      el.querySelectorAll('.btn-cancel').forEach(btn => btn.addEventListener('click', async (ev) => {
        currentCancelAppointmentId = ev.target.getAttribute('data-id');
        document.getElementById('cancel-reason-section').classList.remove('hidden');
        document.getElementById('cancel-reason-input').value = '';
        document.getElementById('cancel-reason-input').focus();
      }));
      el.querySelectorAll('.btn-reschedule').forEach(btn => btn.addEventListener('click', async (ev) => {
        const id = ev.target.getAttribute('data-id');
        const serviceId = ev.target.getAttribute('data-service');
        const dataLocal = data; // capture for closure
        openRescheduleCalendar(id, serviceId, dataLocal);
      }));
      
      el.querySelectorAll('.btn-complete').forEach(btn => btn.addEventListener('click', (ev) => {
        currentAppointmentId = Number(ev.target.getAttribute('data-id'));
        currentServicePrice = Number(ev.target.getAttribute('data-price'));
        document.getElementById('complete-confirm-section').classList.remove('hidden');
      }));
      // Settings button moved to header; keep list clean
    } else { el.textContent = 'Ошибка загрузки'; }
    } catch(e) {
      console.error('Error loading appointments:', e);
      const el = document.getElementById('appointments');
      el.innerHTML = `<div style="color: #e74c3c; padding: 20px; text-align: center;">
        ❌ Ошибка: ${e.message || 'Не удалось загрузить записи'}<br>
        <button onclick="location.reload()" style="margin-top: 10px; padding: 8px 16px; background: #9B7EBD; color: white; border: none; border-radius: 8px; cursor: pointer;">Обновить страницу</button>
      </div>`;
    }
  }
    
  // Separate reschedule calendar to avoid conflicts with dayoff calendar
  function openRescheduleCalendar(appointmentId, serviceId, masterData){
      document.getElementById('reschedule-section').classList.remove('hidden');
      const rescheduleModal = { current: new Date() };
      renderRescheduleModalCalendar();
      
      async function renderRescheduleModalCalendar(){
        const cur = rescheduleModal.current;
        const year = cur.getFullYear();
        const month = cur.getMonth();
        const title = new Date(year, month, 1).toLocaleDateString('ru-RU', {month:'long', year:'numeric'});
        document.getElementById('reschedule-cal-title').textContent = title.charAt(0).toUpperCase()+title.slice(1);
        const grid = document.getElementById('reschedule-calendar-grid');
        grid.innerHTML = '';
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const startDay = firstDay.getDay() || 7;
        const daysInMonth = lastDay.getDate();
        const today = new Date(); today.setHours(0,0,0,0);
        
        for(let i = 1; i < startDay; i++){ grid.appendChild(document.createElement('div')); }
        
        for(let day = 1; day <= daysInMonth; day++){
          const cell = document.createElement('div');
          cell.className = 'day-cell';
          cell.textContent = day;
          const cellDate = new Date(year, month, day);
          cellDate.setHours(0,0,0,0);
          if(cellDate < today){ cell.classList.add('disabled'); }
          else {
            cell.addEventListener('click', async () => {
              const dateStr = year + '-' + String(month+1).padStart(2,'0') + '-' + String(day).padStart(2,'0');
              await loadRescheduleSlots(dateStr);
            });
          }
          if(cellDate.getTime() === today.getTime()){ cell.classList.add('today'); }
          grid.appendChild(cell);
        }
      }
      
      async function loadRescheduleSlots(dateStr){
        try {
          const rc = masterData.referral_code;
          const slots = await api(`/api/slots?code=${encodeURIComponent(rc)}&service=${encodeURIComponent(serviceId)}&date=${encodeURIComponent(dateStr)}`);
          const slotsEl = document.getElementById('reschedule-slots-list');
          slotsEl.innerHTML = '';
          if(!Array.isArray(slots) || !slots.length){
            const p = document.createElement('div'); p.className='muted'; p.textContent='Нет свободных слотов'; slotsEl.appendChild(p); return;
          }
          slots.forEach(s => {
            const btn = document.createElement('button'); btn.className='slot-btn';
            const label = new Date(s.start).toLocaleTimeString('ru-RU',{hour:'2-digit', minute:'2-digit'});
            btn.textContent = label;
            if(!s.available){ btn.classList.add('unavailable'); btn.disabled = true; }
            btn.addEventListener('click', async () => {
              const res = await fetch('/api/master/appointment/reschedule', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ mid, appointment_id: Number(appointmentId), new_start: s.start })
              });
              const json = await res.json();
              if(json && json.ok){ 
                document.getElementById('reschedule-section').classList.add('hidden');
                showSuccessTick();
                loadAppointments(); 
              }
              else alert('Ошибка переноса: ' + (json?.error || ''));
            });
            slotsEl.appendChild(btn);
          });
        } catch(e){ alert('Ошибка загрузки слотов'); }
      }
      
      document.getElementById('reschedule-close').onclick = () => {
        document.getElementById('reschedule-section').classList.add('hidden');
      };
      document.getElementById('reschedule-prev').onclick = () => {
        rescheduleModal.current.setMonth(rescheduleModal.current.getMonth() - 1);
        renderRescheduleModalCalendar();
      };
      document.getElementById('reschedule-next').onclick = () => {
        rescheduleModal.current.setMonth(rescheduleModal.current.getMonth() + 1);
        renderRescheduleModalCalendar();
      };
  }
  
  function openHoursModal(){
    document.getElementById('settings-section').classList.add('hidden');
    const modal = document.getElementById('hours-section');
    const ws = window.__master_schedule || {};
    modal.classList.remove('hidden');
    modal.querySelectorAll('input[data-day]').forEach(inp => {
      const day = inp.getAttribute('data-day');
      const ivs = ws[day];
      if(Array.isArray(ivs) && ivs.length){ inp.value = ivs.map(iv => `${iv[0]}-${iv[1]}`).join(', '); } else { inp.value = ''; }
    });
  }

  async function saveHours(){
    const modal = document.getElementById('hours-section');
    const obj = {};
    modal.querySelectorAll('input[data-day]').forEach(inp => {
      const day = inp.getAttribute('data-day');
      const val = (inp.value || '').trim();
      if(val){
        const parts = val.split(',').map(s => s.trim());
        const ivs = [];
        parts.forEach(p => {
          const [a,b] = p.split('-').map(x => (x||'').trim());
          if(a && b) ivs.push([a,b]);
        });
        obj[day] = ivs;
      } else { obj[day] = []; }
    });
    try{
      const resp = await fetch('/api/master/schedule/hours', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mid, hours: obj }) });
      const js = await resp.json();
      if(js && js.ok){ window.__master_schedule = js.work_schedule || {}; document.getElementById('hours-section').classList.add('hidden'); renderCalendar(); showSuccessTick(); }
      else alert('Не удалось сохранить: ' + (js?.error || ''));
    }catch(e){ alert('Ошибка запроса'); }
  }

  async function saveDaysOff(){
    const modal = document.getElementById('daysoff-section');
    const checked = Array.from(modal.querySelectorAll('input[type="checkbox"]')).filter(ch => ch.checked).map(ch => ch.value);
    try {
      const resp = await fetch('/api/master/schedule/days_off', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mid, days_off: checked, days_off_dates: Array.from(cal.toggledOff) }) });
      const js = await resp.json();
      if(js && js.ok){
        // После сохранения перечитываем график с сервера для консистенции
        const fresh = await api(`/api/master/schedule?mid=${encodeURIComponent(mid)}`);
        const ws = (fresh && fresh.work_schedule) || (js.work_schedule || {});
        window.__master_schedule = Object.assign({}, ws, {_loaded:true});
        window.__master_schedule.days_off_dates = ws.days_off_dates || [];
        document.getElementById('daysoff-section').classList.add('hidden');
        renderCalendar();
      }
      else alert('Не удалось сохранить: ' + (js?.error || ''));
    } catch(e){ alert('Ошибка запроса'); }
  }

  async function saveDayOffDates(){
    try {
      const resp = await fetch('/api/master/schedule/days_off', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mid, days_off: (window.__master_schedule?.days_off)||[], days_off_dates: Array.from(cal.toggledOff) }) });
      const js = await resp.json();
      if(js && js.ok){
        const fresh = await api(`/api/master/schedule?mid=${encodeURIComponent(mid)}`);
        const ws = (fresh && fresh.work_schedule) || (js.work_schedule || {});
        window.__master_schedule = Object.assign({}, ws, {_loaded:true});
        window.__master_schedule.days_off_dates = ws.days_off_dates || [];
        showSuccessTick();
        closeCalendar();
        renderCalendar();
      }
      else alert('Не удалось сохранить: ' + (js?.error || ''));
    } catch(e){ alert('Ошибка запроса'); }
  }

  function showSuccessTick(){
    const ov = document.createElement('div'); ov.className='success-overlay';
    const tick = document.createElement('div'); tick.className='success-tick success-anim';
    tick.innerHTML = '<svg viewBox="0 0 64 64"><path d="M16 34 L28 46 L48 22"/></svg>';
    ov.appendChild(tick);
    document.body.appendChild(ov);
    setTimeout(()=>{ try{ document.body.removeChild(ov); }catch{} }, 900);
  }

  async function handleCompleteNo(){
    document.getElementById('complete-confirm-section').classList.add('hidden');
    try {
      const res = await fetch('/api/master/appointment/complete', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ mid, appointment_id: currentAppointmentId, client_came: false })
      });
      const json = await res.json();
      if(json && json.ok){ 
        showSuccessTick();
        loadAppointments(); 
      } else { 
        alert('Ошибка: ' + (json?.error || '')); 
      }
    } catch(e){ console.error(e); alert('Ошибка: ' + e.message); }
  }

  async function handleCompleteYes(){
    document.getElementById('complete-confirm-section').classList.add('hidden');
    document.getElementById('payment-amount').value = currentServicePrice;
    document.getElementById('complete-payment-section').classList.remove('hidden');
  }

  async function handleCompleteSave(){
    const amount = Number(document.getElementById('payment-amount').value) || 0;
    document.getElementById('complete-payment-section').classList.add('hidden');
    try {
      const res = await fetch('/api/master/appointment/complete', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ mid, appointment_id: currentAppointmentId, client_came: true, payment_amount: amount })
      });
      const json = await res.json();
      if(json && json.ok){ 
        showSuccessTick();
        loadAppointments(); 
      } else { 
        alert('Ошибка: ' + (json?.error || '')); 
      }
    } catch(e){ console.error(e); alert('Ошибка: ' + e.message); }
  }

  async function loadClients(){
    const data = await api(`/api/master/clients?mid=${encodeURIComponent(mid)}`);
    const el = document.getElementById('clients');
    el.innerHTML='';
    if(Array.isArray(data)){
      if(!data.length){ el.textContent = 'Клиентов пока нет'; return; }
      data.forEach(c => {
        const card = document.createElement('div'); card.className='card';
        card.style.cursor = 'pointer';
        card.innerHTML = `<div class="row"><div>${c.name}${c.username? ' @'+c.username:''}</div><div>${c.phone}</div></div>
          <div class="muted">Визитов: ${c.total_visits} • Потрачено: ${c.total_spent} ₽</div>`;
        card.addEventListener('click', () => openClientHistory(c.id));
        el.appendChild(card);
      });
    } else { el.textContent='Ошибка загрузки'; }
  }

  async function openClientHistory(clientId){
    try {
      const data = await api(`/api/master/client/history?mid=${encodeURIComponent(mid)}&client_id=${clientId}`);
      if(!data || !data.client){ alert('Не удалось загрузить историю'); return; }
      
      const client = data.client;
      const appointments = data.appointments || [];
      
      // Update modal title
      document.getElementById('client-history-title').textContent = `История: ${client.name}`;
      
      // Show client info
      const infoEl = document.getElementById('client-history-info');
      infoEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
          <div style="font-weight:600">${client.name}</div>
          <div style="color:#666">${client.phone}</div>
        </div>
        <div class="muted">Всего визитов: ${client.total_visits} • Потрачено: ${client.total_spent} ₽</div>
      `;
      
      // Show appointments list
      const listEl = document.getElementById('client-history-list');
      listEl.innerHTML = '';
      
      if(appointments.length === 0){
        listEl.innerHTML = '<div class="muted" style="text-align:center; padding:20px">История посещений пуста</div>';
      } else {
        appointments.forEach(appt => {
          const card = document.createElement('div');
          card.className = 'card';
          
          // Format date
          const dt = new Date(appt.start_time);
          const dateStr = dt.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric'});
          const timeStr = dt.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
          
          // Status badge
          let statusBadge = '';
          let statusColor = '#D0D4DC';
          if(appt.is_completed){
            statusBadge = 'Завершена';
            statusColor = '#4CAF50';
          } else if(appt.status === 'cancelled'){
            statusBadge = 'Отменена';
            statusColor = '#F44336';
          } else if(appt.status === 'confirmed'){
            statusBadge = 'Подтверждена';
            statusColor = '#2196F3';
          } else {
            statusBadge = 'Запланирована';
            statusColor = '#9E9E9E';
          }
          
          // Amount
          const amount = appt.payment_amount || appt.service_price || 0;
          
          card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:8px">
              <div>
                <div style="font-weight:600; margin-bottom:4px">${appt.service_name}</div>
                <div class="muted">${dateStr} в ${timeStr}</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:11px; padding:4px 8px; border-radius:8px; background:${statusColor}; color:white; margin-bottom:4px">${statusBadge}</div>
                <div style="font-weight:600">${amount} ₽</div>
              </div>
            </div>
          `;
          
          listEl.appendChild(card);
        });
      }
      
      // Open modal
      document.getElementById('client-history-section').classList.remove('hidden');
    } catch(e){
      console.error(e);
      alert('Ошибка загрузки истории: ' + e.message);
    }
  }

  let currentServiceId = null;
  window.openServiceEdit = openServiceEdit;
  async function loadServices(){
    const data = await api(`/api/master/services?mid=${encodeURIComponent(mid)}`);
    const el = document.getElementById('services-list');
    el.innerHTML='';
    if(Array.isArray(data)){
      if(!data.length){ el.innerHTML = '<div class="muted">Услуг пока нет. Добавьте первую!</div>'; return; }
      data.forEach(s => {
        const card = document.createElement('div'); card.className='card';
        card.innerHTML = `<div class="row" style="justify-content:space-between"><div style="font-weight:600">${s.name}</div><button class="icon-btn" data-id="${s.id}" onclick="openServiceEdit(${s.id})">✏️</button></div>
          <div class="muted">${s.price} ₽ • ${s.duration} мин</div>`;
        el.appendChild(card);
      });
    } else { el.textContent='Ошибка загрузки'; }
  }

  function openServiceEdit(serviceId){
    currentServiceId = serviceId;
    document.getElementById('services-section').classList.add('hidden');
    const modal = document.getElementById('service-edit-section');
    const title = document.getElementById('service-edit-title');
    const deleteBtn = document.getElementById('service-delete');
    if(serviceId){
      title.textContent = 'Редактировать услугу';
      deleteBtn.style.display = 'block';
      api(`/api/master/services?mid=${encodeURIComponent(mid)}`).then(data => {
        if(Array.isArray(data)){
          const svc = data.find(s => s.id === serviceId);
          if(svc){
            document.getElementById('service-name').value = svc.name;
            document.getElementById('service-price').value = svc.price;
            document.getElementById('service-duration').value = svc.duration;
          }
        }
      });
    } else {
      title.textContent = 'Новая услуга';
      deleteBtn.style.display = 'none';
      document.getElementById('service-name').value = '';
      document.getElementById('service-price').value = '';
      document.getElementById('service-duration').value = '';
    }
    modal.classList.remove('hidden');
  }

  async function saveService(){
    const name = document.getElementById('service-name').value.trim();
    const price = Number(document.getElementById('service-price').value) || 0;
    const duration = Number(document.getElementById('service-duration').value) || 0;
    
    // Validation
    if(!name){ alert('Укажите название услуги'); return; }
    if(name.length > 100){ alert('Название услуги не должно превышать 100 символов'); return; }
    if(price <= 0 || price > 50000){ alert('Цена должна быть от 1 до 50 000 ₽'); return; }
    if(duration <= 0){ alert('Длительность должна быть больше 0 минут'); return; }
    if(duration % 30 !== 0){ alert('Длительность должна быть кратна 30 минутам (например, 30, 60, 90, 120)'); return; }
    
    try{
      const resp = await fetch('/api/master/service/save', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ mid, service_id: currentServiceId, name, price, duration })
      });
      const js = await resp.json();
      if(js && js.ok){
        document.getElementById('service-edit-section').classList.add('hidden');
        showSuccessTick();
        loadServices();
        document.getElementById('services-section').classList.remove('hidden');
      } else { alert('Ошибка сохранения: ' + (js?.error || '')); }
    } catch(e){ alert('Ошибка запроса'); }
  }

  async function deleteService(){
    if(!currentServiceId) return;
    if(!confirm('Удалить услугу?')) return;
    try{
      const resp = await fetch('/api/master/service/delete', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ mid, service_id: currentServiceId })
      });
      const js = await resp.json();
      if(js && js.ok){
        document.getElementById('service-edit-section').classList.add('hidden');
        showSuccessTick();
        loadServices();
        document.getElementById('services-section').classList.remove('hidden');
      } else { alert('Ошибка удаления: ' + (js?.error || '')); }
    } catch(e){ alert('Ошибка запроса'); }
  }

  // Cancel reason modal handlers
  document.getElementById('cancel-reason-close').addEventListener('click', () => {
    document.getElementById('cancel-reason-section').classList.add('hidden');
    currentCancelAppointmentId = null;
  });

  document.getElementById('cancel-reason-skip').addEventListener('click', () => {
    document.getElementById('cancel-reason-section').classList.add('hidden');
    currentCancelAppointmentId = null;
  });

  document.getElementById('cancel-reason-confirm').addEventListener('click', async () => {
    console.log('Cancel button clicked!');
    if (!currentCancelAppointmentId) {
      console.log('No appointment ID');
      return;
    }
    
    const reason = document.getElementById('cancel-reason-input').value.trim();
    console.log('Cancelling appointment:', currentCancelAppointmentId, 'reason:', reason);
    
    try {
      const res = await fetch('/api/master/appointment/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          mid, 
          appointment_id: Number(currentCancelAppointmentId), 
          reason 
        })
      });
      
      console.log('Response status:', res.status);
      
      if (!res.ok) {
        const json = await res.json();
        console.error('Server error:', json);
        alert('Ошибка отмены: ' + (json?.error || 'Неизвестная ошибка'));
        return;
      }
      
      const json = await res.json();
      console.log('Response data:', json);
      
      if (json && json.ok) {
        document.getElementById('cancel-reason-section').classList.add('hidden');
        currentCancelAppointmentId = null;
        showSuccessTick();
        loadAppointments();
      } else {
        alert('Ошибка отмены: ' + (json?.error || 'Неизвестная ошибка'));
      }
    } catch (e) {
      console.error('Fetch error:', e);
      alert('Ошибка запроса: ' + e.message);
    }
  });

  // ========== OFFLINE CLIENT BOOKING ==========
  
  const bookClient = {
    services: [],
    selectedDate: null,
    selectedTime: null,
    selectedServiceId: null,
    clientId: null,
    calCurrent: new Date()
  };

  // Open book client modal
  document.getElementById('open-book-client')?.addEventListener('click', async () => {
    // Reset state
    bookClient.selectedDate = null;
    bookClient.selectedTime = null;
    bookClient.selectedServiceId = null;
    bookClient.clientId = null;
    document.getElementById('book-client-phone').value = '';
    document.getElementById('book-client-name').value = '';
    document.getElementById('book-client-comment').value = '';
    document.getElementById('book-client-date-btn').textContent = 'Выберите дату';
    document.getElementById('book-client-slots').innerHTML = '<p class="muted">Сначала выберите дату</p>';
    
    // Load services
    try {
      const data = await api(`/api/master/services?mid=${encodeURIComponent(mid)}`);
      // API returns array directly, not {services: [...]}
      const servicesArr = Array.isArray(data) ? data : (data.services || []);
      bookClient.services = servicesArr.filter(s => s.is_active);
      
      const select = document.getElementById('book-client-service');
      select.innerHTML = '<option value="">— Выберите услугу —</option>';
      bookClient.services.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        // API returns duration_minutes, not duration
        const dur = s.duration_minutes || s.duration || 0;
        opt.textContent = `${s.name} (${dur} мин, ${s.price}₽)`;
        select.appendChild(opt);
      });
    } catch (e) {
      console.error('Failed to load services:', e);
    }
    
    document.getElementById('book-client-section').classList.remove('hidden');
    // Re-init feather icons for new modal
    if (typeof feather !== 'undefined') feather.replace({ 'stroke-width': 2.5 });
  });

  // Close book client modal
  document.getElementById('book-client-close')?.addEventListener('click', () => {
    document.getElementById('book-client-section').classList.add('hidden');
  });

  // Service change - update price display
  document.getElementById('book-client-service')?.addEventListener('change', (e) => {
    bookClient.selectedServiceId = e.target.value ? parseInt(e.target.value) : null;
    // Reload slots if date already selected
    if (bookClient.selectedDate && bookClient.selectedServiceId) {
      loadBookingSlots();
    }
  });

  // Open calendar for booking
  document.getElementById('book-client-date-btn')?.addEventListener('click', () => {
    bookClient.calCurrent = new Date();
    document.getElementById('book-client-calendar-section').classList.remove('hidden');
    renderBookingCalendar();
    if (typeof feather !== 'undefined') feather.replace({ 'stroke-width': 2.5 });
  });

  // Calendar navigation
  document.getElementById('book-cal-prev')?.addEventListener('click', () => {
    bookClient.calCurrent = new Date(bookClient.calCurrent.getFullYear(), bookClient.calCurrent.getMonth() - 1, 1);
    renderBookingCalendar();
  });
  document.getElementById('book-cal-next')?.addEventListener('click', () => {
    bookClient.calCurrent = new Date(bookClient.calCurrent.getFullYear(), bookClient.calCurrent.getMonth() + 1, 1);
    renderBookingCalendar();
  });
  document.getElementById('book-client-calendar-close')?.addEventListener('click', () => {
    document.getElementById('book-client-calendar-section').classList.add('hidden');
  });

  function renderBookingCalendar() {
    const grid = document.getElementById('book-client-calendar-grid');
    if (!grid) return;
    grid.innerHTML = '';
    
    const y = bookClient.calCurrent.getFullYear();
    const m = bookClient.calCurrent.getMonth();
    const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
    document.getElementById('book-cal-title').textContent = `${monthNames[m]} ${y}`;
    
    const firstDay = new Date(y, m, 1);
    let startWeekday = firstDay.getDay();
    if (startWeekday === 0) startWeekday = 7;
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const today = new Date(); today.setHours(0,0,0,0);
    
    // Work schedule for checking working days
    const ws = window.__master_schedule || {};
    const weekdayNames = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday'];
    const daysOffDates = new Set(ws.days_off_dates || []);
    
    // Empty cells before first day
    for (let i = 1; i < startWeekday; i++) {
      const empty = document.createElement('div');
      empty.className = 'day-cell disabled';
      grid.appendChild(empty);
    }
    
    // Days of month
    for (let d = 1; d <= daysInMonth; d++) {
      const cell = document.createElement('div');
      cell.className = 'day-cell';
      cell.textContent = d;
      
      const cellDate = new Date(y, m, d);
      const dateStr = `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const weekdayName = weekdayNames[cellDate.getDay()];
      
      // Check if it's a working day
      const daySchedule = ws[weekdayName] || [];
      const isWorkingDay = daySchedule.length > 0;
      const isDayOff = daysOffDates.has(dateStr);
      const isPast = cellDate < today;
      
      if (isPast || !isWorkingDay || isDayOff) {
        cell.classList.add('disabled');
      } else {
        cell.addEventListener('click', () => {
          bookClient.selectedDate = dateStr;
          document.getElementById('book-client-date-btn').textContent = formatDateRu(dateStr);
          document.getElementById('book-client-calendar-section').classList.add('hidden');
          if (bookClient.selectedServiceId) {
            loadBookingSlots();
          } else {
            document.getElementById('book-client-slots').innerHTML = '<p class="muted">Выберите услугу</p>';
          }
        });
      }
      
      if (cellDate.getTime() === today.getTime()) {
        cell.classList.add('today');
      }
      
      grid.appendChild(cell);
    }
  }

  function formatDateRu(dateStr) {
    const [y, m, d] = dateStr.split('-');
    const months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
    return `${parseInt(d)} ${months[parseInt(m)-1]}`;
  }

  async function loadBookingSlots() {
    const slotsDiv = document.getElementById('book-client-slots');
    slotsDiv.innerHTML = '<p class="muted">Загрузка...</p>';
    
    try {
      // API uses code (referral_code), service (service_id), date
      const code = window.__master_referral_code;
      if (!code) {
        slotsDiv.innerHTML = '<p class="muted">Код мастера не найден</p>';
        return;
      }
      const data = await api(`/api/slots?code=${encodeURIComponent(code)}&service=${bookClient.selectedServiceId}&date=${bookClient.selectedDate}`);
      // API returns array directly with {start, end, available}
      const slots = Array.isArray(data) ? data : [];
      
      if (slots.length === 0) {
        slotsDiv.innerHTML = '<p class="muted">Нет свободных слотов</p>';
        return;
      }
      
      slotsDiv.innerHTML = '';
      const slotsGrid = document.createElement('div');
      slotsGrid.className = 'slots-grid';
      
      slots.forEach(slot => {
        const btn = document.createElement('button');
        btn.className = 'slot-btn' + (slot.available ? '' : ' unavailable');
        // Format time from ISO string
        const startTime = new Date(slot.start);
        const timeLabel = startTime.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
        btn.textContent = timeLabel;
        btn.disabled = !slot.available;
        if (slot.available) {
          btn.addEventListener('click', () => {
            // Remove active from all
            slotsGrid.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            bookClient.selectedTime = timeLabel; // Store HH:MM for API
            bookClient.selectedStartISO = slot.start; // Store ISO if needed later
          });
        }
        slotsGrid.appendChild(btn);
      });
      slotsDiv.appendChild(slotsGrid);
    } catch (e) {
      console.error('Failed to load slots:', e);
      slotsDiv.innerHTML = '<p class="muted">Ошибка загрузки</p>';
    }
  }

  // Phone input formatting
  document.getElementById('book-client-phone')?.addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '');
    if (val.startsWith('8')) val = '7' + val.slice(1);
    if (val.startsWith('7')) {
      let formatted = '+7';
      if (val.length > 1) formatted += ' (' + val.slice(1, 4);
      if (val.length > 4) formatted += ') ' + val.slice(4, 7);
      if (val.length > 7) formatted += '-' + val.slice(7, 9);
      if (val.length > 9) formatted += '-' + val.slice(9, 11);
      e.target.value = formatted;
    }
  });

  // Save booking
  document.getElementById('book-client-save')?.addEventListener('click', async () => {
    const phone = document.getElementById('book-client-phone').value.trim();
    const name = document.getElementById('book-client-name').value.trim();
    const comment = document.getElementById('book-client-comment').value.trim();
    
    if (!phone || phone.length < 12) {
      alert('Введите номер телефона');
      return;
    }
    if (!name) {
      alert('Введите имя клиента');
      return;
    }
    if (!bookClient.selectedServiceId) {
      alert('Выберите услугу');
      return;
    }
    if (!bookClient.selectedDate) {
      alert('Выберите дату');
      return;
    }
    if (!bookClient.selectedTime) {
      alert('Выберите время');
      return;
    }
    
    try {
      // Step 1: Create or get client
      const clientRes = await fetch('/api/master/client/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mid, phone, name })
      });
      
      if (!clientRes.ok) {
        const err = await clientRes.json();
        alert('Ошибка: ' + (err.error || 'Не удалось создать клиента'));
        return;
      }
      
      const clientData = await clientRes.json();
      const clientId = clientData.client.id;
      
      // Step 2: Create appointment
      const bookRes = await fetch('/api/master/book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mid,
          client_id: clientId,
          service_id: bookClient.selectedServiceId,
          date: bookClient.selectedDate,
          time: bookClient.selectedTime,
          comment
        })
      });
      
      if (!bookRes.ok) {
        const err = await bookRes.json();
        alert('Ошибка: ' + (err.error || 'Не удалось создать запись'));
        return;
      }
      
      const bookData = await bookRes.json();
      
      // Success!
      document.getElementById('book-client-section').classList.add('hidden');
      showSuccessTick();
      loadAppointments();
      
      // Show info
      const isNew = clientData.is_new ? '(новый клиент)' : '';
      console.log(`Записан ${clientData.client.name} ${isNew} на ${bookClient.selectedDate} ${bookClient.selectedTime}`);
      
    } catch (e) {
      console.error('Booking error:', e);
      alert('Ошибка: ' + e.message);
    }
  });

  // ========== END OFFLINE CLIENT BOOKING ==========

  loadAppointments().catch(e => status('appointments error', e));
})();