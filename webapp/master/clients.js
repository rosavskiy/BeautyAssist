// Clients Management JavaScript
let tg = window.Telegram.WebApp;
let clients = [];
let mid = null;
let currentClientId = null;

// Get master ID from URL params
function getMasterId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('mid') || tg.initDataUnsafe?.user?.id;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    tg.ready();
    tg.expand();
    
    // Get master ID
    mid = getMasterId();
    if (!mid) {
        showError('Не удалось определить мастера');
        return;
    }
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
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
    try {
        if (!mid) {
            showError('Не удалось получить ID мастера');
            return;
        }

        const response = await fetch(`/api/master/clients?mid=${mid}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки клиентов');
        }

        clients = await response.json();
        renderClients(clients);
    } catch (error) {
        console.error('Error loading clients:', error);
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
        <div class="client-card" onclick="openClientHistory(${client.id})">
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
    `).join('');
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
});
