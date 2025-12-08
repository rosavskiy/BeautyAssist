// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Animate elements on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fade-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all cards and sections
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll(
        '.feature-card, .problem-card, .step-card, .testimonial-card, .pricing-card, .faq-item'
    );
    
    animatedElements.forEach(el => {
        observer.observe(el);
    });
});

// Track button clicks (for analytics)
function trackEvent(eventName, eventData) {
    // Yandex.Metrika
    if (typeof ym !== 'undefined') {
        ym(XXXXXXXX, 'reachGoal', eventName, eventData);
    }
    
    // Google Analytics (если добавите)
    if (typeof gtag !== 'undefined') {
        gtag('event', eventName, eventData);
    }
    
    console.log('Event tracked:', eventName, eventData);
}

// Track CTA clicks
document.querySelectorAll('.btn-primary, .btn-secondary').forEach(button => {
    button.addEventListener('click', (e) => {
        const buttonText = e.target.textContent.trim();
        const buttonLocation = e.target.closest('section')?.className || 'unknown';
        
        trackEvent('cta_click', {
            button_text: buttonText,
            location: buttonLocation
        });
    });
});

// Track pricing card interactions
document.querySelectorAll('.pricing-card').forEach(card => {
    card.addEventListener('mouseenter', (e) => {
        const planName = e.currentTarget.querySelector('h3')?.textContent;
        trackEvent('pricing_hover', { plan: planName });
    });
});

// FAQ accordion (optional enhancement)
document.querySelectorAll('.faq-item').forEach(item => {
    item.addEventListener('click', () => {
        item.classList.toggle('active');
    });
});

// Mobile menu toggle (если понадобится)
const mobileMenuButton = document.querySelector('.mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

if (mobileMenuButton) {
    mobileMenuButton.addEventListener('click', () => {
        navLinks.classList.toggle('active');
    });
}

// Lazy load images
if ('loading' in HTMLImageElement.prototype) {
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
        img.src = img.dataset.src;
    });
} else {
    // Fallback for browsers that don't support lazy loading
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lazysizes/5.3.2/lazysizes.min.js';
    document.body.appendChild(script);
}

// Add current year to footer
const yearElement = document.querySelector('.footer-bottom p');
if (yearElement) {
    const currentYear = new Date().getFullYear();
    yearElement.innerHTML = yearElement.innerHTML.replace('2025', currentYear);
}

// Handle video placeholder click
document.querySelector('.video-placeholder')?.addEventListener('click', function() {
    // Replace with actual video embed or open modal
    trackEvent('video_play', { location: 'solution_section' });
    
    // Example: Replace placeholder with YouTube embed
    // this.innerHTML = '<iframe width="100%" height="100%" src="https://www.youtube.com/embed/VIDEO_ID" frameborder="0" allowfullscreen></iframe>';
    
    alert('Здесь будет демо-видео BeautyAssist');
});

// Sticky header on scroll
let lastScroll = 0;
const nav = document.querySelector('.nav');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 100) {
        nav.style.position = 'sticky';
        nav.style.top = '0';
        nav.style.background = 'rgba(255, 255, 255, 0.95)';
        nav.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        nav.style.transition = 'all 0.3s ease';
    } else {
        nav.style.position = 'static';
        nav.style.background = 'transparent';
        nav.style.boxShadow = 'none';
    }
    
    lastScroll = currentScroll;
});

// Price calculator (optional)
function calculateAnnualSavings(currentCRM, beautyAssistPlan) {
    const prices = {
        yclients: 1690 * 12, // 20,280₽/год
        dikidi: 990 * 12,    // 11,880₽/год
        beautyassist_monthly: 199 * 12,    // 2,388₽/год
        beautyassist_quarterly: 499 * 4,   // 1,996₽/год
        beautyassist_yearly: 1699          // 1,699₽/год
    };
    
    return prices[currentCRM] - prices[beautyAssistPlan];
}

// Log savings for user
console.log('💰 Экономия при переходе с Yclients:', calculateAnnualSavings('yclients', 'beautyassist_yearly'), '₽/год');
console.log('💰 Экономия при переходе с Dikidi:', calculateAnnualSavings('dikidi', 'beautyassist_yearly'), '₽/год');

// Handle form submissions (if you add lead forms)
const forms = document.querySelectorAll('form');
forms.forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        trackEvent('form_submit', { form_name: form.id || 'unnamed' });
        
        // Send to your backend
        try {
            const response = await fetch('/api/leads', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                alert('Спасибо! Мы свяжемся с вами в ближайшее время.');
                form.reset();
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            alert('Произошла ошибка. Попробуйте позже или напишите нам в Telegram.');
        }
    });
});

// Add UTM parameters tracking
const urlParams = new URLSearchParams(window.location.search);
const utmSource = urlParams.get('utm_source');
const utmMedium = urlParams.get('utm_medium');
const utmCampaign = urlParams.get('utm_campaign');

if (utmSource || utmMedium || utmCampaign) {
    trackEvent('landing_visit', {
        utm_source: utmSource,
        utm_medium: utmMedium,
        utm_campaign: utmCampaign
    });
    
    // Save UTM to sessionStorage for tracking conversions
    sessionStorage.setItem('utm_data', JSON.stringify({
        source: utmSource,
        medium: utmMedium,
        campaign: utmCampaign
    }));
}

// Exit intent popup (optional - показать оффер при попытке уйти)
let exitIntentShown = false;

document.addEventListener('mouseleave', (e) => {
    if (e.clientY < 10 && !exitIntentShown) {
        exitIntentShown = true;
        
        trackEvent('exit_intent', { location: 'page_top' });
        
        // Show modal or special offer
        // For now, just log
        console.log('🚪 Пользователь пытается уйти - можно показать специальное предложение');
        
        // Example: show discount popup
        // showExitPopup('Получите скидку 20% на первый месяц!');
    }
});

// Performance monitoring
window.addEventListener('load', () => {
    if ('performance' in window) {
        const perfData = window.performance.timing;
        const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
        
        trackEvent('page_load', {
            load_time: pageLoadTime,
            page_url: window.location.pathname
        });
        
        console.log('⚡ Время загрузки страницы:', pageLoadTime, 'мс');
    }
});

// A/B testing helper (optional)
function getVariant() {
    const variants = ['A', 'B'];
    const stored = localStorage.getItem('ab_variant');
    
    if (stored) {
        return stored;
    }
    
    const variant = variants[Math.floor(Math.random() * variants.length)];
    localStorage.setItem('ab_variant', variant);
    
    return variant;
}

// Example: test different headlines
const variant = getVariant();
console.log('🧪 A/B тест вариант:', variant);

// Track scroll depth
let maxScroll = 0;
const scrollMilestones = [25, 50, 75, 100];
const reachedMilestones = new Set();

window.addEventListener('scroll', () => {
    const scrollPercent = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
    
    if (scrollPercent > maxScroll) {
        maxScroll = scrollPercent;
    }
    
    scrollMilestones.forEach(milestone => {
        if (scrollPercent >= milestone && !reachedMilestones.has(milestone)) {
            reachedMilestones.add(milestone);
            trackEvent('scroll_depth', { depth: milestone });
        }
    });
});

// Log when user leaves page
window.addEventListener('beforeunload', () => {
    trackEvent('page_exit', {
        max_scroll: Math.round(maxScroll),
        time_on_page: Math.round((Date.now() - performance.timing.navigationStart) / 1000)
    });
});
