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
  function plainTextMath(expression) {
    return String(expression || '')
      .replace(/\\times\b/g, '*')
      .replace(/\\cdot\b/g, '*')
      .replace(/\\div\b/g, '÷')
      .replace(/\\leq?\b/g, '≤')
      .replace(/\\geq?\b/g, '≥')
      .replace(/\\neq\b/g, '≠')
      .replace(/\\%/g, '%')
      .replace(/\\([#$&_{}])/g, '$1')
      .replace(/\s+/g, ' ')
      .trim();
  }
  function makeInlineMathFriendly(markdown) {
    // Primary pupils should see familiar operators rather than raw TeX.
    return String(markdown || '')
      .replace(/\\\(([\s\S]*?)\\\)/g, function (_whole, expression) {
        return `(${plainTextMath(expression)})`;
      })
      .replace(/\\\[([\s\S]*?)\\\]/g, function (_whole, expression) {
        return `(${plainTextMath(expression)})`;
      });
  }
  window.renderSafeMarkdown = function renderSafeMarkdown(markdown) {
    const friendlyMarkdown = makeInlineMathFriendly(markdown);
    const raw = window.marked ? window.marked.parse(friendlyMarkdown) : friendlyMarkdown;
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      return window.DOMPurify.sanitize(raw, {USE_PROFILES: {html: true}});
    }
    // Fail closed with the built-in allow-list when DOMPurify is not bundled.
    return sanitise(raw);
  };
})();
