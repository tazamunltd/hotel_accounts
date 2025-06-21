(function() {
    // Will hold our overlay element
    let overlay = null;

    // On DOM ready, inject the spinner HTML (hidden by default)
    document.addEventListener('DOMContentLoaded', function() {
        overlay = document.createElement('div');
        overlay.className = 'o_loader_overlay';
        overlay.innerHTML = '<div class="o_loader_spinner"></div>';
        document.body.appendChild(overlay);
        overlay.style.display = 'none';
    });

    // Keep original send
    const originalSend = XMLHttpRequest.prototype.send;

    // Patch send() to show spinner on start, hide on loadend
    XMLHttpRequest.prototype.send = function() {
        if (overlay) {
            overlay.style.display = 'flex';
            this.addEventListener('loadend', function() {
                overlay.style.display = 'none';
            });
        }
        return originalSend.apply(this, arguments);
    };
})();