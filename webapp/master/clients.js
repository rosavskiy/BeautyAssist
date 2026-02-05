// Clients Management JavaScript
let tg = window.Telegram?.WebApp;
let clients = [];
let mid = null;
let currentClientId = null;
let currentClientData = null;
let selectMode = false;
let selectedClients = new Set();
let deleteTarget = null; // 'single' or 'bulk'

// Get master ID from URL params
function getMasterId() {
    const params = new URLSearchParams(window.location.search);
    const midFromUrl = params.get('mid');
    const midFromTg = tg?.initDataUnsafe?.user?.id;
    
    console.log('getMasterId - URL param:', midFromUrl);
    console.log('getMasterId - Telegram WebApp:', midFromTg);
    
    // Prefer URL parameter, fallback to Telegram
    const result = midFromUrl || midFromTg;
    console.log('getMasterId - final result:', result);
    return result;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('Clients page loaded');
    console.log('Telegram WebApp available:', !!tg);
    
    if (tg) {
        tg.ready();
        tg.expand();
    }
    
    // Get master ID
    mid = getMasterId();
    console.log('Master ID:', mid);
    
    if (!mid) {
        console.error('Master ID not found');
        showError('Не удалось определить мастера. Откройте эту страницу через команду /clients в боте.');
        document.getElementById('clients-list').innerHTML = `
            <div class="error-state">
                <p style="text-align: center; padding: 20px;">
                    ❌ Не удалось определить мастера<br><br>
                    Откройте эту страницу через команду <strong>/clients</strong> в боте
                </p>
            </div>
        `;
        return;
    }
    
    // Set theme colors
    document.body.style.backgroundColor = tg?.themeParams?.bg_color || '#ffffff';
    document.body.style.color = tg?.themeParams?.text_color || '#000000';
    
    // Setup search
    setupSearch();
    
    // Load clients
    loadClients();
});

// Setup Search
function setupSearch() {
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', (e) => {
        filterClients(e.target.value);
    });
}

// Load Clients from API
async function loadClients() {
    console.log('=== loadClients START ===');
    console.log('Loading clients for mid:', mid);
    console.log('mid type:', typeof mid);
    console.log('mid value:', JSON.stringify(mid));
    
    try {
        if (!mid) {
            console.error('mid is falsy:', mid);
            showError('Не удалось получить ID мастера');
            return;
        }

        const url = `/api/master/clients?mid=${mid}`;
        console.log('Fetching clients from:', url);
        
        const response = await fetch(url);
        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Response error:', errorText);
            throw new Error(`Ошибка загрузки клиентов (${response.status}): ${errorText}`);
        }

        const responseText = await response.text();
        console.log('Response text:', responseText.substring(0, 200));
        
        clients = JSON.parse(responseText);
        console.log('Clients parsed:', clients.length, 'items');
        renderClients(clients);
    } catch (error) {
        console.error('=== loadClients ERROR ===');
        console.error('Error loading clients:', error);
        console.error('Error stack:', error.stack);
        showError('Не удалось загрузить клиентов: ' + error.message);
        document.getElementById('clients-list').innerHTML = `
            <div class="error-state">
                <p>❌ Ошибка загрузки клиентов</p>
                <button class="btn-secondary" onclick="loadClients()">Попробовать снова</button>
            </div>
        `;
    }
}

