// Planning view JavaScript

// Convert km to meters and minutes to seconds for form submission
function setupUnitConversions(prefix) {
    const distanceKmInput = document.getElementById(`${prefix}_distance_km`);
    const distanceMetersInput = document.getElementById(`${prefix}_distance_meters`);
    const durationMinInput = document.getElementById(`${prefix}_duration_min`);
    const durationSecondsInput = document.getElementById(`${prefix}_duration_seconds`);

    if (distanceKmInput && distanceMetersInput) {
        distanceKmInput.addEventListener('input', () => {
            const km = parseFloat(distanceKmInput.value);
            distanceMetersInput.value = km ? Math.round(km * 1000) : '';
        });
    }

    if (durationMinInput && durationSecondsInput) {
        durationMinInput.addEventListener('input', () => {
            const minutes = parseFloat(durationMinInput.value);
            durationSecondsInput.value = minutes ? Math.round(minutes * 60) : '';
        });
    }
}

// Setup activity type selector to populate hidden fields
function setupTypeSelector(selectorId, extendedIdField, sportTypeField) {
    const selector = document.getElementById(selectorId);
    const extendedInput = document.getElementById(extendedIdField);
    const sportInput = document.getElementById(sportTypeField);

    if (selector) {
        selector.addEventListener('change', () => {
            const selected = selector.selectedOptions[0];
            if (selected.dataset.extendedId) {
                extendedInput.value = selected.dataset.extendedId;
                sportInput.value = '';
            } else if (selected.dataset.sportType) {
                sportInput.value = selected.dataset.sportType;
                extendedInput.value = '';
            }
        });
    }
}

// Initialize add planned activity form
setupUnitConversions('add');
setupTypeSelector('add_type_selector', 'add_extended_type_id', 'add_sport_type');

// Initialize edit planned activity form
setupUnitConversions('edit');
setupTypeSelector('edit_type_selector', 'edit_extended_type_id', 'edit_sport_type');

// Add form submission handler - ensure conversions happen before submit
document.getElementById('addPlannedForm').addEventListener('submit', (e) => {
    // Convert distance km to meters
    const distanceKm = document.getElementById('add_distance_km').value;
    if (distanceKm) {
        document.getElementById('add_distance_meters').value = Math.round(parseFloat(distanceKm) * 1000);
    }

    // Convert duration minutes to seconds
    const durationMin = document.getElementById('add_duration_min').value;
    if (durationMin) {
        document.getElementById('add_duration_seconds').value = Math.round(parseFloat(durationMin) * 60);
    }

    // Let form submit normally
});

// Edit form submission handler - ensure conversions happen before submit
document.getElementById('editPlannedForm').addEventListener('submit', (e) => {
    // Convert distance km to meters
    const distanceKm = document.getElementById('edit_distance_km').value;
    if (distanceKm) {
        document.getElementById('edit_distance_meters').value = Math.round(parseFloat(distanceKm) * 1000);
    }

    // Convert duration minutes to seconds
    const durationMin = document.getElementById('edit_duration_min').value;
    if (durationMin) {
        document.getElementById('edit_duration_seconds').value = Math.round(parseFloat(durationMin) * 60);
    }

    // Let form submit normally
});

// Add for day button - pre-populate date
document.querySelectorAll('.add-planned-for-day').forEach(btn => {
    btn.addEventListener('click', () => {
        const date = btn.dataset.date;
        document.getElementById('add_date').value = date;
        const modal = new bootstrap.Modal(document.getElementById('addPlannedActivityModal'));
        modal.show();
    });
});

// Edit planned activity button
document.querySelectorAll('.edit-planned-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();

        const id = btn.dataset.id;
        const date = btn.dataset.date;
        const name = btn.dataset.name;
        const description = btn.dataset.description;
        const extendedId = btn.dataset.extendedId;
        const sportType = btn.dataset.sportType;
        const distance = btn.dataset.distance;
        const duration = btn.dataset.duration;
        const notes = btn.dataset.notes;
        const intensity = btn.dataset.intensity;

        // Set form action
        document.getElementById('editPlannedForm').action = `/planning/activity/${id}`;

        // Populate fields
        document.getElementById('edit_date').value = date;
        document.getElementById('edit_name').value = name;
        document.getElementById('edit_description').value = description;
        document.getElementById('edit_notes').value = notes;
        document.getElementById('edit_intensity').value = intensity;

        // Set activity type
        const typeSelector = document.getElementById('edit_type_selector');
        if (extendedId) {
            typeSelector.value = `ext-${extendedId}`;
            document.getElementById('edit_extended_type_id').value = extendedId;
            document.getElementById('edit_sport_type').value = '';
        } else if (sportType) {
            typeSelector.value = `sport-${sportType}`;
            document.getElementById('edit_sport_type').value = sportType;
            document.getElementById('edit_extended_type_id').value = '';
        }

        // Set distance and duration (convert from meters/seconds to km/minutes)
        if (distance) {
            const km = parseFloat(distance) / 1000;
            document.getElementById('edit_distance_km').value = km.toFixed(1);
            document.getElementById('edit_distance_meters').value = distance;
        }
        if (duration) {
            const minutes = Math.round(parseFloat(duration) / 60);
            document.getElementById('edit_duration_min').value = minutes;
            document.getElementById('edit_duration_seconds').value = duration;
        }

        const modal = new bootstrap.Modal(document.getElementById('editPlannedActivityModal'));
        modal.show();
    });
});

