// Admin Analytics JavaScript
let tg = window.Telegram.WebApp;
let charts = {};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    tg.ready();
    tg.expand();
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
    // Setup event listeners
    setupTabNavigation();
    setupRefreshButton();
    
    // Load initial data
    loadAllData();
});

// Tab Navigation
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));
            
            // Add active class to clicked tab
            tab.classList.add('active');
            const tabName = tab.dataset.tab;
            document.getElementById(tabName).classList.add('active');
            
            // Load data for specific tab if needed
            loadTabData(tabName);
        });
    });
}

// Refresh Button
function setupRefreshButton() {
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.addEventListener('click', () => {
        loadAllData();
    });
}

// Load all analytics data
async function loadAllData() {
    showLoading(true);
    try {
        await Promise.all([
            loadGrowthMetrics(),
            loadRetentionData(),
            loadFunnelData()
        ]);
        hideError();
    } catch (error) {
        showError('Ошибка загрузки данных: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Load data for specific tab
async function loadTabData(tabName) {
    if (tabName === 'cohorts' && !document.getElementById('cohort-tbody').dataset.loaded) {
        await loadCohortData();
    }
}

// Load Growth Metrics
async function loadGrowthMetrics() {
    try {
        const response = await fetch('/api/admin/analytics/growth?period=month');
        const data = await response.json();
        
        document.getElementById('dau-value').textContent = data.dau;
        document.getElementById('wau-value').textContent = data.wau;
        document.getElementById('mau-value').textContent = data.mau;
        document.getElementById('growth-value').textContent = `${data.growth_rate >= 0 ? '+' : ''}${data.growth_rate}%`;
        document.getElementById('activation-value').textContent = `${data.activation_rate}%`;
        
        // Color code growth
        const growthEl = document.getElementById('growth-value');
        if (data.growth_rate > 0) {
            growthEl.style.color = '#4CAF50';
        } else if (data.growth_rate < 0) {
            growthEl.style.color = '#F44336';
        }
    } catch (error) {
        console.error('Error loading growth metrics:', error);
    }
}

// Load Retention Data
async function loadRetentionData() {
    try {
        const response = await fetch('/api/admin/analytics/retention');
        const data = await response.json();
        
        // Update retention stats
        document.getElementById('day1-retention').textContent = `${data.day1.toFixed(1)}%`;
        document.getElementById('day7-retention').textContent = `${data.day7.toFixed(1)}%`;
        document.getElementById('day30-retention').textContent = `${data.day30.toFixed(1)}%`;
        
        // Render retention overview chart
        renderRetentionOverviewChart(data);
        
        // Render detailed retention chart
        renderRetentionChart(data);
    } catch (error) {
        console.error('Error loading retention data:', error);
    }
}

// Render Retention Overview Chart (in Overview tab)
function renderRetentionOverviewChart(data) {
    const ctx = document.getElementById('retention-overview-chart');
    if (!ctx) return;
    
    if (charts.retentionOverview) {
        charts.retentionOverview.destroy();
    }
    
    charts.retentionOverview = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Day 1', 'Day 7', 'Day 30'],
            datasets: [{
                label: 'Retention %',
                data: [data.day1, data.day7, data.day30],
                backgroundColor: [
                    'rgba(76, 175, 80, 0.7)',
                    'rgba(255, 152, 0, 0.7)',
                    'rgba(244, 67, 54, 0.7)'
                ],
                borderColor: [
                    'rgb(76, 175, 80)',
                    'rgb(255, 152, 0)',
                    'rgb(244, 67, 54)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: value => value + '%'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: context => context.parsed.y.toFixed(1) + '%'
                    }
                }
            }
        }
    });
}

// Render Retention Chart (in Retention tab)
function renderRetentionChart(data) {
    const ctx = document.getElementById('retention-chart');
    if (!ctx) return;
    
    if (charts.retention) {
        charts.retention.destroy();
    }
    
    charts.retention = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Day 1', 'Day 7', 'Day 30'],
            datasets: [{
                label: 'Retention Rate',
                data: [data.day1, data.day7, data.day30],
                fill: true,
                backgroundColor: 'rgba(33, 150, 243, 0.2)',
                borderColor: 'rgb(33, 150, 243)',
                borderWidth: 3,
                tension: 0.4,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: value => value + '%'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: context => 'Retention: ' + context.parsed.y.toFixed(1) + '%'
                    }
                }
            }
        }
    });
}

