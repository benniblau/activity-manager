// Activity type selector — auto-initializes all instances via data attribute
document.querySelectorAll('[data-activity-type-selector]').forEach(container => {
    const name = container.dataset.activityTypeSelector;
    const selector = document.getElementById(name);
    const extendedInput = document.getElementById(name + '_extended_type_id');
    const sportInput = document.getElementById(name + '_sport_type');

    if (selector && extendedInput && sportInput) {
        selector.addEventListener('change', function() {
            const selected = this.options[this.selectedIndex];
            const value = this.value;

            if (value.startsWith('ext-')) {
                extendedInput.value = selected.dataset.extendedId || '';
                sportInput.value = '';
            } else if (value.startsWith('sport-')) {
                extendedInput.value = '';
                sportInput.value = selected.dataset.sportType || '';
            } else {
                extendedInput.value = '';
                sportInput.value = '';
            }
        });

        // Trigger on page load if there's a selected value
        if (selector.value) {
            selector.dispatchEvent(new Event('change'));
        }
    }
});
