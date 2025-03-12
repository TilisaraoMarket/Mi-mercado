const lazyLoadImages = () => {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });

    const lazyImages = document.querySelectorAll('img.lazy');
    lazyImages.forEach(img => imageObserver.observe(img));
};

// Modificar la función que crea las tarjetas de productos
const createProductCard = (producto) => {
    return `
        <div class="product-card">
            <img class="lazy product-image" 
                 data-src="${producto.imagen_url}" 
                 src="placeholder.jpg" 
                 alt="${producto.titulo}">
            <!-- resto del código -->
        </div>
    `;
};