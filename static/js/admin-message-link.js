'use strict';

(function addMessageShortcut() {
    function makeShortcut(count) {
        if (document.getElementById('admin-message-shortcut')) return;
        const link = document.createElement('a');
        link.id = 'admin-message-shortcut';
        link.href = '/admin/messages';
        link.textContent = count > 0 ? `✉ User Messages (${count} new)` : '✉ User Messages';
        link.setAttribute('aria-label', count > 0 ? `User messages, ${count} unread` : 'User messages');
        Object.assign(link.style, {
            position: 'fixed',
            right: '20px',
            bottom: '20px',
            zIndex: '10000',
            padding: '12px 18px',
            borderRadius: '999px',
            background: '#6c63e8',
            color: '#fff',
            fontFamily: 'system-ui, sans-serif',
            fontWeight: '800',
            textDecoration: 'none',
            boxShadow: '0 8px 24px rgba(35, 28, 100, .28)'
        });
        document.body.appendChild(link);
    }

    fetch('/api/admin/messages/summary', { credentials: 'same-origin' })
        .then(response => response.ok ? response.json() : Promise.reject(new Error('not authorised')))
        .then(data => makeShortcut(Number(data.summary && data.summary.unread || 0)))
        .catch(() => { /* Admin dashboard guard handles unauthorised access. */ });
})();
