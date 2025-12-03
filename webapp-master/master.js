(function(){
  const tg = window.Telegram?.WebApp; tg && tg.expand();
  const qs = new URLSearchParams(window.location.search);
  const mid = qs.get('mid');
  const status = (msg, err) => console.log(msg || (err||''));

  async function api(path){ const r = await fetch(path); return r.json(); }

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
    cal.onDatePick = null;
    cal.mode = 'dayoff';
    // Ensure schedule is loaded before first render to avoid false-off weekends
    const ws = window.__master_schedule || {};
    if(!ws || !ws._loaded){
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
    cal.toggledOff = new Set(ws.days_off_dates || []);
    document.getElementById('slots-list').innerHTML = '';
    document.getElementById('calendar-section').classList.remove('hidden');
    renderCalendar();
    // Show helper text in slots area
    const slotsEl = document.getElementById('slots-list');
    const help = document.createElement('div'); help.className='muted'; help.textContent='Нажимайте на дни, чтобы отметить как нерабочие'; slotsEl.appendChild(help);
    // Add save button for per-date dayoff aligned to right
    const actions = document.createElement('div'); actions.className='slots-actions';
    const save = document.createElement('button'); save.className='nav-btn'; save.textContent='Сохранить';
    save.addEventListener('click', saveDayOffDates);
    actions.appendChild(save);
    slotsEl.appendChild(actions);
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
    const todayStr = new Date().toISOString().slice(0,10);
    for(let d=1; d<=daysInMonth; d++){
      const cell = document.createElement('div'); cell.className='day-cell';
      const date = new Date(year, month, d);
      const dateStr = date.toISOString().slice(0,10);
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
    if(ev.target.id === 'daysoff-close') document.getElementById('daysoff-section').classList.add('hidden');
    if(ev.target.id === 'daysoff-save') saveDaysOff();
    if(ev.target.id === 'open-dayoff-calendar') openCalendarDayOffMode();
    if(ev.target.id === 'open-hours') openHoursModal();
    if(ev.target.id === 'hours-close') document.getElementById('hours-section').classList.add('hidden');
    if(ev.target.id === 'hours-save') saveHours();
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
        card.innerHTML = `<div class="row"><div>${when} — ${a.service}</div><div class="muted">${a.status}</div></div>
          <div>${a.client.name} (${a.client.phone})${a.client.username? ' @'+a.client.username:''}</div>
          <div class="row">
            <button data-id="${a.id}" class="btn-cancel">Отменить</button>
            <button data-id="${a.id}" data-start="${a.start}" data-service="${a.service_id}" class="btn-reschedule">Перенести</button>
          </div>`;
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
        openCalendar(async (dateStr) => {
          try {
            const rc = dataLocal.referral_code;
            const slots = await api(`/api/slots?code=${encodeURIComponent(rc)}&service=${encodeURIComponent(serviceId)}&date=${encodeURIComponent(dateStr)}`);
            const slotsEl = document.getElementById('slots-list');
            slotsEl.innerHTML = '';
            if(!Array.isArray(slots) || !slots.length){
              const p = document.createElement('div'); p.className='muted'; p.textContent='Нет свободных слотов на выбранную дату'; slotsEl.appendChild(p); return;
            }
            slots.forEach(s => {
              const btn = document.createElement('button'); btn.className='slot-btn';
              const label = new Date(s.start).toLocaleTimeString('ru-RU',{hour:'2-digit', minute:'2-digit'});
              btn.textContent = label;
              btn.addEventListener('click', async () => {
                const res = await fetch('/api/master/appointment/reschedule', {
                  method:'POST', headers:{'Content-Type':'application/json'},
                  body: JSON.stringify({ mid, appointment_id: Number(id), new_start: s.start })
                });
                const json = await res.json();
                if(json && json.ok){ closeCalendar(); loadAppointments(); }
                else alert('Ошибка переноса: ' + (json?.error || ''));
              });
              slotsEl.appendChild(btn);
            });
          } catch(e){ alert('Ошибка загрузки слотов'); }
        });
      }));
      // Settings button moved to header; keep list clean
    } else { el.textContent = 'Ошибка загрузки'; }
  }
  function openHoursModal(){
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
      if(js && js.ok){ window.__master_schedule = js.work_schedule || {}; document.getElementById('daysoff-section').classList.add('hidden'); renderCalendar(); }
      else alert('Не удалось сохранить: ' + (js?.error || ''));
    } catch(e){ alert('Ошибка запроса'); }
  }

  async function saveDayOffDates(){
    try {
      const resp = await fetch('/api/master/schedule/days_off', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mid, days_off: (window.__master_schedule?.days_off)||[], days_off_dates: Array.from(cal.toggledOff) }) });
      const js = await resp.json();
      if(js && js.ok){ window.__master_schedule = js.work_schedule || {}; showSuccessTick(); closeCalendar(); renderCalendar(); }
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

  loadAppointments().catch(e => status('appointments error', e));
  loadClients().catch(e => status('clients error', e));
})();