/**
 * training-templates.js — Admin UI for training template CRUD
 */

const tmpl = (() => {

    // ── Pace / duration helpers ───────────────────────────────────────────────

    /** "5:30" → 330 seconds, returns null on invalid input */
    function mssToSeconds(str) {
        if (!str || !str.includes(':')) return null;
        const [m, s] = str.split(':').map(Number);
        if (isNaN(m) || isNaN(s)) return null;
        return m * 60 + s;
    }

    /** 330 → "5:30" */
    function secondsToMss(sec) {
        if (!sec) return '';
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    // ── Templates list page ───────────────────────────────────────────────────

    function submitAdd(event) {
        event.preventDefault();
        const form = event.target;
        const fd = new FormData(form);
        const errEl = document.getElementById('addTemplateError');
        errEl.style.display = 'none';

        const payload = {
            name: fd.get('name'),
            sport_type: fd.get('sport_type') || null,
            description: fd.get('description') || null,
        };

        fetch('/api/templates/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                errEl.textContent = data.error;
                errEl.style.display = 'block';
                return;
            }
            // Navigate to the detail page for the new template
            window.location.href = `/admin/templates/${data.id}`;
        })
        .catch(err => {
            errEl.textContent = 'Failed to create template.';
            errEl.style.display = 'block';
            console.error(err);
        });
    }

    function deleteTemplate(id, name) {
        const doDelete = () => {
            fetch(`/api/templates/${id}`, { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    if (data.error) { alert(data.error); return; }
                    window.location.reload();
                })
                .catch(err => { console.error(err); alert('Failed to delete template.'); });
        };

        if (typeof confirmModal === 'function') {
            confirmModal(`Delete template "${name}"?`, 'All segments will be removed.', doDelete);
        } else if (window.confirm(`Delete template "${name}"? All segments will be removed.`)) {
            doDelete();
        }
    }

    // ── Template detail page ──────────────────────────────────────────────────

    function toggleAddSegmentForm() {
        const el = document.getElementById('addSegmentForm');
        if (!el) return;
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
        if (el.style.display === 'block') el.querySelector('input[name="label"]').focus();
    }

    function submitAddSegment(event, templateId) {
        event.preventDefault();
        const form = event.target;
        const fd = new FormData(form);

        const distKm = parseFloat(fd.get('distance_km'));
        const payload = {
            label: fd.get('label'),
            distance_meters: distKm > 0 ? distKm * 1000 : null,
            duration_seconds: mssToSeconds(fd.get('duration_mss')),
            target_pace_sec_per_km: mssToSeconds(fd.get('pace_mss')),
            notes: fd.get('notes') || null,
        };

        fetch(`/api/templates/${templateId}/segments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to add segment.'); });
    }

    function openEditSegmentModal(seg, templateId) {
        document.getElementById('editSegmentId').value = seg.id;
        document.getElementById('editSegmentTemplateId').value = templateId;
        document.getElementById('editSegmentLabel').value = seg.label || '';
        document.getElementById('editSegmentDist').value =
            seg.distance_meters ? (seg.distance_meters / 1000).toFixed(2) : '';
        document.getElementById('editSegmentDur').value =
            seg.duration_seconds ? secondsToMss(seg.duration_seconds) : '';
        document.getElementById('editSegmentPace').value =
            seg.target_pace_sec_per_km ? secondsToMss(seg.target_pace_sec_per_km) : '';
        document.getElementById('editSegmentNotes').value = seg.notes || '';
        new bootstrap.Modal(document.getElementById('editSegmentModal')).show();
    }

    function submitEditSegment(event) {
        event.preventDefault();
        const segmentId = document.getElementById('editSegmentId').value;
        const templateId = document.getElementById('editSegmentTemplateId').value;

        const distKm = parseFloat(document.getElementById('editSegmentDist').value);
        const payload = {
            label: document.getElementById('editSegmentLabel').value,
            distance_meters: distKm > 0 ? distKm * 1000 : null,
            duration_seconds: mssToSeconds(document.getElementById('editSegmentDur').value),
            target_pace_sec_per_km: mssToSeconds(document.getElementById('editSegmentPace').value),
            notes: document.getElementById('editSegmentNotes').value || null,
        };

        fetch(`/api/templates/${templateId}/segments/${segmentId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            bootstrap.Modal.getInstance(document.getElementById('editSegmentModal')).hide();
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to save segment.'); });
    }

    function duplicateSegment(seg, templateId) {
        const payload = {
            label: seg.label,
            distance_meters: seg.distance_meters || null,
            duration_seconds: seg.duration_seconds || null,
            target_pace_sec_per_km: seg.target_pace_sec_per_km || null,
            notes: seg.notes || null,
        };
        fetch(`/api/templates/${templateId}/segments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert(data.error); return; }
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to duplicate segment.'); });
    }

    function deleteSegment(segmentId, templateId) {
        const doDelete = () => {
            fetch(`/api/templates/${templateId}/segments/${segmentId}`, { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    if (data.error) { alert(data.error); return; }
                    window.location.reload();
                })
                .catch(err => { console.error(err); alert('Failed to delete segment.'); });
        };

        if (typeof confirmModal === 'function') {
            confirmModal('Delete segment?', 'This cannot be undone.', doDelete);
        } else if (window.confirm('Delete this segment?')) {
            doDelete();
        }
    }

    function initSegmentSortable(templateId) {
        const tbody = document.getElementById('segmentList');
        if (!tbody || typeof Sortable === 'undefined') return;

        Sortable.create(tbody, {
            animation: 150,
            handle: '.segment-drag',
            draggable: '.segment-row',
            ghostClass: 'seg-ghost',
            onEnd() {
                const orderedIds = Array.from(tbody.querySelectorAll('.segment-row'))
                    .map(row => parseInt(row.dataset.id, 10));
                fetch(`/api/templates/${templateId}/segments/reorder`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ordered_ids: orderedIds }),
                }).catch(err => console.error('Reorder failed', err));
            }
        });
    }

    function openEditTemplateModal(template) {
        document.getElementById('editTemplateId').value = template.id;
        document.getElementById('editTemplateName').value = template.name || '';
        document.getElementById('editTemplateSport').value = template.sport_type || '';
        document.getElementById('editTemplateDesc').value = template.description || '';
        document.getElementById('editTemplateError').style.display = 'none';
        new bootstrap.Modal(document.getElementById('editTemplateModal')).show();
    }

    function submitEditTemplate(event) {
        event.preventDefault();
        const templateId = document.getElementById('editTemplateId').value;
        const errEl = document.getElementById('editTemplateError');
        errEl.style.display = 'none';

        const payload = {
            name: document.getElementById('editTemplateName').value,
            sport_type: document.getElementById('editTemplateSport').value || null,
            description: document.getElementById('editTemplateDesc').value || null,
        };

        fetch(`/api/templates/${templateId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                errEl.textContent = data.error;
                errEl.style.display = 'block';
                return;
            }
            bootstrap.Modal.getInstance(document.getElementById('editTemplateModal')).hide();
            window.location.reload();
        })
        .catch(err => { console.error(err); alert('Failed to save template.'); });
    }

    return {
        submitAdd,
        deleteTemplate,
        toggleAddSegmentForm,
        submitAddSegment,
        openEditSegmentModal,
        submitEditSegment,
        duplicateSegment,
        deleteSegment,
        initSegmentSortable,
        openEditTemplateModal,
        submitEditTemplate,
    };
})();