// Load Cohort Data
async function loadCohortData() {
    try {
        const response = await fetch('/api/admin/analytics/cohorts?weeks=8');
        const data = await response.json();
        
        const tbody = document.getElementById('cohort-tbody');
        tbody.innerHTML = '';
        tbody.dataset.loaded = 'true';
        
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="no-data">Нет данных</td></tr>';
            return;
        }
        
        data.forEach(cohort => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${cohort.cohort_week}</td>
                <td>${cohort.registered}</td>
                <td class="cohort-cell" style="background-color: ${getCohortColor(100)}">${cohort.day0.toFixed(1)}%</td>
                <td class="cohort-cell" style="background-color: ${getCohortColor(cohort.day7 || 0)}">${cohort.day7 ? cohort.day7.toFixed(1) + '%' : '-'}</td>
                <td class="cohort-cell" style="background-color: ${getCohortColor(cohort.day14 || 0)}">${cohort.day14 ? cohort.day14.toFixed(1) + '%' : '-'}</td>
                <td class="cohort-cell" style="background-color: ${getCohortColor(cohort.day30 || 0)}">${cohort.day30 ? cohort.day30.toFixed(1) + '%' : '-'}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading cohort data:', error);
        const tbody = document.getElementById('cohort-tbody');
        tbody.innerHTML = '<tr><td colspan="6" class="error">Ошибка загрузки</td></tr>';
    }
}

// Get color for cohort cell (heat map)
function getCohortColor(percentage) {
    if (percentage >= 70) return 'rgba(76, 175, 80, 0.7)';
    if (percentage >= 50) return 'rgba(139, 195, 74, 0.6)';
    if (percentage >= 30) return 'rgba(255, 193, 7, 0.5)';
    if (percentage >= 10) return 'rgba(255, 152, 0, 0.4)';
    return 'rgba(244, 67, 54, 0.3)';
}

// Load Funnel Data
async function loadFunnelData() {
    try {
        const response = await fetch('/api/admin/analytics/funnel');
        const data = await response.json();
        
        // Update funnel bars width and values
        updateFunnelStage('registered', data.registered);
        updateFunnelStage('onboarded', data.onboarded);
        updateFunnelStage('first-service', data.first_service);
        updateFunnelStage('first-booking', data.first_booking);
        updateFunnelStage('paid', data.paid);
        
        // Update paid conversion in overview
        document.getElementById('paid-conversion-value').textContent = `${data.paid.rate.toFixed(1)}%`;
        
        // Render funnel chart
        renderFunnelChart(data);
    } catch (error) {
        console.error('Error loading funnel data:', error);
    }
}

// Update funnel stage
function updateFunnelStage(stageName, stageData) {
    const bar = document.getElementById(`${stageName}-bar`);
    const valueEl = document.getElementById(`${stageName}-value`);
    
    if (bar && valueEl) {
        bar.style.width = `${stageData.rate}%`;
        valueEl.textContent = `${stageData.count} (${stageData.rate.toFixed(1)}%)`;
    }
}

// Render Funnel Chart
function renderFunnelChart(data) {
    const ctx = document.getElementById('funnel-chart');
    if (!ctx) return;
    
    if (charts.funnel) {
        charts.funnel.destroy();
    }
    
    charts.funnel = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Registered', 'Onboarded', 'First Service', 'First Booking', 'Paid'],
            datasets: [{
                label: 'Users',
                data: [
                    data.registered.count,
                    data.onboarded.count,
                    data.first_service.count,
                    data.first_booking.count,
                    data.paid.count
                ],
                backgroundColor: [
                    'rgba(33, 150, 243, 0.7)',
                    'rgba(76, 175, 80, 0.7)',
                    'rgba(255, 193, 7, 0.7)',
                    'rgba(255, 152, 0, 0.7)',
                    'rgba(156, 39, 176, 0.7)'
                ],
                borderColor: [
                    'rgb(33, 150, 243)',
                    'rgb(76, 175, 80)',
                    'rgb(255, 193, 7)',
                    'rgb(255, 152, 0)',
                    'rgb(156, 39, 176)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: context => {
                            const rates = [
                                data.registered.rate,
                                data.onboarded.rate,
                                data.first_service.rate,
                                data.first_booking.rate,
                                data.paid.rate
                            ];
                            return `${context.parsed.x} users (${rates[context.dataIndex].toFixed(1)}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Show loading overlay
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = show ? 'flex' : 'none';
}

// Show error message
function showError(message) {
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    setTimeout(() => {
        errorEl.style.display = 'none';
    }, 5000);
}

// Hide error message
function hideError() {
    const errorEl = document.getElementById('error-message');
    errorEl.style.display = 'none';
}
