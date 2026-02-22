/**
 * plan.js — AJAX interactions for the weekly training plan view
 */

const planUI = (() => {
    // Track loaded state per day for actual-activities dropdowns
    const actualsLoaded = {};

    // ── Sortable drag-to-reorder ──────────────────────────────────────────────
    // Each <tbody> is its own sortable group; dragging moves complete <tr> rows
    // so the planned-activity chip and match dropdown stay in sync automatically.
    function initSortables() {
        document.querySelectorAll('tbody.plan-day-body').forEach(tbody => {
            Sortable.create(tbody, {
                animation: 150,
                handle: '.plan-drag-cell',
                draggable: '.plan-item-row',
                ghostClass: 'sortable-ghost',
                onEnd() {
                    const dayDate = tbody.dataset.day;
                    const orderedIds = Array.from(tbody.querySelectorAll('.plan-item-row'))
                        .map(row => parseInt(row.dataset.id, 10));
                    fetch('/api/plan/reorder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ day_date: dayDate, ordered_ids: orderedIds }),
                    }).catch(err => console.error('Reorder failed', err));
                }
            });
        });
    }

    // ── Add form toggle ───────────────────────────────────────────────────────
    function toggleAddForm(dayDate) {
        const form = document.getElementById(`add-form-${dayDate}`);
        if (!form) return;
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }

    // ── Load extended types into a select (for Add form) ─────────────────────
    function _populateExtSelect(select, container, sportType, selectedId) {
        const types = (EXTENDED_TYPES_BY_SPORT[sportType] || []);
        select.innerHTML = '<option value="">— Any —</option>';
        types.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.custom_name;
            if (selectedId && String(t.id) === String(selectedId)) opt.selected = true;
            select.appendChild(opt);
        });
        container.style.display = types.length > 0 ? 'block' : 'none';
    }

    function loadExtendedTypes(sportType, dayDate) {
        const container = document.getElementById(`ext-type-container-${dayDate}`);
        const select = document.getElementById(`ext-type-${dayDate}`);
        if (!container || !select) return;
        if (!sportType) { container.style.display = 'none'; return; }
        _populateExtSelect(select, container, sportType, null);
    }

    // ── Submit Add form ───────────────────────────────────────────────────────
    function submitAdd(event, dayDate) {
        event.preventDefault();
        const form = event.target;
        const fd = new FormData(form);

        const distKm = parseFloat(fd.get('planned_distance_km'));
        const durationStr = fd.get('planned_duration_hhmm') || '';
        let durationSec = null;
        if (durationStr.includes(':')) {
            const [h, m] = durationStr.split(':').map(Number);
            durationSec = h * 3600 + m * 60;
        }

        const payload = {
            day_date: dayDate,
            sport_type: fd.get('sport_type') || null,
            extended_type_id: fd.get('extended_type_id') ? parseInt(fd.get('extended_type_id'), 10) : null,
            planned_distance: distKm > 0 ? distKm * 1000 : null,
            planned_duration: durationSec,
            notes: fd.get('notes') || null,
        };

        fetch('/api/plan/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            // Reload the page to reflect changes
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to save planned activity.'); });
    }

    // ── Delete ────────────────────────────────────────────────────────────────
    function deletePlan(planId, dayDate) {
        if (typeof confirmModal === 'function') {
            confirmModal(
                'Delete planned activity?',
                'This cannot be undone.',
                () => _doDelete(planId, dayDate)
            );
        } else if (window.confirm('Delete this planned activity?')) {
            _doDelete(planId, dayDate);
        }
    }

    function _doDelete(planId, dayDate) {
        fetch(`/api/plan/${planId}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.error) { alert(data.error); return; }
                window.location.reload();
            })
            .catch(err => { console.error(err); alert('Failed to delete.'); });
    }

    // ── Duplicate ─────────────────────────────────────────────────────────────
    function duplicate(planId, dayDate) {
        fetch(`/api/plan/${planId}/duplicate`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.error) { alert(data.error); return; }
                window.location.reload();
            })
            .catch(err => { console.error(err); alert('Failed to duplicate.'); });
    }

    // ── Match dropdown ────────────────────────────────────────────────────────
    function updateMatch(planId, activityId) {
        const payload = { matched_activity_id: activityId ? parseInt(activityId, 10) : null };
        fetch(`/api/plan/${planId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); }
            // Update matched badge inline
            const select = document.querySelector(`select[data-plan-id="${planId}"]`);
            if (select) {
                const badge = select.nextElementSibling;
                if (activityId) {
                    if (!badge || !badge.classList.contains('matched-badge')) {
                        const b = document.createElement('span');
                        b.className = 'badge bg-success matched-badge';
                        b.innerHTML = '<i class="bi bi-check-circle"></i>';
                        select.after(b);
                    }
                } else if (badge && badge.classList.contains('matched-badge')) {
                    badge.remove();
                }
            }
        })
        .catch(err => console.error(err));
    }

    // Lazy-load actual activities into dropdown on first focus
    function ensureActualsLoaded(selectEl, dayDate) {
        if (actualsLoaded[dayDate]) return;
        actualsLoaded[dayDate] = true;

        fetch(`/api/activities/?day_date=${dayDate}`)
            .then(r => r.json())
            .then(data => {
                const activities = data.activities || data;
                if (!Array.isArray(activities)) return;

                // Update all match dropdowns for this day
                document.querySelectorAll(`select[data-day="${dayDate}"]`).forEach(sel => {
                    const currentVal = sel.value;
                    // Keep existing options (already rendered server-side); just update if needed
                    // Remove old options after first blank one, then re-add
                    while (sel.options.length > 1) sel.remove(1);
                    activities.forEach(act => {
                        const opt = document.createElement('option');
                        opt.value = act.id;
                        const distKm = act.distance ? ` (${(act.distance/1000).toFixed(1)}km)` : '';
                        opt.textContent = act.name + distKm;
                        if (String(act.id) === String(currentVal)) opt.selected = true;
                        sel.appendChild(opt);
                    });
                    if (currentVal) sel.value = currentVal;
                });
            })
            .catch(err => console.error('Failed to load actual activities', err));
    }

    // ── Edit modal ────────────────────────────────────────────────────────────
    function openEditModal(item) {
        document.getElementById('edit-plan-id').value = item.id;
        document.getElementById('edit-plan-day').value = item.day_date;
        document.getElementById('edit-sport-type').value = item.sport_type || '';
        document.getElementById('edit-notes').value = item.notes || '';

        // Distance: stored in meters, display in km
        const distKm = item.planned_distance ? (item.planned_distance / 1000).toFixed(1) : '';
        document.getElementById('edit-distance').value = distKm;

        // Duration: stored in seconds, display as h:mm
        let durationStr = '';
        if (item.planned_duration) {
            const h = Math.floor(item.planned_duration / 3600);
            const m = Math.floor((item.planned_duration % 3600) / 60);
            durationStr = `${h}:${String(m).padStart(2, '0')}`;
        }
        document.getElementById('edit-duration').value = durationStr;

        // Load extended types for this sport
        loadEditExtendedTypes(item.sport_type, item.extended_type_id);

        const modal = new bootstrap.Modal(document.getElementById('editPlanModal'));
        modal.show();
    }

    function loadEditExtendedTypes(sportType, currentExtId) {
        const container = document.getElementById('edit-ext-container');
        const select = document.getElementById('edit-extended-type');
        if (!sportType) { container.style.display = 'none'; return; }
        _populateExtSelect(select, container, sportType, currentExtId);
    }

    function submitEdit(event) {
        event.preventDefault();
        const planId = document.getElementById('edit-plan-id').value;

        const distKm = parseFloat(document.getElementById('edit-distance').value);
        const durationStr = document.getElementById('edit-duration').value || '';
        let durationSec = null;
        if (durationStr.includes(':')) {
            const [h, m] = durationStr.split(':').map(Number);
            durationSec = h * 3600 + m * 60;
        }

        const extVal = document.getElementById('edit-extended-type').value;

        const payload = {
            sport_type: document.getElementById('edit-sport-type').value || null,
            extended_type_id: extVal ? parseInt(extVal, 10) : null,
            planned_distance: distKm > 0 ? distKm * 1000 : null,
            planned_duration: durationSec,
            notes: document.getElementById('edit-notes').value || null,
        };

        fetch(`/api/plan/${planId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            bootstrap.Modal.getInstance(document.getElementById('editPlanModal')).hide();
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to save changes.'); });
    }

    // ── Init ──────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        initSortables();
    });

    return {
        toggleAddForm,
        loadExtendedTypes,
        submitAdd,
        deletePlan,
        duplicate,
        updateMatch,
        ensureActualsLoaded,
        openEditModal,
        loadEditExtendedTypes,
        submitEdit,
    };
})();
