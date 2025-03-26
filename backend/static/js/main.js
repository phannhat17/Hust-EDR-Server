/**
 * Main JavaScript file for EDR System
 */

// Track active page to highlight in navigation
document.addEventListener('DOMContentLoaded', function() {
    // Set active navigation link
    setActiveNav();
    
    // Initialize Bootstrap tooltips
    initTooltips();
    
    // Add any global event listeners
    setupGlobalListeners();
});

/**
 * Set active navigation link based on current URL
 */
function setActiveNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        
        const href = link.getAttribute('href');
        if (href === currentPath || 
            (href !== '/' && currentPath.startsWith(href))) {
            link.classList.add('active');
        }
        
        // Special case for home page
        if (currentPath === '/' && href === '/') {
            link.classList.add('active');
        }
    });
}

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Setup global event listeners
 */
function setupGlobalListeners() {
    // Example: Confirm dangerous actions
    document.querySelectorAll('.confirm-action').forEach(element => {
        element.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm-message') || 'Are you sure?')) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Format timestamp to local date/time string
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Formatted date/time
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch (e) {
        console.error('Error formatting timestamp:', e);
        return timestamp;
    }
}

/**
 * Format alert status for display
 * @param {string} status - Alert status code
 * @returns {string} Formatted status text
 */
function formatStatus(status) {
    if (!status) return 'Unknown';
    
    return status
        .replace('_', ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Get appropriate CSS class based on alert status
 * @param {string} status - Alert status code
 * @returns {string} CSS class name
 */
function getStatusClass(status) {
    switch (status) {
        case 'new': return 'bg-warning';
        case 'in_review': return 'bg-info';
        case 'in_progress': return 'bg-primary';
        case 'resolved': return 'bg-success';
        case 'false_positive': return 'bg-secondary';
        default: return 'bg-secondary';
    }
}

/**
 * Show toast notification
 * @param {string} message - Notification message
 * @param {string} type - Notification type (success, error, warning, info)
 */
function showToast(message, type = 'info') {
    // Check if toast container exists, create it if not
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${getToastBgClass(type)} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Create toast content
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add toast to container
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

/**
 * Get appropriate background class for toast
 * @param {string} type - Notification type
 * @returns {string} Background class
 */
function getToastBgClass(type) {
    switch (type.toLowerCase()) {
        case 'success': return 'success';
        case 'error': return 'danger';
        case 'warning': return 'warning';
        case 'info': return 'info';
        default: return 'secondary';
    }
}

/**
 * Handle API errors and display appropriate message
 * @param {Error} error - Error object from API call
 * @param {string} defaultMessage - Default error message
 */
function handleApiError(error, defaultMessage = 'An error occurred') {
    console.error('API Error:', error);
    
    let message = defaultMessage;
    
    if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        message = error.response.data?.error || 
                 `Error ${error.response.status}: ${error.response.statusText}`;
    } else if (error.request) {
        // The request was made but no response was received
        message = 'No response received from server. Please check your connection.';
    } else {
        // Something happened in setting up the request that triggered an Error
        message = error.message || defaultMessage;
    }
    
    showToast(message, 'error');
} 