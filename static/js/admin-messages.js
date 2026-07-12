'use strict';

let adminMessages = [];
let selectedId = null;
let searchTimer = null;

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
}

async function readJson(response) {
    let data = {};
    try { data = await response.json(); } catch (_) { /* no JSON body */ }
    if (response.status === 401 || response.status === 403) {
        window.location.href = '/login';
        throw new Error('Administrator login is required.');
    }
    if (!response.ok) throw new Error(data.detail || data.error || 'The request failed.');
    return data;
}

function showStatus(text, kind = 'info') {
    const element = document.getElementById('admin-status');
    element.textContent = text;
    element.className = `status-message ${kind}`;
}

function clearStatus() {
    const element = document.getElementById('admin-status');
    element.textContent = '';
    element.className = 'status-message hidden';
}

function capitalise(value) {
    return String(value || '').replace(/^./, part => part.toUpperCase());
}

function appendText(parent, tag, text, className = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
}

async function loadSummary() {
    const data = await readJson(await fetch('/api/admin/messages/summary', { credentials: 'same-origin' }));
    const summary = data.summary || {};
    const container = document.getElementById('summary');
    container.replaceChildren();
    for (const key of ['unread', 'open', 'pending', 'replied', 'closed', 'total']) {
        const card = document.createElement('div');
        card.className = 'summary-card';
        appendText(card, 'strong', String(summary[key] || 0));
        appendText(card, 'span', capitalise(key));
        container.appendChild(card);
    }
}

function renderAdminList() {
    const list = document.getElementById('admin-message-list');
    list.replaceChildren();
    if (!adminMessages.length) {
        appendText(list, 'div', 'No messages match these filters.', 'empty');
        return;
    }
    for (const message of adminMessages) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `message-card${message.id === selectedId ? ' active' : ''}`;
        button.addEventListener('click', () => openAdminMessage(message.id));
        appendText(button, 'h3', message.subject);
        const badge = appendText(button, 'span', capitalise(message.status), `badge ${message.status}`);
        if (!message.admin_read_at) badge.textContent += ' · New';
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        appendText(meta, 'span', capitalise(message.category));
        appendText(meta, 'span', message.contact_email || 'No email');
        appendText(meta, 'span', formatDate(message.updated_at || message.created_at));
        button.appendChild(meta);
        list.appendChild(button);
    }
}

function createBubble(kind, text, label, date, emailStatus) {
    const bubble = document.createElement('div');
    bubble.className = `bubble ${kind}`;
    appendText(bubble, 'div', text);
    const detail = `${label} · ${formatDate(date)}${emailStatus ? ` · Email: ${emailStatus}` : ''}`;
    appendText(bubble, 'small', detail);
    return bubble;
}

function makeSelect(message) {
    const select = document.createElement('select');
    select.id = 'detail-status';
    select.setAttribute('aria-label', 'Message status');
    for (const value of ['open', 'pending', 'replied', 'closed']) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = capitalise(value);
        option.selected = value === message.status;
        select.appendChild(option);
    }
    select.addEventListener('change', () => changeStatus(message.id, select.value));
    return select;
}

function renderAdminDetail(message) {
    selectedId = message.id;
    renderAdminList();
    const detail = document.getElementById('admin-message-detail');
    detail.className = '';
    detail.replaceChildren();

    const header = document.createElement('div');
    header.className = 'detail-header';
    const title = document.createElement('div');
    appendText(title, 'h2', message.subject);
    appendText(title, 'div', `${capitalise(message.category)} · ${formatDate(message.created_at)}`, 'message-meta');
    header.appendChild(title);
    header.appendChild(makeSelect(message));
    detail.appendChild(header);

    const contact = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = 'Parent or guardian email: ';
    contact.appendChild(strong);
    contact.appendChild(document.createTextNode(message.contact_email || 'Not supplied'));
    detail.appendChild(contact);

    const thread = document.createElement('div');
    thread.className = 'thread';
    thread.appendChild(createBubble('user', message.message, 'User message', message.created_at));
    for (const reply of (message.replies || [])) {
        thread.appendChild(createBubble('admin', reply.reply, `Support reply by ${reply.admin_email}`, reply.created_at, reply.email_status));
    }
    detail.appendChild(thread);

    const form = document.createElement('form');
    form.className = 'reply-form';
    form.addEventListener('submit', event => sendReply(event, message.id));
    appendText(form, 'h3', 'Reply');

    const label = document.createElement('label');
    label.htmlFor = 'admin-reply';
    label.textContent = 'Reply shown in the user message box';
    form.appendChild(label);
    const textarea = document.createElement('textarea');
    textarea.id = 'admin-reply';
    textarea.maxLength = 5000;
    textarea.required = true;
    form.appendChild(textarea);

    const checkLabel = document.createElement('label');
    checkLabel.className = 'checkbox-label';
    const checkbox = document.createElement('input');
    checkbox.id = 'send-reply-email';
    checkbox.type = 'checkbox';
    checkbox.checked = Boolean(message.contact_email);
    checkbox.disabled = !message.contact_email;
    checkLabel.appendChild(checkbox);
    checkLabel.appendChild(document.createTextNode('Also send this reply by email'));
    form.appendChild(checkLabel);

    const button = document.createElement('button');
    button.id = 'send-admin-reply';
    button.type = 'submit';
    button.className = 'btn btn-primary';
    button.textContent = 'Send reply';
    form.appendChild(button);
    detail.appendChild(form);
}

