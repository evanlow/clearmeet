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
    
    // Word counter for transcript textarea
    const transcriptTextarea = document.getElementById('transcript_text');
    const wordCountDisplay = document.getElementById('word-count');
    
    if (transcriptTextarea && wordCountDisplay) {
        function countWords(text) {
            // Trim whitespace and split by whitespace
            const words = text.trim().split(/\s+/);
            // Return 0 if only empty string, otherwise return word count
            return text.trim().length === 0 ? 0 : words.length;
        }
        
        function updateWordCount() {
            const text = transcriptTextarea.value;
            const wordCount = countWords(text);
            const recommendedWords = 50;
            
            // Update display text
            wordCountDisplay.textContent = `${wordCount} word${wordCount !== 1 ? 's' : ''}`;
            
            // Update styling based on word count (50+ is recommended, 10+ is minimum)
            if (wordCount >= recommendedWords) {
                wordCountDisplay.classList.remove('word-count-insufficient');
                wordCountDisplay.classList.add('word-count-sufficient');
            } else if (wordCount >= 10) {
                // Between 10-49 words: acceptable but show as warning
                wordCountDisplay.classList.remove('word-count-sufficient');
                wordCountDisplay.classList.add('word-count-insufficient');
            } else {
                // Less than 10 words: too short
                wordCountDisplay.classList.remove('word-count-sufficient');
                wordCountDisplay.classList.add('word-count-insufficient');
            }
        }
        
        // Update on input
        transcriptTextarea.addEventListener('input', updateWordCount);
        
        // Update on page load (in case there's pre-filled content)
        updateWordCount();
    }
    
    // Handle tab switching to show/hide word counter
    const wordCounter = document.querySelector('.word-counter');
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            
            // Show word counter only on text tab, hide on audio tab
            if (wordCounter) {
                if (tabId === 'text-tab') {
                    wordCounter.style.display = 'flex';
                } else {
                    wordCounter.style.display = 'none';
                }
            }
        });
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
