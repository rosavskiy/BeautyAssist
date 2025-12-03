(function(){
  const tg = window.Telegram?.WebApp;
  tg && tg.expand();

  const qs = new URLSearchParams(window.location.search);
  const masterCode = qs.get('code');
  const preselectService = qs.get('service');

  const serviceSelect = document.getElementById('service-select');
  const dateInput = document.getElementById('date-input');
  const slotsEl = document.getElementById('slots');
  const nameEl = document.getElementById('client-name');
  const phoneEl = document.getElementById('client-phone');
  const submitBtn = document.getElementById('submit-btn');
  const statusEl = document.getElementById('status');

  // Helpers
  function api(path){ return fetch(path).then(r => r.json()); }
  function setStatus(msg, isErr){ statusEl.textContent = msg || ''; statusEl.style.color = isErr ? '#f66' : '#0a0'; }
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

  async function loadServices(){
    const data = await api(`/api/services?code=${encodeURIComponent(masterCode)}`);
    if(Array.isArray(data)){
      serviceSelect.innerHTML = data.map(s => `<option value="${s.id}" ${preselectService==s.id? 'selected':''}>${s.name} — ${s.price} ₽ / ${s.duration} мин</option>`).join('');
      if(data.length){
        await loadSlots();
      }
    }else{
      setStatus('Мастер не найден', true);
    }
  }

  async function loadSlots(){
    const service = serviceSelect.value;
    const date = dateInput.value || new Date().toISOString().slice(0,10);
    if(!dateInput.value){ dateInput.value = date; }
    const data = await api(`/api/slots?code=${encodeURIComponent(masterCode)}&service=${encodeURIComponent(service)}&date=${date}`);
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
        const btn = document.createElement('div');
        btn.className = 'slot';
        btn.textContent = label;
        if(!s.available){
          btn.classList.add('disabled');
          btn.setAttribute('aria-disabled', 'true');
          btn.title = 'Слот занят';
        } else {
          btn.addEventListener('click', () => {
            document.querySelectorAll('.slot').forEach(el => el.classList.remove('active'));
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
      tg && tg.close();
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

  serviceSelect.addEventListener('change', loadSlots);
  dateInput.addEventListener('change', loadSlots);
  submitBtn.addEventListener('click', book);
  phoneEl.addEventListener('input', () => {
    formatPhoneDisplay();
    submitBtn.disabled = !selectedStart || !isPhoneValid() || !nameEl.value.trim();
  });
  nameEl.addEventListener('input', () => {
    submitBtn.disabled = !selectedStart || !isPhoneValid() || !nameEl.value.trim();
  });

  // init defaults
  const today = new Date();
  dateInput.value = today.toISOString().slice(0,10);
  // initialize masked phone prefix
  if(!phoneEl.value) phoneEl.value = '+7 ';
  loadServices().catch(() => setStatus('Ошибка загрузки услуг', true));
})();