// Render Clients List
function renderClients(clientsToRender) {
    const listContainer = document.getElementById('clients-list');
    const emptyState = document.getElementById('empty-state');

    if (clientsToRender.length === 0) {
        listContainer.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    listContainer.style.display = 'block';
    emptyState.style.display = 'none';

    listContainer.innerHTML = clientsToRender.map(client => `
        <div class="client-card ${selectedClients.has(client.id) ? 'selected' : ''}" data-id="${client.id}">
            ${selectMode ? `
                <div class="client-checkbox">
                    <input type="checkbox" ${selectedClients.has(client.id) ? 'checked' : ''} 
                           onchange="toggleClientSelect(${client.id}, this.checked)">
                </div>
            ` : ''}
            <div class="client-content" onclick="${selectMode ? `toggleClientSelect(${client.id})` : `openClientHistory(${client.id})`}">
                <div class="client-header">
                    <div>
                        <span class="client-name">${escapeHtml(client.name)}</span>
                        ${client.username ? `<span class="client-username">@${escapeHtml(client.username)}</span>` : ''}
                    </div>
                    <div class="client-phone">${escapeHtml(client.phone)}</div>
                </div>
                
                <div class="client-stats">
                    <div class="stat-item">
                        <span>📊 Визитов:</span>
                        <span class="stat-value">${client.total_visits || 0}</span>
                    </div>
                    <div class="stat-item">
                        <span>💰 Потрачено:</span>
                        <span class="stat-value">${client.total_spent || 0} ₽</span>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
    
    // Re-init feather icons
    if (typeof feather !== 'undefined') feather.replace({ 'stroke-width': 2.5 });
}

// Filter Clients
function filterClients(searchTerm) {
    if (!searchTerm || searchTerm.trim() === '') {
        renderClients(clients);
        return;
    }

    const term = searchTerm.toLowerCase();
    const filtered = clients.filter(client => {
        const nameMatch = client.name.toLowerCase().includes(term);
        const phoneMatch = client.phone.includes(term);
        const usernameMatch = client.username && client.username.toLowerCase().includes(term);
        return nameMatch || phoneMatch || usernameMatch;
    });

    renderClients(filtered);
}

// Open Client History
async function openClientHistory(clientId) {
    currentClientId = clientId;
    currentClientData = null;
    
    try {
        if (!mid) {
            throw new Error('Не удалось получить ID мастера');
        }

        const response = await fetch(`/api/master/client/history?mid=${mid}&client_id=${clientId}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки истории');
        }

        const data = await response.json();
        
        if (!data || !data.client) {
            throw new Error('Не удалось загрузить данные клиента');
        }

        const client = data.client;
        currentClientData = client; // Save for editing
        const appointments = data.appointments || [];

        // Update modal title
        document.getElementById('modal-title').textContent = `История: ${client.name}`;

        // Render client info
        const infoEl = document.getElementById('client-info');
        infoEl.innerHTML = `
            <div class="client-info-header">
                <div class="client-info-name">${escapeHtml(client.name)}</div>
                <div class="client-info-phone">${escapeHtml(client.phone)}</div>
            </div>
            <div class="client-info-stats">
                Всего визитов: ${client.total_visits || 0} • Потрачено: ${client.total_spent || 0} ₽
            </div>
        `;

        // Render appointments
        const listEl = document.getElementById('appointments-list');
        
        if (appointments.length === 0) {
            listEl.innerHTML = '<div class="empty-history">История посещений пуста</div>';
        } else {
            listEl.innerHTML = appointments.map(appt => {
                // Format date
                const dt = new Date(appt.start_time);
                const dateStr = dt.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric'});
                const timeStr = dt.toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'});

                // Status
                let statusClass = 'status-scheduled';
                let statusText = 'Запланирована';
                
                if (appt.is_completed) {
                    statusClass = 'status-completed';
                    statusText = 'Завершена';
                } else if (appt.status === 'cancelled') {
                    statusClass = 'status-cancelled';
                    statusText = 'Отменена';
                } else if (appt.status === 'confirmed') {
                    statusClass = 'status-confirmed';
                    statusText = 'Подтверждена';
                }

                const amount = appt.payment_amount || appt.service_price || 0;

                return `
                    <div class="appointment-card">
                        <div class="appointment-header">
                            <div>
                                <div class="appointment-service">${escapeHtml(appt.service_name)}</div>
                                <div class="appointment-datetime">${dateStr} в ${timeStr}</div>
                            </div>
                            <div>
                                <div class="appointment-status ${statusClass}">${statusText}</div>
                                <div class="appointment-price">${amount} ₽</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Show modal
        document.getElementById('client-history-modal').style.display = 'flex';

    } catch (error) {
        console.error('Error loading client history:', error);
        showError(error.message);
    }
}

// Close Client History
function closeClientHistory() {
    document.getElementById('client-history-modal').style.display = 'none';
    currentClientId = null;
}

// Show Error Toast
function showError(message) {
    const toast = document.getElementById('error-toast');
    const messageEl = document.getElementById('error-message');
    
    messageEl.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.id === 'client-history-modal') {
        closeClientHistory();
    }
    if (e.target.id === 'edit-client-modal') {
        closeEditModal();
    }
    if (e.target.id === 'confirm-delete-modal') {
        closeConfirmDelete();
    }
});

// ========== SELECT MODE ==========

function toggleSelectMode() {
    selectMode = !selectMode;
    selectedClients.clear();
    
    const bulkActions = document.getElementById('bulk-actions');
    const toggleBtn = document.getElementById('toggle-select-mode');
    
    if (selectMode) {
        bulkActions.classList.remove('hidden');
        toggleBtn.classList.add('active');
    } else {
        bulkActions.classList.add('hidden');
        toggleBtn.classList.remove('active');
    }
    
    updateSelectedCount();
    renderClients(clients);
}

function toggleClientSelect(clientId, checked) {
    if (checked === undefined) {
        // Toggle
        if (selectedClients.has(clientId)) {
            selectedClients.delete(clientId);
        } else {
            selectedClients.add(clientId);
        }
    } else {
        // Set explicitly
        if (checked) {
            selectedClients.add(clientId);
        } else {
            selectedClients.delete(clientId);
        }
    }
    
    updateSelectedCount();
    renderClients(clients);
}

function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox.checked) {
        clients.forEach(c => selectedClients.add(c.id));
    } else {
        selectedClients.clear();
    }
    updateSelectedCount();
    renderClients(clients);
}

function updateSelectedCount() {
    document.getElementById('selected-count').textContent = `${selectedClients.size} выбрано`;
    document.getElementById('select-all').checked = selectedClients.size === clients.length && clients.length > 0;
}

// ========== EDIT CLIENT ==========

function openEditModal() {
    if (!currentClientData) return;
    
    document.getElementById('edit-client-name').value = currentClientData.name || '';
    document.getElementById('edit-client-phone').value = currentClientData.phone || '';
    document.getElementById('edit-client-modal').style.display = 'flex';
    
    if (typeof feather !== 'undefined') feather.replace({ 'stroke-width': 2.5 });
}

function closeEditModal() {
    document.getElementById('edit-client-modal').style.display = 'none';
}

async function saveClient() {
    if (!currentClientId || !mid) return;
    
    const name = document.getElementById('edit-client-name').value.trim();
    const phone = document.getElementById('edit-client-phone').value.trim();
    
    if (!name) {
        showError('Введите имя клиента');
        return;
    }
    
    try {
        const response = await fetch('/api/master/client/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mid, client_id: currentClientId, name, phone })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }
        
        closeEditModal();
        closeClientHistory();
        showSuccess('Клиент обновлён');
        loadClients();
        
    } catch (error) {
        showError(error.message);
    }
}

// ========== DELETE CLIENT ==========

function openDeleteConfirm(type) {
    deleteTarget = type;
    const textEl = document.getElementById('confirm-delete-text');
    
    if (type === 'single') {
        textEl.textContent = 'Вы уверены, что хотите удалить этого клиента? Все его записи также будут удалены.';
    } else {
        textEl.textContent = `Удалить ${selectedClients.size} клиентов? Все их записи также будут удалены.`;
    }
    
    document.getElementById('confirm-delete-modal').style.display = 'flex';
    if (typeof feather !== 'undefined') feather.replace({ 'stroke-width': 2.5 });
}

function closeConfirmDelete() {
    document.getElementById('confirm-delete-modal').style.display = 'none';
    deleteTarget = null;
}

async function confirmDelete() {
    if (deleteTarget === 'single') {
        await deleteSingleClient();
    } else {
        await deleteBulkClients();
    }
    closeConfirmDelete();
}

async function deleteSingleClient() {
    if (!currentClientId || !mid) return;
    
    try {
        const response = await fetch('/api/master/client/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mid, client_id: currentClientId })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка удаления');
        }
        
        closeClientHistory();
        showSuccess('Клиент удалён');
        loadClients();
        
    } catch (error) {
        showError(error.message);
    }
}

async function deleteBulkClients() {
    if (selectedClients.size === 0 || !mid) return;
    
    try {
        const response = await fetch('/api/master/clients/delete-bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mid, client_ids: Array.from(selectedClients) })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка удаления');
        }
        
        const data = await response.json();
        showSuccess(`Удалено клиентов: ${data.deleted_count}`);
        selectedClients.clear();
        updateSelectedCount();
        loadClients();
        
    } catch (error) {
        showError(error.message);
    }
}

// ========== SUCCESS TOAST ==========

function showSuccess(message) {
    const toast = document.getElementById('success-toast');
    const messageEl = document.getElementById('success-message');
    
    messageEl.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ========== INIT EVENT LISTENERS ==========

document.addEventListener('DOMContentLoaded', () => {
    // Toggle select mode button
    document.getElementById('toggle-select-mode')?.addEventListener('click', toggleSelectMode);
    
    // Select all checkbox
    document.getElementById('select-all')?.addEventListener('change', toggleSelectAll);
    
    // Delete selected button
    document.getElementById('delete-selected')?.addEventListener('click', () => {
        if (selectedClients.size > 0) {
            openDeleteConfirm('bulk');
        }
    });
    
    // Edit client button (in history modal)
    document.getElementById('edit-client-btn')?.addEventListener('click', openEditModal);
    
    // Delete client button (in history modal)
    document.getElementById('delete-client-btn')?.addEventListener('click', () => {
        openDeleteConfirm('single');
    });
});