async function openAdminMessage(messageId) {
    clearStatus();
    try {
        const data = await readJson(await fetch(`/api/admin/messages/${encodeURIComponent(messageId)}`, { credentials: 'same-origin' }));
        renderAdminDetail(data.message);
        await Promise.all([loadSummary(), loadMessages(false)]);
    } catch (error) {
        showStatus(error.message, 'error');
    }
}

function queryString() {
    const params = new URLSearchParams();
    const status = document.getElementById('filter-status').value;
    const category = document.getElementById('filter-category').value;
    const search = document.getElementById('message-search').value.trim();
    if (status) params.set('status', status);
    if (category) params.set('category', category);
    if (search) params.set('search', search);
    params.set('limit', '200');
    return params.toString();
}

async function loadMessages(clearSelection = false) {
    if (clearSelection) selectedId = null;
    const list = document.getElementById('admin-message-list');
    list.textContent = 'Loading messages…';
    try {
        const data = await readJson(await fetch(`/api/admin/messages?${queryString()}`, { credentials: 'same-origin' }));
        adminMessages = Array.isArray(data.messages) ? data.messages : [];
        renderAdminList();
    } catch (error) {
        list.replaceChildren();
        appendText(list, 'div', error.message, 'empty');
    }
}

async function sendReply(event, messageId) {
    event.preventDefault();
    clearStatus();
    const button = document.getElementById('send-admin-reply');
    const reply = document.getElementById('admin-reply').value.trim();
    const sendEmail = document.getElementById('send-reply-email').checked;
    if (!reply) return;
    button.disabled = true;
    button.textContent = 'Sending…';
    try {
        const data = await readJson(await fetch(`/api/admin/messages/${encodeURIComponent(messageId)}/reply`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reply, send_email: sendEmail })
        }));
        let note = 'Reply saved in the user message box.';
        if (data.email_status === 'sent') note += ' Email sent.';
        if (data.email_status === 'skipped' || data.email_status === 'failed') {
            note += ` ${data.email_message || 'Email was not sent.'}`;
        }
        await openAdminMessage(messageId);
        showStatus(note, data.email_status === 'failed' ? 'error' : 'success');
    } catch (error) {
        showStatus(error.message, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Send reply';
    }
}

async function changeStatus(messageId, status) {
    try {
        await readJson(await fetch(`/api/admin/messages/${encodeURIComponent(messageId)}/status`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        }));
        showStatus(`Status changed to ${capitalise(status)}.`, 'success');
        await Promise.all([loadSummary(), loadMessages(false)]);
    } catch (error) {
        showStatus(error.message, 'error');
    }
}

async function refreshAll() {
    clearStatus();
    await Promise.all([loadSummary(), loadMessages(true)]);
    document.getElementById('admin-message-detail').className = 'empty';
    document.getElementById('admin-message-detail').textContent = 'Select a message to read it.';
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refresh-admin-messages').addEventListener('click', refreshAll);
    document.getElementById('filter-status').addEventListener('change', () => loadMessages(true));
    document.getElementById('filter-category').addEventListener('change', () => loadMessages(true));
    document.getElementById('message-search').addEventListener('input', () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => loadMessages(true), 250);
    });
    refreshAll();
});
