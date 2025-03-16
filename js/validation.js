const validateInput = (input) => {
    const value = input.value.trim();
    
    if (!value) {
        showError(input, 'Este campo es requerido');
        return false;
    }
    
    if (input.type === 'email') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            showError(input, 'Email inválido');
            return false;
        }
    }
    
    if (input.type === 'number') {
        if (isNaN(value) || value < 0) {
            showError(input, 'Número inválido');
            return false;
        }
    }
    
    removeError(input);
    return true;
};

const showError = (input, message) => {
    const errorDiv = input.nextElementSibling?.classList.contains('error-message') 
        ? input.nextElementSibling 
        : document.createElement('div');
    
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    if (!input.nextElementSibling?.classList.contains('error-message')) {
        input.parentNode.insertBefore(errorDiv, input.nextSibling);
    }
    
    input.classList.add('error');
};

const removeError = (input) => {
    const errorDiv = input.nextElementSibling;
    if (errorDiv?.classList.contains('error-message')) {
        errorDiv.remove();
    }
    input.classList.remove('error');
};