// Global function to show alert modal
function showAlert(message, type = 'error') {
    const modal = new bootstrap.Modal(document.getElementById('alertModal'));
    const titleElement = document.getElementById('alertModalTitle');
    const iconElement = document.getElementById('alertModalIcon');
    const bodyElement = document.getElementById('alertModalBody');
    const modalHeader = document.querySelector('#alertModal .modal-header');

    // Set message
    bodyElement.textContent = message;

    // Set icon and color based on type
    if (type === 'error') {
        titleElement.textContent = 'Error';
        iconElement.className = 'bi bi-exclamation-triangle-fill text-danger';
        modalHeader.className = 'modal-header';
    } else if (type === 'success') {
        titleElement.textContent = 'Success';
        iconElement.className = 'bi bi-check-circle-fill text-success';
        modalHeader.className = 'modal-header';
    } else if (type === 'warning') {
        titleElement.textContent = 'Warning';
        iconElement.className = 'bi bi-exclamation-circle-fill text-warning';
        modalHeader.className = 'modal-header';
    } else {
        titleElement.textContent = 'Notice';
        iconElement.className = 'bi bi-info-circle-fill text-info';
        modalHeader.className = 'modal-header';
    }

    modal.show();
}

// Global function to show confirmation modal
function showConfirm(message, onConfirm) {
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const bodyElement = document.getElementById('confirmModalBody');
    const confirmButton = document.getElementById('confirmModalOk');

    // Set message
    bodyElement.textContent = message;

    // Remove any existing event listeners by cloning the button
    const newConfirmButton = confirmButton.cloneNode(true);
    confirmButton.parentNode.replaceChild(newConfirmButton, confirmButton);

    // Add new event listener for this confirmation
    newConfirmButton.addEventListener('click', () => {
        modal.hide();
        if (onConfirm) {
            onConfirm();
        }
    });

    modal.show();
}
