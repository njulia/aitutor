/* Small, dependency-free chart renderer for learner pages.
 * Supports the doughnut, line and bar configurations used by this project.
 * It deliberately avoids analytics, network calls and third-party CDNs.
 */
(function (global) {
  'use strict';

  function resolveCanvas(target) {
    if (target && target.canvas) return target.canvas;
    if (typeof target === 'string') return document.getElementById(target);
    return target;
  }

  function values(config) {
    const datasets = (((config || {}).data || {}).datasets || []);
    return datasets.length ? (datasets[0].data || []).map(Number) : [];
  }

  function labels(config) {
    return ((((config || {}).data || {}).labels) || []).map(String);
  }

  function setup(canvas) {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(260, Math.round(rect.width || canvas.width || 600));
    const height = Math.max(180, Math.round(rect.height || canvas.height || 300));
    const ratio = Math.max(1, global.devicePixelRatio || 1);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    ctx.font = '12px system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    return {ctx, width, height};
  }

  function palette(dataset, count) {
    const source = dataset.backgroundColor || dataset.borderColor || '#667eea';
    if (Array.isArray(source)) return source;
    return Array.from({length: count}, () => source);
  }

  function drawDoughnut(ctx, width, height, data, dataset) {
    const total = data.reduce((a, b) => a + Math.max(0, b), 0) || 1;
    const radius = Math.min(width, height) * 0.39;
    const inner = radius * 0.68;
    const colours = palette(dataset, data.length);
    let angle = -Math.PI / 2;
    data.forEach((value, index) => {
      const next = angle + (Math.max(0, value) / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, radius, angle, next);
      ctx.arc(width / 2, height / 2, inner, next, angle, true);
      ctx.closePath();
      ctx.fillStyle = colours[index] || '#dfe3ee';
      ctx.fill();
      angle = next;
    });
  }

  function axes(ctx, width, height, max) {
    const box = {left: 48, right: width - 18, top: 18, bottom: height - 38};
    ctx.strokeStyle = '#d5dbea';
    ctx.fillStyle = '#64708a';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) {
      const y = box.bottom - ((box.bottom - box.top) * i / 4);
      ctx.beginPath(); ctx.moveTo(box.left, y); ctx.lineTo(box.right, y); ctx.stroke();
      ctx.fillText(Math.round(max * i / 4) + '%', 4, y);
    }
    return box;
  }

  function drawBar(ctx, width, height, data, chartLabels, dataset) {
    const max = Math.max(100, ...data, 1);
    const box = axes(ctx, width, height, max);
    const colours = palette(dataset, data.length);
    const slot = (box.right - box.left) / Math.max(data.length, 1);
    const barWidth = Math.max(12, Math.min(slot * 0.62, 64));
    data.forEach((value, i) => {
      const h = (Math.max(0, value) / max) * (box.bottom - box.top);
      const x = box.left + slot * i + (slot - barWidth) / 2;
      ctx.fillStyle = colours[i] || '#667eea';
      ctx.fillRect(x, box.bottom - h, barWidth, h);
      ctx.save();
      ctx.translate(x + barWidth / 2, box.bottom + 10);
      ctx.rotate(-0.28);
      ctx.fillStyle = '#46516b';
      ctx.textAlign = 'right';
      ctx.fillText((chartLabels[i] || '').slice(0, 18), 0, 0);
      ctx.restore();
    });
  }

  function drawLine(ctx, width, height, data, chartLabels, dataset) {
    const max = Math.max(100, ...data, 1);
    const box = axes(ctx, width, height, max);
    const span = Math.max(data.length - 1, 1);
    const points = data.map((value, i) => ({
      x: box.left + ((box.right - box.left) * i / span),
      y: box.bottom - (Math.max(0, value) / max) * (box.bottom - box.top),
    }));
    ctx.strokeStyle = dataset.borderColor || '#667eea';
    ctx.lineWidth = Number(dataset.borderWidth || 3);
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
    ctx.stroke();
    const pointColours = Array.isArray(dataset.pointBackgroundColor) ? dataset.pointBackgroundColor : [];
    points.forEach((p, i) => {
      ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = pointColours[i] || dataset.borderColor || '#667eea'; ctx.fill();
      if (chartLabels[i]) {
        ctx.fillStyle = '#46516b'; ctx.textAlign = 'center';
        ctx.fillText(chartLabels[i].slice(0, 12), p.x, box.bottom + 18);
      }
    });
  }

  function Chart(target, config) {
    this.canvas = resolveCanvas(target);
    this.config = config || {};
    this.destroy = function () {
      if (!this.canvas) return;
      const c = this.canvas.getContext('2d');
      c.clearRect(0, 0, this.canvas.width, this.canvas.height);
    };
    if (!this.canvas || !this.canvas.getContext) return;
    const view = setup(this.canvas);
    const dataset = ((((this.config || {}).data || {}).datasets || [])[0]) || {};
    const data = values(this.config);
    const chartLabels = labels(this.config);
    if (this.config.type === 'doughnut') drawDoughnut(view.ctx, view.width, view.height, data, dataset);
    else if (this.config.type === 'line') drawLine(view.ctx, view.width, view.height, data, chartLabels, dataset);
    else drawBar(view.ctx, view.width, view.height, data, chartLabels, dataset);
  }

  global.Chart = Chart;
})(window);
