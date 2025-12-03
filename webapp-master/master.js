(function(){
  const tg = window.Telegram?.WebApp; tg && tg.expand();
  const qs = new URLSearchParams(window.location.search);
  const mid = qs.get('mid');
  const status = (msg, err) => console.log(msg || (err||''));

  async function api(path){ const r = await fetch(path); return r.json(); }

  let currentAppointmentId = null;
  let currentServicePrice = 0;

  // Calendar state
  const cal = {
    current: new Date(),
    onDatePick: null,
    mode: 'reschedule', // or 'dayoff'
    toggledOff: new Set(), // YYYY-MM-DD strings
  };

  function openCalendar(onPick){
    cal.onDatePick = onPick;
    cal.mode = 'reschedule';
    document.getElementById('calendar-section').classList.remove('hidden');
    renderCalendar();
  }
  function openCalendarDayOffMode(){
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
    });
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
    if(ev.target.id === 'calendar-close') closeCalendar();
    if(ev.target.id === 'cal-prev'){ cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()-1, 1); renderCalendar(); }
    if(ev.target.id === 'cal-next'){ cal.current = new Date(cal.current.getFullYear(), cal.current.getMonth()+1, 1); renderCalendar(); }
    if(ev.target.id === 'open-settings') document.getElementById('settings-section').classList.remove('hidden');
    if(ev.target.id === 'settings-close') document.getElementById('settings-section').classList.add('hidden');
    if(ev.target.id === 'open-clients'){ loadClients(); document.getElementById('clients-section').classList.remove('hidden'); }
    if(ev.target.id === 'clients-close') document.getElementById('clients-section').classList.add('hidden');
    if(ev.target.id === 'open-services'){ loadServices(); document.getElementById('settings-section').classList.add('hidden'); document.getElementById('services-section').classList.remove('hidden'); }
    if(ev.target.id === 'services-close') document.getElementById('services-section').classList.add('hidden');
    if(ev.target.id === 'add-service-btn') openServiceEdit(null);
    if(ev.target.id === 'service-edit-close') document.getElementById('service-edit-section').classList.add('hidden');
    if(ev.target.id === 'service-save') saveService();
    if(ev.target.id === 'service-delete') deleteService();
    if(ev.target.id === 'daysoff-close') document.getElementById('daysoff-section').classList.add('hidden');
    if(ev.target.id === 'daysoff-save') saveDaysOff();
    if(ev.target.id === 'open-dayoff-calendar') openCalendarDayOffMode();
    if(ev.target.id === 'open-hours') openHoursModal();
    if(ev.target.id === 'hours-close') document.getElementById('hours-section').classList.add('hidden');
    if(ev.target.id === 'hours-save') saveHours();
    if(ev.target.id === 'complete-confirm-close') document.getElementById('complete-confirm-section').classList.add('hidden');
    if(ev.target.id === 'complete-no') handleCompleteNo();
    if(ev.target.id === 'complete-yes') handleCompleteYes();
    if(ev.target.id === 'complete-payment-close') document.getElementById('complete-payment-section').classList.add('hidden');
    if(ev.target.id === 'complete-save') handleCompleteSave();
  });

  async function loadAppointments(){
    const data = await api(`/api/master/appointments?mid=${encodeURIComponent(mid)}`);
    const el = document.getElementById('appointments');
    el.innerHTML = '';
    // Store schedule for calendar highlighting
    if(data && data.work_schedule){ window.__master_schedule = data.work_schedule; }
    if(data && Array.isArray(data.appointments)){
      const apps = data.appointments;
      if(!apps.length){ el.textContent = 'На сегодня записей нет'; return; }
      apps.forEach(a => {
        const card = document.createElement('div'); card.className='card';
        const when = new Date(a.start).toLocaleString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        
        // Translate status
        let statusText = a.status;
        if(a.status === 'scheduled') statusText = 'Запланирована';
        else if(a.status === 'confirmed') statusText = 'Подтверждена';
        else if(a.status === 'cancelled') statusText = 'Отменена';
        else if(a.status === 'completed') statusText = 'Завершена';
        else if(a.status === 'no_show') statusText = 'Не явился';
        
        // Gray out completed appointments
        if(a.is_completed) card.style.opacity = '0.5';
        
        // Build client info with links
        let clientInfo = a.client.name;
        if(a.client.username) clientInfo += ` <a href="https://t.me/${a.client.username}" target="_blank">@${a.client.username}</a>`;
        else if(a.client.telegram_id) clientInfo += ` <a href="tg://user?id=${a.client.telegram_id}">ID:${a.client.telegram_id}</a>`;
        clientInfo += ` (${a.client.phone})`;
        
        card.innerHTML = `<div class="row"><div>${when} — ${a.service}</div><div class="muted">${statusText}</div></div>
          <div>${clientInfo}</div>`;
        
        // Show action buttons only if not completed
        if(!a.is_completed){
          const btnRow = document.createElement('div');
          btnRow.className = 'row';
          btnRow.style.gap = '8px';
          btnRow.style.marginTop = '12px';
          btnRow.innerHTML = `
            <button data-id="${a.id}" class="action-btn btn-cancel">Отменить</button>
            <button data-id="${a.id}" data-start="${a.start}" data-service="${a.service_id}" class="action-btn btn-reschedule">Перенести</button>
            ${a.is_past ? `<button data-id="${a.id}" data-price="${a.service_price}" class="action-btn btn-complete">Завершить</button>` : ''}`;
          card.appendChild(btnRow);
        }
        
        el.appendChild(card);
      });
      el.querySelectorAll('.btn-cancel').forEach(btn => btn.addEventListener('click', async (ev) => {
        const id = ev.target.getAttribute('data-id');
        const reason = prompt('Причина отмены (необязательно):') || '';
        const res = await fetch('/api/master/appointment/cancel', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ mid, appointment_id: Number(id), reason })
        });
        const json = await res.json();
        if(json && json.ok){ loadAppointments(); }
        else alert('Ошибка отмены: ' + (json?.error || '')); 
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
        card.innerHTML = `<div class="row"><div>${c.name}${c.username? ' @'+c.username:''}</div><div>${c.phone}</div></div>
          <div class="muted">Визитов: ${c.total_visits} • Потрачено: ${c.total_spent}</div>`;
        el.appendChild(card);
      });
    } else { el.textContent='Ошибка загрузки'; }
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

  loadAppointments().catch(e => status('appointments error', e));
})();