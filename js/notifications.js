// Agregar al inicio del archivo
const showNotification = (message, type = 'info') => {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
};

// Reemplazar los alert por:
showNotification('Producto agregado al carrito', 'success');
showNotification('Error al procesar la orden', 'error');