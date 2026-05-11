/**
 * ObStar AI — Client-side JavaScript
 * Handles status polling, drag-drop uploads, and UI interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    initStatusPolling();
    initFileUpload();
    initToastAutoDismiss();
});


/* ========== Status Polling ========== */
function initStatusPolling() {
    const statusEl = document.querySelector('[data-meeting-status]');
    if (!statusEl) return;

    const meetingId = statusEl.dataset.meetingId;
    const currentStatus = statusEl.dataset.meetingStatus;

    if (currentStatus === 'pending' || currentStatus === 'processing') {
        pollMeetingStatus(meetingId);
    }
}

function pollMeetingStatus(meetingId) {
    const pollInterval = 3000; // 3 seconds

    const poll = () => {
        fetch(`/api/meetings/${meetingId}/status/`)
            .then(res => res.json())
            .then(data => {
                updateStatusUI(data.status);

                if (data.status === 'completed') {
                    // Reload to show transcript and summary
                    setTimeout(() => window.location.reload(), 500);
                } else if (data.status === 'failed') {
                    showError(data.error_message || 'Processing failed.');
                } else {
                    // Keep polling
                    setTimeout(poll, pollInterval);
                }
            })
            .catch(err => {
                console.error('Polling error:', err);
                setTimeout(poll, pollInterval * 2);
            });
    };

    setTimeout(poll, pollInterval);
}

function updateStatusUI(status) {
    const badge = document.querySelector('.status-badge');
    if (badge) {
        badge.className = `badge badge-${status} status-badge`;
        badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }

    const progressDots = document.querySelector('.progress-dots');
    if (progressDots && status === 'processing') {
        progressDots.textContent = '.'.repeat((Date.now() / 500 % 3) + 1);
    }
}

function showError(message) {
    const processingEl = document.querySelector('.processing-state');
    if (processingEl) {
        processingEl.innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠</div>
                <div class="error-message">${message}</div>
                <p class="text-secondary mt-sm">You can try re-processing this meeting.</p>
            </div>
        `;
    }
}


/* ========== File Upload ========== */
function initFileUpload() {
    const uploadZone = document.querySelector('.upload-zone');
    const fileInput = document.querySelector('#meeting-file-input');
    const fileNameDisplay = document.querySelector('.file-name-display');

    if (!uploadZone || !fileInput) return;

    // Drag events
    ['dragenter', 'dragover'].forEach(event => {
        uploadZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(event => {
        uploadZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.remove('dragover');
        });
    });

    uploadZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length) {
            fileInput.files = files;
            showFileName(files[0].name, fileNameDisplay);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            showFileName(fileInput.files[0].name, fileNameDisplay);
        }
    });
}

function showFileName(name, displayEl) {
    if (displayEl) {
        displayEl.textContent = `📎 ${name}`;
        displayEl.classList.add('visible');
    }
}


/* ========== Toast Auto-dismiss ========== */
function initToastAutoDismiss() {
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach((toast, index) => {
        setTimeout(() => {
            toast.style.transition = 'all 0.3s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(40px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000 + (index * 500));
    });
}


/* ========== Utility ========== */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}
