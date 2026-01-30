// Sync button with AJAX and progress updates
const syncBtn = document.getElementById('syncBtn');
if (syncBtn) {
    syncBtn.addEventListener('click', async (e) => {
        e.preventDefault(); // Prevent navigation

        const overlay = document.getElementById('syncOverlay');
        const message = overlay?.querySelector('.sync-message');
        const submessage = overlay?.querySelector('.sync-submessage');

        if (overlay) {
            overlay.classList.add('active');
        }

        try {
            // Step 1: Sync activity summary data
            if (message) message.textContent = 'Syncing activities from Strava...';
            if (submessage) submessage.textContent = 'Fetching activity list';

            const syncResponse = await fetch('/api/sync/activities', { method: 'POST' });
            const syncData = await syncResponse.json();

            if (!syncResponse.ok) {
                throw new Error(syncData.error || 'Sync failed');
            }

            const { created, updated, needs_descriptions } = syncData;

            // Step 2: Get activities needing descriptions
            if (needs_descriptions > 0) {
                if (message) message.textContent = 'Fetching descriptions...';

                const listResponse = await fetch('/api/sync/activities-needing-descriptions');
                const listData = await listResponse.json();
                const activityIds = listData.activity_ids || [];

                let descriptionsAdded = 0;
                for (let i = 0; i < activityIds.length; i++) {
                    if (submessage) {
                        submessage.textContent = `Activity ${i + 1} of ${activityIds.length}`;
                    }

                    try {
                        const descResponse = await fetch(`/api/sync/description/${activityIds[i]}`, {
                            method: 'POST'
                        });
                        const descData = await descResponse.json();
                        if (descData.has_description) {
                            descriptionsAdded++;
                        }
                    } catch {
                        // Continue on error
                    }
                }

                // Show completion message
                if (message) message.textContent = 'Sync complete!';
                if (submessage) {
                    submessage.textContent = `${created} new, ${updated} updated, ${descriptionsAdded} descriptions`;
                }
            } else {
                if (message) message.textContent = 'Sync complete!';
                if (submessage) submessage.textContent = `${created} new, ${updated} updated`;
            }

            // Reload page after short delay to show results
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } catch (error) {
            if (message) message.textContent = 'Sync failed';
            if (submessage) submessage.textContent = error.message;

            setTimeout(() => {
                if (overlay) overlay.classList.remove('active');
            }, 3000);
        }
    });
}

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

// Mobile: Prevent day feeling icon click from affecting card
document.querySelectorAll('.day-card-feeling').forEach(feeling => {
    feeling.addEventListener('click', (e) => {
        e.stopPropagation();
    });
});

// Dynamic day feeling modal population
const dayFeelingModal = document.getElementById('dayFeelingModal');
if (dayFeelingModal) {
    dayFeelingModal.addEventListener('show.bs.modal', (event) => {
        const trigger = event.relatedTarget;
        const day = trigger.dataset.day;

        // Get feeling data for this day
        const feeling = window.dayFeelingsData?.[day] || {};

        // Update form action
        const form = document.getElementById('dayFeelingForm');
        form.action = `/day/${day}/annotations`;

        // Update modal title
        document.getElementById('dayFeelingModalDate').textContent = day;

        // Update referer
        const referer = `/?page=${window.currentPage || 1}${window.currentSportType ? '&sport_type=' + window.currentSportType : ''}`;
        document.getElementById('dayFeelingReferer').value = referer;

        // Update text fields
        document.getElementById('dayFeelingText').value = feeling.feeling_text || '';
        document.getElementById('dayFeelingCoach').value = feeling.coach_comment || '';

        // Update pain selector
        const painValue = feeling.feeling_pain;
        const selector = document.querySelector('#dayFeelingModal .pain-scale-selector');
        const hiddenInput = document.getElementById('day_feeling_pain');

        if (selector) {
            selector.querySelectorAll('.pain-scale-option').forEach(opt => {
                const isSelected = painValue !== null && painValue !== undefined &&
                                   parseInt(opt.dataset.value) === painValue;
                opt.classList.toggle('selected', isSelected);
            });
            hiddenInput.value = painValue !== null && painValue !== undefined ? painValue : '';
        }
    });
}

// Day row expand/collapse functionality (Desktop)
// Uses d-none class for visibility toggling
document.querySelectorAll('.day-row-collapsed').forEach(collapsedRow => {
    const dayId = collapsedRow.dataset.day;
    const expandedRow = document.querySelector(`.day-row-expanded[data-day="${dayId}"]`);

    if (!expandedRow) return;

    collapsedRow.addEventListener('click', (e) => {
        // Don't toggle if clicking on modal triggers or activity links
        if (e.target.closest('[data-bs-toggle="modal"]') || e.target.closest('a')) {
            return;
        }

        // Toggle the expanded state using d-none class
        if (collapsedRow.classList.contains('expanded')) {
            // Collapse
            collapsedRow.classList.remove('expanded', 'd-none');
            expandedRow.classList.add('d-none');
        } else {
            // Expand
            collapsedRow.classList.add('expanded', 'd-none');
            expandedRow.classList.remove('d-none');
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
            collapsedRow.classList.remove('expanded', 'd-none');
            expandedRow.classList.add('d-none');
        }
    });
});