// Delete planned activity button
document.querySelectorAll('.delete-planned-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();

        const id = btn.dataset.id;
        const name = btn.dataset.name;

        showConfirm(`Are you sure you want to delete "${name}"?`, () => {
            fetch(`/planning/activity/${id}`, {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'}
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    location.reload();
                } else if (data.error) {
                    showAlert('Error: ' + data.error, 'error');
                }
            })
            .catch(error => {
                showAlert('Error deleting planned activity: ' + error, 'error');
            });
        });
    });
});

// Copy planned activity button
let currentCopyId = null;

document.querySelectorAll('.copy-planned-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentCopyId = btn.dataset.id;

        // Reset form
        const container = document.getElementById('copy_dates_container');
        container.innerHTML = `
            <div class="input-group mb-2">
                <input type="date" class="form-control copy-date-input" required>
                <button type="button" class="btn btn-outline-danger remove-date-btn">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;

        const modal = new bootstrap.Modal(document.getElementById('copyPlannedActivityModal'));
        modal.show();
    });
});

// Add copy date button
document.getElementById('add_copy_date_btn').addEventListener('click', () => {
    const container = document.getElementById('copy_dates_container');
    const newInput = document.createElement('div');
    newInput.className = 'input-group mb-2';
    newInput.innerHTML = `
        <input type="date" class="form-control copy-date-input" required>
        <button type="button" class="btn btn-outline-danger remove-date-btn">
            <i class="bi bi-trash"></i>
        </button>
    `;
    container.appendChild(newInput);
});

// Remove date button (event delegation)
document.getElementById('copy_dates_container').addEventListener('click', (e) => {
    if (e.target.closest('.remove-date-btn')) {
        const container = document.getElementById('copy_dates_container');
        if (container.children.length > 1) {
            e.target.closest('.input-group').remove();
        } else {
            showAlert('At least one date is required', 'warning');
        }
    }
});

// Copy form submission
document.getElementById('copyPlannedForm').addEventListener('submit', (e) => {
    e.preventDefault();

    const dateInputs = document.querySelectorAll('.copy-date-input');
    const targetDates = Array.from(dateInputs).map(input => input.value).filter(val => val);

    if (targetDates.length === 0) {
        showAlert('Please select at least one date', 'warning');
        return;
    }

    fetch(`/planning/activity/${currentCopyId}/copy`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({target_dates: targetDates})
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            location.reload();
        } else if (data.error) {
            showAlert('Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Error copying planned activity: ' + error, 'error');
    });
});

// Match activity button
let currentMatchPlannedId = null;
let currentMatchDate = null;

document.querySelectorAll('.match-activity-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();

        currentMatchPlannedId = btn.dataset.plannedId;
        currentMatchDate = btn.dataset.date;

        // Get planned activity details from button data attributes
        const plannedName = btn.dataset.plannedName;
        const plannedType = btn.dataset.plannedType;
        const plannedDistance = btn.dataset.plannedDistance;
        const plannedDuration = btn.dataset.plannedDuration;

        // Populate the planned activity display
        const plannedDisplay = document.getElementById('match_planned_display');
        plannedDisplay.innerHTML = `
            <div class="fw-bold">${plannedName}</div>
            <div class="small text-muted">
                ${plannedType}
                ${plannedDistance ? `• ${(plannedDistance / 1000).toFixed(1)} km` : ''}
                ${plannedDuration ? `• ${Math.round(plannedDuration / 60)} min` : ''}
            </div>
        `;

        // Fetch actual activities for this date
        fetch(`/api/activities/?day_date=${currentMatchDate}`)
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById('match_activity_select');
                select.innerHTML = '<option value="">-- Select Activity --</option>';

                // API returns {count, activities} object
                const activities = data.activities || [];

                activities.forEach(activity => {
                    const option = document.createElement('option');
                    option.value = activity.id;
                    option.textContent = `${activity.name} (${activity.sport_type})`;
                    select.appendChild(option);
                });

                const modal = new bootstrap.Modal(document.getElementById('matchActivityModal'));
                modal.show();
            })
            .catch(error => {
                showAlert('Error loading activities: ' + error, 'error');
            });
    });
});

// Confirm match button
document.getElementById('confirm_match_btn').addEventListener('click', () => {
    const activityId = document.getElementById('match_activity_select').value;

    if (!activityId) {
        showAlert('Please select an activity', 'warning');
        return;
    }

    fetch(`/planning/activity/${currentMatchPlannedId}/match/${activityId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            location.reload();
        } else if (data.error) {
            showAlert('Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Error matching activities: ' + error, 'error');
    });
});

// Unmatch button
document.querySelectorAll('.unmatch-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();

        const id = btn.dataset.id;

        showConfirm('Are you sure you want to unmatch this activity?', () => {
            fetch(`/planning/activity/${id}/match`, {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'}
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    location.reload();
                } else if (data.error) {
                    showAlert('Error: ' + data.error, 'error');
                }
            })
            .catch(error => {
                showAlert('Error unmatching activity: ' + error, 'error');
            });
        });
    });
});
