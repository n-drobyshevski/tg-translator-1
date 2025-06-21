function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        // Focus the first focusable element
        const focusableElements = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusableElements.length) {
            focusableElements[0].focus();
        }
        // Prevent scrolling of the background
        document.body.style.overflow = 'hidden';
    }
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        // Restore scrolling
        document.body.style.overflow = '';
    }
}

function handleModalOverlayClick(event, modalId) {
    if (event.target.id === modalId) {
        hideModal(modalId);
    }
}
