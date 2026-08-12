(() => {
  const form = document.getElementById('school-finder-form');
  const input = document.getElementById('postcode');
  const button = form?.querySelector('button[type=submit]');
  const entryYear = document.getElementById('entry-year');
  const childGender = document.getElementById('child-gender');
  const filterSummary = document.getElementById('finder-summary');
  const filterCount = document.getElementById('filter-result-count');
  let currentSchools = [];
  let activeFilter = 'all';
  let mockBySchool = new Map();
  const COMMON_MOCK_ID = 'common-diagnostic-1';

  const normaliseName = (value) => String(value ?? '').toLocaleLowerCase('en-GB').replace(/[^a-z0-9]+/g, ' ').trim();

  async function loadMockCatalogue() {
    try {
      const response = await fetch('/api/elevenplus/mock-exams', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      mockBySchool = new Map();
      (data.exams || []).filter(exam => exam.category === 'school_target' && exam.school).forEach(exam => {
        const key = normaliseName(exam.school);
        if (key && !mockBySchool.has(key)) mockBySchool.set(key, exam);
      });
    } catch (_) {
      mockBySchool = new Map();
    }
  }

  function findSchoolMock(schoolName) {
    const key = normaliseName(schoolName);
    if (mockBySchool.has(key)) return mockBySchool.get(key);
    for (const [schoolKey, exam] of mockBySchool.entries()) {
      if (key && schoolKey && (key.includes(schoolKey) || schoolKey.includes(key))) return exam;
    }
    return null;
  }

  function mockLink(schoolName) {
    const exam = findSchoolMock(schoolName);
    if (exam) {
      return `<a class="school-mock-link target" href="/elevenplus-mock-exams?examId=${encodeURIComponent(exam.id)}">Practice ${esc(exam.school)} mock</a>`;
    }
    return `<a class="school-mock-link common" href="/elevenplus-mock-exams?examId=${encodeURIComponent(COMMON_MOCK_ID)}">Try the Common 11+ Diagnostic</a>`;
  }
  const status = document.getElementById('finder-status');
  const results = document.getElementById('finder-results');
  const list = document.getElementById('school-list');
  const area = document.getElementById('results-area');
  const mapPanel = document.getElementById('finder-map-panel');
  const mapFrame = document.getElementById('school-map');
  const mapFallback = document.getElementById('map-fallback');
  const mapOpenLink = document.getElementById('map-open-link');
  if (!form) return;
  // School Finder UI v2026-08-11. All optional DOM nodes are guarded so a partial/stale page cannot crash lookup.

  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const setStatus = (message, error = false) => {
    if (!status) return;
    status.hidden = !message;
    status.className = `finder-status${error ? ' error' : ''}`;
    status.textContent = message || '';
  };

  const card = (school, index) => {
    const site = school.website ? `<a class="primary" href="${esc(school.website)}" target="_blank" rel="noopener">School website</a>` : '';
    const search = `https://www.get-information-schools.service.gov.uk/Search?SearchType=Text&SearchText=${encodeURIComponent(school.name)}`;
    const badge = school.eligibility && school.eligibility.startsWith('Usually not') ? 'not-suitable' : 'possible';
    const map = school.google_maps_url ? `<a class="map-link" href="${esc(school.google_maps_url)}" target="_blank" rel="noopener" data-map-school="${esc(school.name)}">View home → school on Google Maps</a>` : '';
    return `<article class="school-card"><div class="school-top"><h3>${index + 1}. ${esc(school.name)}</h3><span class="distance">${esc(school.distance_km)} km</span></div><div class="school-meta"><span>${esc(school.route || school.type || 'Secondary school')}</span><span>${esc(normaliseGender(school.gender, school.name))}</span></div><p class="eligibility-badge ${badge}">${esc(school.eligibility || 'Potential option — check admissions')}</p><p class="school-note"><strong>Admissions:</strong> ${esc(school.admission_hint)}</p><p class="school-note">${esc(school.level_note)}</p>${school.address ? `<p class="school-note">${esc(school.address)}</p>` : ''}<div class="school-actions"><a href="${search}" target="_blank" rel="noopener">Check DfE record</a>${mockLink(school.name)}${map}${site}</div></article>`;
  };

  function showMap(schools, allLocationsUrl, allLocationsEmbedUrl) {
    if (!mapPanel) return;
    mapPanel.hidden = false;
    if (mapFrame) {
      if (allLocationsEmbedUrl) {
        mapFrame.src = allLocationsEmbedUrl;
        mapFrame.hidden = false;
        mapFrame.title = `Google Maps showing home and ${schools.length} schools`;
        if (mapFallback) mapFallback.hidden = true;
      } else {
        mapFrame.hidden = true;
        mapFrame.removeAttribute('src');
        if (mapFallback) mapFallback.hidden = false;
      }
    }
    if (mapOpenLink) {
      mapOpenLink.href = allLocationsUrl || '#';
      mapOpenLink.textContent = `Open all ${schools.length} schools + home in Google Maps`;
      mapOpenLink.hidden = !allLocationsUrl;
    }
  }

  const normaliseGender = (value, name = '') => {
      const text = String(value ?? '').toLowerCase().trim();
      const schoolName = String(name ?? '').toLowerCase();
      if (text.includes('female') || text.includes('girls') || text === 'girl' || text === 'girls') return 'Girls';
      if (text.includes('male') || text.includes('boys') || text === 'boy' || text === 'boys') return 'Boys';
      // Safe fallback only for an unambiguous school name.
      if (/\\bfor girls\\b|\\bgirls school\\b|\\bgirls grammar\\b/.test(schoolName)) return 'Girls';
      if (/\\bfor boys\\b|\\bboys school\\b|\\bboys grammar\\b/.test(schoolName)) return 'Boys';
      if (text.includes('mixed') || text.includes('co-educ') || text.includes('coeduc') || text.includes('both')) return 'Co-educational';
      return 'Not stated';
    };
      const render = () => {
    const filtered = activeFilter === 'all' ? currentSchools : currentSchools.filter(s => {
      const gender = normaliseGender(s.gender, s.name);
      return s.route === activeFilter || gender === activeFilter;
    });
    if (list) list.innerHTML = filtered.map(card).join('');
    if (filterCount) filterCount.textContent = `${filtered.length} of ${currentSchools.length} schools shown`;
    if (filterSummary) filterSummary.hidden = currentSchools.length === 0;
  };

  filterSummary?.addEventListener('click', (event) => {
    const chip = event.target.closest('[data-filter]');
    if (!chip) return;
    activeFilter = chip.dataset.filter;
    filterSummary.querySelectorAll('.filter-chip').forEach(x => x.classList.toggle('active', x === chip));
    render();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const postcode = input.value.trim();
    if (!postcode) { setStatus('Please enter a postcode.', true); input.focus(); return; }
    button.disabled = true;
    if (results) results.hidden = true;
    setStatus('Finding nearby secondary schools…');
    await loadMockCatalogue();
    try {
      const response = await fetch('/api/schools/nearby', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({postcode, entry_year: entryYear?.value || 'Year 7', child_gender: childGender?.value || 'any'}) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'We could not find schools right now.');
      currentSchools = data.schools || [];
      activeFilter = 'all';
      filterSummary?.querySelectorAll('.filter-chip').forEach(x => x.classList.toggle('active', x.dataset.filter === 'all'));
      if (filterSummary) filterSummary.hidden = !currentSchools.length;
      render();
      if (currentSchools.length && mapPanel) showMap(currentSchools, data.google_maps_all_locations_url, data.google_maps_all_locations_embed_url);
      if (area) area.textContent = data.area ? `Around ${data.postcode} · local area: ${data.area}` : `Around ${data.postcode}`;
      if (results) results.hidden = false;
      setStatus(data.schools?.length ? `${data.schools.length} nearby schools found.` : 'No suitable secondary schools were found in the public directory for this postcode.', false);
      if (data.schools?.length && results) results.scrollIntoView({behavior:'smooth', block:'start'});
    } catch (error) {
      console.error('School Finder lookup failed:', error);
      const message = error && error.message === 'Failed to fetch'
        ? 'The school directory could not be reached just now. Please try again in a moment.'
        : (error.message || 'We could not complete the lookup. Please try again.');
      setStatus(message, true);
    } finally { button.disabled = false; }
  });
})();
