'use strict';

const STORAGE_KEY = 'homework_magic_message_access_v1';
let messages = [];
let selectedMessageId = null;

function readAccessMap() {
    try {
        const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        return value && typeof value === 'object' ? value : {};
    } catch (_) {
        return {};
    }
}

function saveAccess(messageId, token) {
    if (!messageId || !token) return;
    const map = readAccessMap();
    map[messageId] = token;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
}

function setStatus(text, kind = 'info') {
    const element = document.getElementById('form-status');
    element.textContent = text;
    element.className = `status-message ${kind}`;
}

function clearStatus() {
    const element = document.getElementById('form-status');
    element.textContent = '';
    element.className = 'status-message hidden';
}

async function readJson(response) {
    let data = {};
    try { data = await response.json(); } catch (_) { /* no JSON body */ }
    if (!response.ok) throw new Error(data.detail || data.error || 'Something went wrong. Please try again.');
    return data;
}

function createMeta(message) {
    const meta = document.createElement('div');
    meta.className = 'message-meta';

    const category = document.createElement('span');
    category.textContent = String(message.category || 'general').replace(/^./, value => value.toUpperCase());
    meta.appendChild(category);

    const date = document.createElement('span');
    date.textContent = formatDate(message.updated_at || message.created_at);
    meta.appendChild(date);

    if (Number(message.reply_count || 0) > 0) {
        const replies = document.createElement('span');
        replies.textContent = `${message.reply_count} ${Number(message.reply_count) === 1 ? 'reply' : 'replies'}`;
        meta.appendChild(replies);
    }
    return meta;
}

function renderList() {
    const list = document.getElementById('message-list');
    list.replaceChildren();
    if (!messages.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = 'No messages yet.';
        list.appendChild(empty);
        document.getElementById('message-detail').className = 'hidden';
        return;
    }

    for (const message of messages) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `message-card${message.id === selectedMessageId ? ' active' : ''}`;
        button.addEventListener('click', () => openMessage(message.id));

        const heading = document.createElement('h3');
        heading.textContent = message.subject;
        button.appendChild(heading);

        const badge = document.createElement('span');
        badge.className = `badge ${message.status || ''}`;
        badge.textContent = String(message.status || 'open').replace(/^./, value => value.toUpperCase());
        button.appendChild(badge);
        button.appendChild(createMeta(message));
        list.appendChild(button);
    }
}

function makeBubble(kind, text, label, date) {
    const bubble = document.createElement('div');
    bubble.className = `bubble ${kind}`;
    const content = document.createElement('div');
    content.textContent = text;
    bubble.appendChild(content);
    const small = document.createElement('small');
    small.textContent = `${label} · ${formatDate(date)}`;
    bubble.appendChild(small);
    return bubble;
}

function renderDetail(message) {
    selectedMessageId = message.id;
    renderList();
    const detail = document.getElementById('message-detail');
    detail.replaceChildren();
    detail.className = '';

    const heading = document.createElement('h2');
    heading.textContent = message.subject;
    detail.appendChild(heading);

    const badge = document.createElement('span');
    badge.className = `badge ${message.status || ''}`;
    badge.textContent = String(message.status || 'open').replace(/^./, value => value.toUpperCase());
    detail.appendChild(badge);

    const thread = document.createElement('div');
    thread.className = 'thread';
    thread.appendChild(makeBubble('user', message.message, 'Your message', message.created_at));
    for (const reply of (message.replies || [])) {
        thread.appendChild(makeBubble('admin', reply.reply, 'Homework Magic support', reply.created_at));
    }
    detail.appendChild(thread);
}

async function openMessage(messageId) {
    const access = readAccessMap()[messageId];
    const headers = access ? { 'X-Message-Access-Token': access } : {};
    try {
        const data = await readJson(await fetch(`/api/messages/${encodeURIComponent(messageId)}`, {
            credentials: 'same-origin', headers
        }));
        renderDetail(data.message);
        await fetch(`/api/messages/${encodeURIComponent(messageId)}/read`, {
            method: 'POST', credentials: 'same-origin', headers
        });
    } catch (error) {
        setStatus(error.message, 'error');
    }
}

async function recoverStoredMessages(existingIds) {
    const recovered = [];
    const accessMap = readAccessMap();
    for (const [messageId, token] of Object.entries(accessMap)) {
        if (existingIds.has(messageId)) continue;
        try {
            const data = await readJson(await fetch(`/api/messages/${encodeURIComponent(messageId)}`, {
                credentials: 'same-origin',
                headers: { 'X-Message-Access-Token': token }
            }));
            recovered.push(data.message);
        } catch (_) {
            // Old or expired recovery entries are ignored.
        }
    }
    return recovered;
}

async function loadMessages(selectNewest = false) {
    const list = document.getElementById('message-list');
    list.textContent = 'Loading messages…';
    try {
        const data = await readJson(await fetch('/api/messages?limit=100', { credentials: 'same-origin' }));
        const direct = Array.isArray(data.messages) ? data.messages : [];
        const recovered = await recoverStoredMessages(new Set(direct.map(item => item.id)));
        messages = [...direct, ...recovered].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
        if (selectNewest && messages.length) selectedMessageId = messages[0].id;
        renderList();
        if (selectedMessageId && messages.some(item => item.id === selectedMessageId)) {
            await openMessage(selectedMessageId);
        }
    } catch (error) {
        list.replaceChildren();
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = error.message;
        list.appendChild(empty);
    }
}

async function submitMessage(event) {
    event.preventDefault();
    clearStatus();
    const button = document.getElementById('send-message');
    button.disabled = true;
    button.textContent = 'Sending…';
    const payload = {
        contact_email: document.getElementById('contact-email').value.trim(),
        category: document.getElementById('message-category').value,
        subject: document.getElementById('message-subject').value.trim(),
        message: document.getElementById('message-body').value.trim()
    };
    try {
        const data = await readJson(await fetch('/api/messages', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }));
        saveAccess(data.message.id, data.access_token);
        selectedMessageId = data.message.id;
        document.getElementById('message-subject').value = '';
        document.getElementById('message-body').value = '';
        setStatus('Your message was sent. A reply will appear in your message box.', 'success');
        await loadMessages();
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Send message';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const savedEmail = '';
    if (savedEmail && savedEmail.includes('@')) document.getElementById('contact-email').value = savedEmail;
    document.getElementById('contact-form').addEventListener('submit', submitMessage);
    document.getElementById('refresh-messages').addEventListener('click', () => loadMessages());
    loadMessages();
});
