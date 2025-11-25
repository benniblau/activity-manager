// Pain scale selector functionality for day feeling modals
document.querySelectorAll('.pain-scale-selector').forEach(selector => {
    const inputId = selector.dataset.input;
    const hiddenInput = document.getElementById(inputId);

    selector.querySelectorAll('.pain-scale-option').forEach(option => {
        option.addEventListener('click', () => {
            selector.querySelectorAll('.pain-scale-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            option.classList.add('selected');
            hiddenInput.value = option.dataset.value;
        });
    });
});

// Day row expand/collapse functionality
document.querySelectorAll('.day-row-collapsed').forEach(collapsedRow => {
    const dayId = collapsedRow.dataset.day;
    const expandedRow = document.querySelector(`.day-row-expanded[data-day="${dayId}"]`);

    collapsedRow.addEventListener('click', (e) => {
        // Don't toggle if clicking on modal triggers or activity links
        if (e.target.closest('[data-bs-toggle="modal"]') || e.target.closest('a')) {
            return;
        }

        // Toggle the expanded state
        if (collapsedRow.classList.contains('expanded')) {
            // Collapse
            collapsedRow.classList.remove('expanded');
            collapsedRow.style.display = 'table-row';
            expandedRow.style.display = 'none';
        } else {
            // Expand
            collapsedRow.classList.add('expanded');
            collapsedRow.style.display = 'none';
            expandedRow.style.display = 'table-row';
        }
    });

    // Click on expanded row's date cell to collapse
    expandedRow.addEventListener('click', (e) => {
        // Only collapse if clicking on the date header or areas without modals/links
        if (e.target.closest('[data-bs-toggle="modal"]') || e.target.closest('a')) {
            return;
        }

        // If clicking on the date cell, collapse
        if (e.target.closest('.day-header')) {
            collapsedRow.classList.remove('expanded');
            collapsedRow.style.display = 'table-row';
            expandedRow.style.display = 'none';
        }
    });
});
