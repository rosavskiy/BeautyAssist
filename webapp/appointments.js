(function(){
  const tg = window.Telegram?.WebApp;
  tg && tg.expand();

  const qs = new URLSearchParams(window.location.search);
  const masterCode = qs.get('code');
  const user = tg?.initDataUnsafe?.user;
  const telegram_id = user?.id;

  const appointmentsList = document.getElementById('appointments-list');
  const rescheduleSection = document.getElementById('reschedule-section');
  const rescheduleClose = document.getElementById('reschedule-close');
  const calPrev = document.getElementById('cal-prev');
  const calNext = document.getElementById('cal-next');
  const calTitle = document.getElementById('cal-title');
  const calendarGrid = document.getElementById('calendar-grid');
  const slotsList = document.getElementById('slots-list');
  const filterBtns = document.querySelectorAll('.filter-btn');

  let currentMonth = new Date();
  let currentAppointmentId = null;
  let currentServiceId = null;
  let currentFilter = 'upcoming';

  function api(path){ return fetch(path).then(r => r.json()); }
  function showSuccessTick(callback){
    const overlay = document.createElement('div');
    overlay.className = 'success-overlay';
    overlay.innerHTML = '<div class="success-tick success-anim"><svg viewBox="0 0 64 64"><path d="M16 34 L28 46 L48 22"/></svg></div>';
    document.body.appendChild(overlay);
    setTimeout(() => {
      overlay.remove();
      if(typeof callback === 'function') callback();
    }, 900);
  }

  // Filter buttons
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      loadAppointments();
    });
  });

  // Calendar functions
  function renderCalendar(){
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const today = new Date();
    today.setHours(0,0,0,0);
    
    calTitle.textContent = currentMonth.toLocaleDateString('ru-RU', {month:'long', year:'numeric'});
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDay = firstDay.getDay() || 7;
    const daysInMonth = lastDay.getDate();
    
    calendarGrid.innerHTML = '';
    
    for(let i = 1; i < startDay; i++){
      calendarGrid.appendChild(document.createElement('div'));
    }
    
    for(let day = 1; day <= daysInMonth; day++){
      const cell = document.createElement('div');
      cell.className = 'day-cell';
      cell.textContent = day;
      
      const cellDate = new Date(year, month, day);
      cellDate.setHours(0,0,0,0);
      
      if(cellDate < today){
        cell.classList.add('disabled');
      } else {
        if(cellDate.getTime() === today.getTime()){
          cell.classList.add('today');
        }
        cell.addEventListener('click', () => selectDate(cellDate));
      }
      
      calendarGrid.appendChild(cell);
    }
  }
  
  async function selectDate(date){
    const dateStr = date.getFullYear() + '-' + 
                    String(date.getMonth()+1).padStart(2,'0') + '-' + 
                    String(date.getDate()).padStart(2,'0');
    
    try {
      const slots = await api(`/api/slots?code=${encodeURIComponent(masterCode)}&service=${currentServiceId}&date=${dateStr}`);
      slotsList.innerHTML = '';
      
      if(!Array.isArray(slots) || !slots.length){
        const p = document.createElement('div');
        p.className = 'muted';
        p.textContent = 'Нет свободных слотов на выбранную дату';
        slotsList.appendChild(p);
        return;
      }
      
      slots.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'slot-btn';
        const label = new Date(s.start).toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        btn.textContent = label;
        
        if(!s.available){
          btn.classList.add('unavailable');
          btn.disabled = true;
        } else {
          btn.addEventListener('click', async () => {
            if(confirm(`Перенести запись на ${date.toLocaleDateString('ru-RU')} в ${label}?`)){
              await rescheduleAppointment(s.start);
            }
          });
        }
        slotsList.appendChild(btn);
      });
    } catch(e){
      alert('Ошибка загрузки слотов');
    }
  }
  
  async function rescheduleAppointment(newStart){
    try {
      const res = await fetch('/api/client/appointment/reschedule', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          code: masterCode,
          telegram_id,
          appointment_id: currentAppointmentId,
          new_start: newStart
        })
      });
      
      const json = await res.json();
      if(json && json.ok){
        rescheduleSection.classList.add('hidden');
        showSuccessTick(() => {
          loadAppointments();
        });
      } else {
        alert('Ошибка переноса: ' + (json?.error || ''));
      }
    } catch(e){
      alert('Ошибка запроса');
    }
  }
  
  async function cancelAppointment(appointmentId){
    if(!confirm('Вы уверены, что хотите отменить запись?')) return;
    
    try {
      const res = await fetch('/api/client/appointment/cancel', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          code: masterCode,
          telegram_id,
          appointment_id: appointmentId
        })
      });
      
      const json = await res.json();
      if(json && json.ok){
        alert('Запись отменена');
        loadAppointments();
      } else {
        alert('Ошибка отмены: ' + (json?.error || ''));
      }
    } catch(e){
      alert('Ошибка запроса');
    }
  }
  
  async function loadAppointments(){
    if(!telegram_id){
      appointmentsList.innerHTML = '<p class="muted">Не удалось определить пользователя</p>';
      return;
    }
    
    try {
      const data = await api(`/api/client/appointments?code=${encodeURIComponent(masterCode)}&telegram_id=${telegram_id}&status=${currentFilter}`);
      appointmentsList.innerHTML = '';
      
      if(!data || !Array.isArray(data.appointments) || !data.appointments.length){
        appointmentsList.innerHTML = '<section><p class="muted">У вас пока нет записей</p></section>';
        return;
      }
      
      data.appointments.forEach(app => {
        const card = document.createElement('section');
        card.className = 'appointment-card';
        
        const startDate = new Date(app.start);
        const dateStr = startDate.toLocaleDateString('ru-RU', {day:'numeric', month:'long', year:'numeric'});
        const timeStr = startDate.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        
        let statusText = app.status;
        let statusClass = '';
        let statusIcon = '';
        if(app.status === 'scheduled') { 
          statusText = 'Запланирована'; 
          statusClass = 'status-scheduled';
          statusIcon = '📋';
        }
        else if(app.status === 'confirmed') { 
          statusText = 'Подтверждена'; 
          statusClass = 'status-confirmed';
          statusIcon = '✅';
        }
        else if(app.status === 'cancelled') { 
          statusText = 'Отменена'; 
          statusClass = 'status-cancelled';
          statusIcon = '❌';
        }
        else if(app.status === 'completed') { 
          statusText = 'Завершена'; 
          statusClass = 'status-completed';
          statusIcon = '✔️';
        }
        else if(app.status === 'no_show') { 
          statusText = 'Не явились'; 
          statusClass = 'status-no-show';
          statusIcon = '⚠️';
        }
        
        const canModify = ['scheduled', 'confirmed'].includes(app.status);
        const isPast = new Date(app.start) < new Date();
        
        let paymentInfo = '';
        if(app.is_completed && app.payment_amount > 0) {
          paymentInfo = `<div style="color: #4CAF50; margin-top: 8px;">💰 Оплачено: ${app.payment_amount} ₽</div>`;
        }
        
        let commentInfo = '';
        if(app.client_comment) {
          commentInfo = `<div style="color: #7C88A0; margin-top: 8px; padding: 8px; background: #F5F7FA; border-radius: 8px;">💬 ${app.client_comment}</div>`;
        }
        
        const priceInfo = app.service_price ? `<div style="color: #7C88A0; margin-bottom: 12px;">💰 ${app.service_price} ₽</div>` : '';
        
        card.innerHTML = `
          <div class="row" style="justify-content: space-between; margin-bottom: 8px;">
            <div style="font-weight: 600; font-size: 16px;">${app.service}</div>
            <div class="badge ${statusClass}">${statusIcon} ${statusText}</div>
          </div>
          <div style="color: #7C88A0; margin-bottom: 4px;">📅 ${dateStr}</div>
          <div style="color: #7C88A0; margin-bottom: 4px;">🕐 ${timeStr}</div>
          ${priceInfo}
          ${commentInfo}
          ${paymentInfo}
          ${canModify && !isPast ? `
            <div class="row" style="gap: 8px; margin-top: 12px;">
              <button class="btn-cancel" data-id="${app.id}">Отменить</button>
              <button class="btn-reschedule" data-id="${app.id}" data-service="${app.service_id}">Перенести</button>
            </div>
          ` : ''}
        `;
        
        appointmentsList.appendChild(card);
      });
      
      // Attach event listeners
      appointmentsList.querySelectorAll('.btn-cancel').forEach(btn => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-id'));
          cancelAppointment(id);
        });
      });
      
      appointmentsList.querySelectorAll('.btn-reschedule').forEach(btn => {
        btn.addEventListener('click', () => {
          currentAppointmentId = Number(btn.getAttribute('data-id'));
          currentServiceId = Number(btn.getAttribute('data-service'));
          currentMonth = new Date();
          renderCalendar();
          rescheduleSection.classList.remove('hidden');
        });
      });
      
    } catch(e){
      appointmentsList.innerHTML = '<section><p class="muted">Ошибка загрузки записей</p></section>';
      console.error(e);
    }
  }
  
  rescheduleClose.addEventListener('click', () => rescheduleSection.classList.add('hidden'));
  calPrev.addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    renderCalendar();
  });
  calNext.addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    renderCalendar();
  });
  
  loadAppointments();
})();
