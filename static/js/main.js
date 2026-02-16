// ClearMeet JavaScript - Minimal client-side functionality

// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});

// Utility function for element visibility
function toggleVisibility(elementId, show) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = show ? 'block' : 'none';
    }
}

// Form validation helper
function validateForm(formId, validationRules) {
    const form = document.getElementById(formId);
    if (!form) return true;
    
    let isValid = true;
    const errors = [];
    
    for (const [field, rule] of Object.entries(validationRules)) {
        const input = form.querySelector(`[name="${field}"]`);
        if (!input) continue;
        
        const value = input.value.trim();
        
        if (rule.required && !value) {
            errors.push(`${rule.label} is required`);
            input.classList.add('error');
            isValid = false;
        } else {
            input.classList.remove('error');
        }
        
        if (rule.minLength && value.length < rule.minLength) {
            errors.push(`${rule.label} must be at least ${rule.minLength} characters`);
            isValid = false;
        }
    }
    
    if (!isValid) {
        alert('Please fix the following errors:\n\n' + errors.join('\n'));
    }
    
    return isValid;
}

// Console log helper for debugging
function debug(message, data = null) {
    if (console && console.log) {
        if (data) {
            console.log('[ClearMeet]', message, data);
        } else {
            console.log('[ClearMeet]', message);
        }
    }
}

// Export for use in inline scripts
window.ClearMeet = {
    toggleVisibility,
    validateForm,
    debug
};
