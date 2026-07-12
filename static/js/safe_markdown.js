/* Render model-generated Markdown with a strict local allow-list. */
(function () {
  'use strict';
  const ALLOWED = new Set(['P','BR','H1','H2','H3','UL','OL','LI','STRONG','EM','CODE','PRE','TABLE','THEAD','TBODY','TR','TH','TD','A']);
  function sanitise(html) {
    const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html');
    const root = doc.body.firstElementChild;
    [...root.querySelectorAll('*')].forEach((node) => {
      if (!ALLOWED.has(node.tagName)) {
        node.replaceWith(doc.createTextNode(node.textContent || ''));
        return;
      }
      [...node.attributes].forEach((attr) => node.removeAttribute(attr.name));
    });
    return root.innerHTML;
  }
  window.renderSafeMarkdown = function renderSafeMarkdown(markdown) {
    const raw = window.marked ? window.marked.parse(String(markdown || '')) : String(markdown || '');
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      return window.DOMPurify.sanitize(raw, {USE_PROFILES: {html: true}});
    }
    // Fail closed with the built-in allow-list when DOMPurify is not bundled.
    return sanitise(raw);
  };
})();
