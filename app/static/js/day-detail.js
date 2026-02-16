// Share button functionality for day detail page
// Reads data from window.dayShareData (injected by template)
const shareBtn = document.getElementById('share-btn');
if (shareBtn) {
    shareBtn.addEventListener('click', async () => {
        const data = window.dayShareData;
        if (!data) return;

        const feelingLabels = {
            0: '😁', 1: '😊', 2: '😐', 3: '🙁', 4: '😟',
            5: '😣', 6: '😬', 7: '😢', 8: '😖', 9: '😩', 10: '😵'
        };

        const PACE_SPORTS = ['Run', 'TrailRun', 'VirtualRun', 'Walk', 'Hike'];

        // Build share text
        let text = '📅 ' + data.formatted_date + '\n';

        if (data.feeling_pain !== null && data.feeling_pain !== undefined) {
            text += 'Feeling: ' + (feelingLabels[data.feeling_pain] || '') + ' (' + data.feeling_pain + '/10)\n';
        }

        if (data.feeling_text) {
            text += '📝 ' + data.feeling_text.replace(/\n/g, ' ') + '\n';
        }

        if (data.activities && data.activities.length > 0) {
            text += '\n';
            data.activities.forEach(a => {
                text += '🏃 ' + a.name;
                if (a.distance) {
                    text += ' — ' + (a.distance / 1000).toFixed(2) + ' km';
                }
                if (a.moving_time) {
                    const h = Math.floor(a.moving_time / 3600);
                    const m = Math.floor((a.moving_time % 3600) / 60);
                    text += ', ' + h + 'h ' + m + 'm';
                }
                if (a.average_speed && a.average_speed > 0 && PACE_SPORTS.includes(a.sport_type)) {
                    const paceSecs = Math.floor(1000 / a.average_speed);
                    const paceMin = Math.floor(paceSecs / 60);
                    const paceSec = String(paceSecs % 60).padStart(2, '0');
                    text += ' (' + paceMin + ':' + paceSec + ' /km)';
                }
                text += '\n';
            });
        } else {
            text += '\n😴 Rest day\n';
        }

        text += '\n' + window.location.href;

        try {
            if (navigator.share) {
                await navigator.share({ text: text });
            } else {
                await navigator.clipboard.writeText(text);
                const orig = shareBtn.innerHTML;
                shareBtn.innerHTML = '<i class="bi bi-check"></i> Copied';
                shareBtn.classList.replace('btn-outline-primary', 'btn-success');
                setTimeout(() => {
                    shareBtn.innerHTML = orig;
                    shareBtn.classList.replace('btn-success', 'btn-outline-primary');
                }, 2000);
            }
        } catch (err) {
            // User cancelled or error — silently ignore
        }
    });
}
