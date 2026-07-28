'use strict';

const message = document.getElementById('order-message');
const rows = document.getElementById('order-rows');
const empty = document.getElementById('empty-orders');
const addressPanel = document.getElementById('address-panel');
const addressBlock = document.getElementById('delivery-address');

function setMessage(text, kind = '') {
  message.textContent = text || '';
  message.className = `message${kind ? ` ${kind}` : ''}`;
}

function node(tag, text, className = '') {
  const item = document.createElement(tag);
  item.textContent = text;
  if (className) item.className = className;
  return item;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
    headers: {
      ...(options.body ? {'Content-Type': 'application/json'} : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'The administrator action failed.');
  }
  return data;
}

function shortOrderId(value) {
  const text = String(value || '');
  return text.length > 14 ? `${text.slice(0, 10)}…` : text;
}

function dateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function actionButton(label, className, handler) {
  const button = node('button', label, className);
  button.type = 'button';
  button.addEventListener('click', handler);
  return button;
}

async function showAddress(orderId) {
  setMessage('Opening the encrypted delivery address…');
  try {
    const data = await requestJson(
      `/api/admin/reward-orders/${encodeURIComponent(orderId)}`,
    );
    const address = data.delivery_address;
    if (!address) throw new Error('This order no longer has a delivery address.');
    addressBlock.textContent = [
      address.recipient_name,
      address.address_line1,
      address.address_line2,
      address.town_city,
      address.postcode,
      address.country,
    ].filter(Boolean).join('\n');
    addressPanel.hidden = false;
    addressPanel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    setMessage('');
  } catch (error) {
    setMessage(error.message, 'error');
  }
}

async function decideOrder(orderId, decision) {
  const prompt = decision === 'dispatch'
    ? 'Confirm that this gift has been posted?'
    : 'Cancel this gift order and return its Gift Points?';
  if (!window.confirm(prompt)) return;
  setMessage(decision === 'dispatch' ? 'Marking as dispatched…' : 'Cancelling order…');
  try {
    await requestJson(
      `/api/admin/reward-orders/${encodeURIComponent(orderId)}/decision`,
      {
        method: 'POST',
        body: JSON.stringify({decision}),
      },
    );
    addressPanel.hidden = true;
    addressBlock.textContent = '';
    setMessage(
      decision === 'dispatch'
        ? 'Gift marked as dispatched.'
        : 'Order cancelled and Gift Points returned.',
      'success',
    );
    await loadOrders(false);
  } catch (error) {
    setMessage(error.message, 'error');
  }
}

function renderOrders(orders) {
  rows.replaceChildren();
  empty.hidden = orders.length > 0;
  orders.forEach((order) => {
    const row = document.createElement('tr');
    const id = node('td', shortOrderId(order.id));
    id.title = order.id;
    row.append(
      id,
      node('td', `${order.reward_icon} ${order.reward_name}`),
      node('td', String(order.points_cost)),
      node('td', dateTime(order.requested_at)),
    );

    const statusCell = document.createElement('td');
    statusCell.append(node('span', order.status, `status ${order.status}`));
    row.append(statusCell);

    const delivery = document.createElement('td');
    delivery.append(node(
      'span',
      order.delivery_address_supplied ? 'Address ready' : 'No address',
    ));
    row.append(delivery);

    const actions = node('td', '', 'actions');
    if (order.delivery_address_supplied) {
      actions.append(actionButton('Show address', 'secondary', () => showAddress(order.id)));
    }
    if (order.status === 'approved') {
      actions.append(
        actionButton('Dispatched', '', () => decideOrder(order.id, 'dispatch')),
        actionButton('Cancel', 'danger', () => decideOrder(order.id, 'cancel')),
      );
    }
    row.append(actions);
    rows.append(row);
  });
}

async function loadOrders(showLoading = true) {
  if (showLoading) setMessage('Loading gift orders…');
  const status = document.getElementById('order-status').value;
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  try {
    const data = await requestJson(`/api/admin/reward-orders${query}`);
    renderOrders(data.orders || []);
    if (showLoading) setMessage('');
  } catch (error) {
    setMessage(error.message, 'error');
  }
}

document.getElementById('refresh-orders').addEventListener('click', () => loadOrders());
document.getElementById('order-status').addEventListener('change', () => loadOrders());
document.getElementById('close-address').addEventListener('click', () => {
  addressPanel.hidden = true;
  addressBlock.textContent = '';
});

loadOrders();
