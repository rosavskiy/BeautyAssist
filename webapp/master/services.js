// Services Management JavaScript
let tg = window.Telegram.WebApp;
let services = [];
let currentServiceId = null;
let deleteServiceId = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    tg.ready();
    tg.expand();
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
    // Setup event listeners
    setupEventListeners();
    
    // Load services
    loadServices();
});

// Setup Event Listeners
function setupEventListeners() {
    // Add service button
    document.getElementById('add-service-btn').addEventListener('click', openServiceModal);
    
    // Service form submit
    document.getElementById('service-form').addEventListener('submit', handleServiceSubmit);
    
    // Description character counter
    const descTextarea = document.getElementById('service-description');
    descTextarea.addEventListener('input', () => {
        const counter = document.querySelector('.char-counter');
        counter.textContent = `${descTextarea.value.length}/500`;
    });
    
    // Close modal on backdrop click
    document.getElementById('service-modal').addEventListener('click', (e) => {
        if (e.target.id === 'service-modal') {
            closeServiceModal();
        }
    });
    
    document.getElementById('delete-modal').addEventListener('click', (e) => {
        if (e.target.id === 'delete-modal') {
            closeDeleteModal();
        }
    });
}

// Load Services from API
async function loadServices() {
    try {
        const masterId = tg.initDataUnsafe?.user?.id;
        if (!masterId) {
            showError('Не удалось получить ID пользователя');
            return;
        }

        const response = await fetch(`/api/master/services?mid=${masterId}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки услуг');
        }

        services = await response.json();
        renderServices();
    } catch (error) {
        console.error('Error loading services:', error);
        showError('Не удалось загрузить услуги: ' + error.message);
        document.getElementById('services-list').innerHTML = `
            <div class="error-state">
                <p>❌ Ошибка загрузки услуг</p>
                <button class="btn-secondary" onclick="loadServices()">Попробовать снова</button>
            </div>
        `;
    }
}

// Render Services List
function renderServices() {
    const listContainer = document.getElementById('services-list');
    const emptyState = document.getElementById('empty-state');

    if (services.length === 0) {
        listContainer.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    listContainer.style.display = 'grid';
    emptyState.style.display = 'none';

    listContainer.innerHTML = services.map(service => `
        <div class="service-card" data-id="${service.id}">
            <div class="service-header">
                <h3 class="service-name">${escapeHtml(service.name)}</h3>
                ${service.category ? `<span class="service-category">${escapeHtml(service.category)}</span>` : ''}
            </div>
            
            <div class="service-details">
                <div class="service-info">
                    <span class="info-label">⏱ Длительность:</span>
                    <span class="info-value">${service.duration_minutes} мин</span>
                </div>
                <div class="service-info">
                    <span class="info-label">💰 Цена:</span>
                    <span class="info-value">${service.price} ₽</span>
                </div>
            </div>

            ${service.description ? `
                <p class="service-description">${escapeHtml(service.description)}</p>
            ` : ''}

            <div class="service-actions">
                <button class="btn-edit" onclick="editService(${service.id})">
                    ✏️ Редактировать
                </button>
                <button class="btn-delete" onclick="openDeleteModal(${service.id}, '${escapeHtml(service.name)}')">
                    🗑 Удалить
                </button>
            </div>

            ${!service.is_active ? '<div class="service-inactive">Неактивна</div>' : ''}
        </div>
    `).join('');
}

// Open Service Modal (Add or Edit)
function openServiceModal(serviceId = null) {
    const modal = document.getElementById('service-modal');
    const form = document.getElementById('service-form');
    const title = document.getElementById('modal-title');
    
    // Reset form
    form.reset();
    document.querySelector('.char-counter').textContent = '0/500';
    
    if (serviceId) {
        // Edit mode
        const service = services.find(s => s.id === serviceId);
        if (!service) return;
        
        title.textContent = 'Редактировать услугу';
        document.getElementById('service-id').value = service.id;
        document.getElementById('service-name').value = service.name;
        document.getElementById('service-duration').value = service.duration_minutes;
        document.getElementById('service-price').value = service.price;
        document.getElementById('service-category').value = service.category || '';
        document.getElementById('service-description').value = service.description || '';
        document.querySelector('.char-counter').textContent = `${(service.description || '').length}/500`;
    } else {
        // Add mode
        title.textContent = 'Добавить услугу';
        document.getElementById('service-id').value = '';
    }
    
    modal.style.display = 'flex';
    
    // Focus first input
    setTimeout(() => {
        document.getElementById('service-name').focus();
    }, 100);
}

// Close Service Modal
function closeServiceModal() {
    document.getElementById('service-modal').style.display = 'none';
}

// Edit Service
function editService(serviceId) {
    openServiceModal(serviceId);
}

// Handle Service Form Submit
async function handleServiceSubmit(e) {
    e.preventDefault();
    
    const serviceId = document.getElementById('service-id').value;
    const name = document.getElementById('service-name').value.trim();
    const duration = parseInt(document.getElementById('service-duration').value);
    const price = parseInt(document.getElementById('service-price').value);
    const category = document.getElementById('service-category').value;
    const description = document.getElementById('service-description').value.trim();
    
    // Validation
    if (!name || name.length < 2) {
        showError('Название услуги должно содержать минимум 2 символа');
        return;
    }
    
    if (!duration || duration < 15 || duration > 480) {
        showError('Длительность должна быть от 15 до 480 минут');
        return;
    }
    
    if (!price || price < 0) {
        showError('Цена должна быть положительным числом');
        return;
    }
    
    // Show loading
    const saveBtn = document.getElementById('save-btn');
    const btnText = saveBtn.querySelector('.btn-text');
    const btnLoading = saveBtn.querySelector('.btn-loading');
    
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline-flex';
    saveBtn.disabled = true;
    
    try {
        const masterId = tg.initDataUnsafe?.user?.id;
        if (!masterId) {
            throw new Error('Не удалось получить ID пользователя');
        }

        const data = {
            mid: masterId,
            name,
            duration_minutes: duration,
            price,
            category: category || null,
            description: description || null
        };
        
        if (serviceId) {
            data.service_id = parseInt(serviceId);
        }
        
        const response = await fetch('/api/master/service/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка сохранения услуги');
        }
        
        const result = await response.json();
        
        // Success
        showSuccess(serviceId ? 'Услуга обновлена' : 'Услуга добавлена');
        closeServiceModal();
        
        // Reload services
        await loadServices();
        
    } catch (error) {
        console.error('Error saving service:', error);
        showError(error.message);
    } finally {
        // Hide loading
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        saveBtn.disabled = false;
    }
}

// Open Delete Modal
function openDeleteModal(serviceId, serviceName) {
    deleteServiceId = serviceId;
    document.getElementById('delete-service-name').textContent = serviceName;
    document.getElementById('delete-modal').style.display = 'flex';
}

// Close Delete Modal
function closeDeleteModal() {
    deleteServiceId = null;
    document.getElementById('delete-modal').style.display = 'none';
}

// Confirm Delete
async function confirmDelete() {
    if (!deleteServiceId) return;
    
    try {
        const masterId = tg.initDataUnsafe?.user?.id;
        if (!masterId) {
            throw new Error('Не удалось получить ID пользователя');
        }

        const response = await fetch('/api/master/service/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                mid: masterId,
                service_id: deleteServiceId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка удаления услуги');
        }
        
        // Success
        showSuccess('Услуга удалена');
        closeDeleteModal();
        
        // Reload services
        await loadServices();
        
    } catch (error) {
        console.error('Error deleting service:', error);
        showError(error.message);
    }
}

// Show Error Toast
function showError(message) {
    const toast = document.getElementById('error-toast');
    const messageEl = document.getElementById('error-message');
    
    messageEl.textContent = message;
    toast.style.display = 'flex';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, 5000);
}

// Show Success Toast
function showSuccess(message) {
    const toast = document.getElementById('success-toast');
    const messageEl = document.getElementById('success-message');
    
    messageEl.textContent = message;
    toast.style.display = 'flex';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
