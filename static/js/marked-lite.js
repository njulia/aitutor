/* Small local Markdown renderer for learner pages. It deliberately supports a
   limited subset and escapes all input before formatting. */
(function () {
  'use strict';
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function inline(text) {
    return escapeHtml(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>');
  }
  function parse(markdown) {
    const lines = String(markdown || '').replace(/\r/g, '').split('\n');
    const out = [];
    let list = null;
    let table = null;
    function closeList() { if (list) { out.push(`</${list}>`); list = null; } }
    function closeTable() { if (table) { out.push('</tbody></table>'); table = null; } }
    for (const raw of lines) {
      const line = raw.trimEnd();
      if (!line.trim()) { closeList(); closeTable(); continue; }
      
      // Table support
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        closeList();
        const cells = line.split('|').map(c => c.trim()).filter((c, i, a) => i > 0 && i < a.length - 1);
        if (line.match(/^[| \t:-]+$/)) {
          if (table === 'header') {
            out.push('</thead><tbody>');
            table = 'body';
          }
          continue;
        }
        if (!table) {
          table = 'header';
          out.push('<table>\n<thead>');
          out.push('<tr>' + cells.map(c => `<th>${inline(c)}</th>`).join('') + '</tr>');
          continue;
        }
        out.push('<tr>' + cells.map(c => `<td>${inline(c)}</td>`).join('') + '</tr>');
        continue;
      }
      closeTable();

      let m = line.match(/^(#{1,3})\s+(.+)$/);
      if (m) { closeList(); const n = m[1].length; out.push(`<h${n}>${inline(m[2])}</h${n}>`); continue; }
      m = line.match(/^[-*]\s+(.+)$/);
      if (m) { if (list !== 'ul') { closeList(); list = 'ul'; out.push('<ul>'); } out.push(`<li>${inline(m[1])}</li>`); continue; }
      m = line.match(/^\d+[.)]\s+(.+)$/);
      if (m) { if (list !== 'ol') { closeList(); list = 'ol'; out.push('<ol>'); } out.push(`<li>${inline(m[1])}</li>`); continue; }
      closeList(); out.push(`<p>${inline(line)}</p>`);
    }
    closeList();
    closeTable();
    return out.join('\n');
  }
  function Renderer() {}
  window.marked = { parse, Renderer, setOptions: function () {} };
})();
