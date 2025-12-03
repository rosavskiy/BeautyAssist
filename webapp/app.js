(function(){
  const tg = window.Telegram?.WebApp;
  tg && tg.expand();

  const qs = new URLSearchParams(window.location.search);
  const masterCode = qs.get('code');
  const preselectService = qs.get('service');

  const serviceSelect = document.getElementById('service-select');
  const dateBtn = document.getElementById('date-btn');
  const calendarSection = document.getElementById('calendar-section');
  const calendarClose = document.getElementById('calendar-close');
  const calPrev = document.getElementById('cal-prev');
  const calNext = document.getElementById('cal-next');
  const calTitle = document.getElementById('cal-title');
  const calendarGrid = document.getElementById('calendar-grid');
  const slotsEl = document.getElementById('slots');
  const nameEl = document.getElementById('client-name');
  const phoneEl = document.getElementById('client-phone');
  const submitBtn = document.getElementById('submit-btn');
  const statusEl = document.getElementById('status');

  // Calendar state
  let currentMonth = new Date();
  let selectedDate = null;

  // Helpers
  function api(path){ return fetch(path).then(r => r.json()); }
  function setStatus(msg, isErr){ statusEl.textContent = msg || ''; statusEl.style.color = isErr ? '#f66' : '#0a0'; }
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
  function getRawDigitsFromPhone(){
    let raw = phoneEl.value || '';
    raw = raw.replace(/\s+/g, '').replace(/[-()]/g, '');
    raw = raw.replace(/^\+?8/, '+7');
    if(!raw.startsWith('+7')) raw = '+7' + raw.replace(/^\+?/, '');
    const digits = raw.replace(/^\+7/, '').replace(/\D/g, '').slice(0,10);
    return digits;
  }
  function formatPhoneDisplay(){
    const d = getRawDigitsFromPhone();
    // Build mask: +7 (XXX) XXX-XX-XX progressively
    let out = '+7 ';
    if(d.length){ out += '(' + d.slice(0, Math.min(3,d.length)) + ')'; }
    if(d.length > 3){ out += ' ' + d.slice(3, Math.min(6,d.length)); }
    if(d.length > 6){ out += '-' + d.slice(6, Math.min(8,d.length)); }
    if(d.length > 8){ out += '-' + d.slice(8, Math.min(10,d.length)); }
    phoneEl.value = out;
  }
  function isPhoneValid(){
    const d = getRawDigitsFromPhone();
    return d.length === 10;
  }

  let selectedStart = null;
  let selectedBtn = null;

  // Calendar functions
  function renderCalendar(){
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const today = new Date();
    today.setHours(0,0,0,0);
    
    calTitle.textContent = currentMonth.toLocaleDateString('ru-RU', {month:'long', year:'numeric'});
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDay = firstDay.getDay() || 7; // 1=Mon
    const daysInMonth = lastDay.getDate();
    
    calendarGrid.innerHTML = '';
    
    // Empty cells before first day
    for(let i = 1; i < startDay; i++){
      const empty = document.createElement('div');
      calendarGrid.appendChild(empty);
    }
    
    // Days
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
        if(selectedDate && cellDate.getTime() === selectedDate.getTime()){
          cell.classList.add('selected');
        }
        cell.addEventListener('click', () => selectDate(cellDate));
      }
      
      calendarGrid.appendChild(cell);
    }
  }
  
  function selectDate(date){
    selectedDate = date;
    const dateStr = date.getFullYear() + '-' + 
                    String(date.getMonth()+1).padStart(2,'0') + '-' + 
                    String(date.getDate()).padStart(2,'0');
    dateBtn.textContent = date.toLocaleDateString('ru-RU', {day:'numeric', month:'long', year:'numeric'});
    calendarSection.classList.add('hidden');
    loadSlots(dateStr);
  }
  
  dateBtn.addEventListener('click', () => {
    currentMonth = selectedDate || new Date();
    renderCalendar();
    calendarSection.classList.remove('hidden');
  });
  
  calendarClose.addEventListener('click', () => calendarSection.classList.add('hidden'));
  calPrev.addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    renderCalendar();
  });
  calNext.addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    renderCalendar();
  });
  
  // Initialize with today
  selectedDate = new Date();
  selectedDate.setHours(0,0,0,0);
  dateBtn.textContent = selectedDate.toLocaleDateString('ru-RU', {day:'numeric', month:'long', year:'numeric'});

  async function loadClientInfo(){
    const user = tg?.initDataUnsafe?.user;
    const telegram_id = user?.id;
    if(!telegram_id) return;
    try {
      const data = await api(`/api/client/info?code=${encodeURIComponent(masterCode)}&telegram_id=${telegram_id}`);
      if(data && data.found){
        nameEl.value = data.name || '';
        phoneEl.value = data.phone || '';
        formatPhoneDisplay();
      }
    } catch(e){
      console.warn('Failed to load client info:', e);
    }
  }

  async function loadServices(){
    if(!masterCode){
      console.error('loadServices: masterCode is missing');
      setStatus('Ошибка: отсутствует код мастера', true);
      return;
    }
    console.log('loadServices: masterCode =', masterCode);
    try {
      const data = await api(`/api/services?code=${encodeURIComponent(masterCode)}`);
      console.log('loadServices: received data =', data);
      if(Array.isArray(data)){
        serviceSelect.innerHTML = data.map(s => `<option value="${s.id}" ${preselectService==s.id? 'selected':''}>${s.name} — ${s.price} ₽ / ${s.duration} мин</option>`).join('');
        if(data.length){
          // Load slots after services are loaded and service is selected
          await loadSlots();
        }
      }else{
        setStatus('Мастер не найден', true);
      }
    } catch(e){
      console.error('loadServices error:', e);
      setStatus('Ошибка загрузки услуг', true);
    }
  }

  async function loadSlots(dateStr){
    if(!serviceSelect.value) return; // Don't load slots if no service selected
    
    if(!dateStr && selectedDate){
      dateStr = selectedDate.getFullYear() + '-' + 
                String(selectedDate.getMonth()+1).padStart(2,'0') + '-' + 
                String(selectedDate.getDate()).padStart(2,'0');
    }
    if(!dateStr) dateStr = new Date().toISOString().slice(0,10);
    
    const service = serviceSelect.value;
    const data = await api(`/api/slots?code=${encodeURIComponent(masterCode)}&service=${encodeURIComponent(service)}&date=${dateStr}`);
    slotsEl.innerHTML = '';
    selectedStart = null;
    submitBtn.disabled = true;
    if(Array.isArray(data)){
      if(!data.length){
        slotsEl.textContent = 'Нет слотов на выбранный день';
        return;
      }
      data.forEach(s => {
        const label = new Date(s.start).toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});
        const btn = document.createElement('button');
        btn.className = 'slot-btn';
        btn.textContent = label;
        if(!s.available){
          btn.classList.add('unavailable');
          btn.disabled = true;
          btn.title = 'Слот занят';
        } else {
          btn.addEventListener('click', () => {
            document.querySelectorAll('.slot-btn').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            selectedStart = s.start;
            selectedBtn = btn;
            submitBtn.disabled = false;
          });
        }
        slotsEl.appendChild(btn);
      });
    } else {
      setStatus('Ошибка загрузки слотов', true);
    }
  }

  async function book(){
    const service = serviceSelect.value;
    const name = nameEl.value.trim();
    const phone = phoneEl.value.trim();
    formatPhoneDisplay();
    if(!selectedStart || !name || !phone){
      setStatus('Заполните имя, телефон и выберите время', true);
      return;
    }
    if(!isPhoneValid()){
      setStatus('Телефон: формат +7 и 10 цифр', true);
      return;
    }
    const tg = window.Telegram?.WebApp;
    const user = tg?.initDataUnsafe?.user;
    const telegram_id = user?.id || null;
    const telegram_username = user?.username || null;
    // show loader on button
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
    // Optimistically block the chosen slot to prevent double-clicks
    if(selectedBtn){ selectedBtn.classList.add('disabled'); }
    const res = await fetch('/api/book', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        code: masterCode,
        service,
        start: selectedStart,
        name,
        phone: '+7' + getRawDigitsFromPhone(),
        telegram_id,
        telegram_username
      })
    });
    const json = await res.json();
    if(json && json.ok){
      setStatus('Вы записаны! Сообщение отправлено мастеру.');
      submitBtn.classList.remove('loading');
      submitBtn.disabled = true;
      // Refresh slots so the just-booked time disappears
      await loadSlots();
      showSuccessTick(() => { tg && tg.close(); });
    }else{
      const err = json?.error || 'Ошибка';
      if(err === 'free_quota_exceeded') setStatus('У мастера исчерпан лимит на бесплатном тарифе.', true);
      else if(err === 'conflict'){
        setStatus('Упс! Слот уже занят. Выберите другое время.', true);
        // Refresh slots to reflect latest occupancy
        await loadSlots();
      }
      else setStatus('Ошибка брони: ' + err, true);
      submitBtn.classList.remove('loading');
      submitBtn.disabled = !selectedStart || !isPhoneValid() || !nameEl.value.trim();
    }
  }

  serviceSelect.addEventListener('change', () => loadSlots());
  submitBtn.addEventListener('click', book);
  phoneEl.addEventListener('input', () => {
    formatPhoneDisplay();
    submitBtn.disabled = !selectedStart || !isPhoneValid() || !nameEl.value.trim();
  });
  nameEl.addEventListener('input', () => {
    submitBtn.disabled = !selectedStart || !isPhoneValid() || !nameEl.value.trim();
  });

  // initialize masked phone prefix
  if(!phoneEl.value) phoneEl.value = '+7 ';
  
  // Check if masterCode is present
  if(!masterCode){
    setStatus('Ошибка: отсутствует код мастера', true);
    console.error('masterCode is missing from URL');
  } else {
    // Load client info if telegram_id is present, then load services
    loadClientInfo().then(() => loadServices()).catch(() => setStatus('Ошибка загрузки услуг', true));
  }
})();
