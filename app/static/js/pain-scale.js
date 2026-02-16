// Pain scale selector functionality (shared across all pages)
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
