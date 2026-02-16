// Edit type button handler
document.querySelectorAll('.edit-type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const base = btn.dataset.base;
        const name = btn.dataset.name;
        const description = btn.dataset.description;
        const color = btn.dataset.color;
        const order = btn.dataset.order;

        document.getElementById('editTypeForm').action = `/admin/types/${id}`;
        document.getElementById('edit_base_sport_type').value = base;
        document.getElementById('edit_custom_name').value = name;
        document.getElementById('edit_description').value = description;
        document.getElementById('edit_color_class').value = color;
        document.getElementById('edit_display_order').value = order;

        const modal = new bootstrap.Modal(document.getElementById('editTypeModal'));
        modal.show();
    });
});

// Delete type button handler
document.querySelectorAll('.delete-type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;

        if (confirm(`Are you sure you want to delete "${name}"? This will not delete activities using this type, but they will fall back to the base type.`)) {
            fetch(`/admin/types/${id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    location.reload();
                } else if (data.error) {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                alert('Error deleting type: ' + error);
            });
        }
    });
});
