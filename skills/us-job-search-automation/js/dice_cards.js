// Dice search results: one line per card, 6 per call (javascript_tool cuts output past ~1,000 characters).
// Line: id|title|company|location|pay|tags (id dice-<uuid>; tags: posted age, employment type, applied).
// A card ([data-testid="job-card"]) reads: title, company, "Remote • Today", type, pay. Raise PAGE for more.
// If this returns 0 cards, Dice changed its markup: fall back to get_page_text and read the cards by eye.
(() => {
  const PAGE = 0, N = 6;
  const cut = (s, n) => String(s || '').replace(/\|/g, '/').replace(/\s+/g, ' ').trim().slice(0, n);
  const rows = [], seen = new Set();
  for (const a of document.querySelectorAll('a[href*="/job-detail/"]')) {
    const m = a.href.match(/job-detail\/([0-9a-f-]{36})/);
    if (!m || seen.has(m[1])) continue;
    seen.add(m[1]);
    let card = a.closest('[data-testid="job-card"]');
    if (!card) { card = a; while (card.parentElement && String(card.innerText || '').split('\n').filter(s => s.trim()).length < 4) card = card.parentElement; }
    const L = String(card.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    const title = String(a.getAttribute('aria-label') || '').replace(/^View Details for /, '').replace(/\s*\([0-9a-f]{20,}\)\s*$/, '') || L[0] || '';
    const ti = Math.max(0, L.findIndex(l => l === title));
    const where = L.find(l => l.includes('•')) || '';
    const [loc, age] = where.split('•').map(s => s.trim());
    const type = L.find(l => /^(full.time|part.time|contract|third party|contract to hire)/i.test(l)) || '';
    const pay = L.find(l => /\$\s?\d|depends on experience/i.test(l)) || '';
    const tags = [age, type, L.some(l => /^applied$/i.test(l)) && 'applied'].filter(Boolean).join(',');
    rows.push(['dice-' + m[1], cut(title, 70), cut(L[ti + 1] !== where && !/^(Remote|Hybrid|On-?site)\b|•|, [A-Z]{2}$/.test(L[ti + 1] || '') ? L[ti + 1] : '', 30), cut(loc, 40), cut(pay, 40), cut(tags, 40)].join('|'));
  }
  const page = rows.slice(PAGE * N, PAGE * N + N);
  return `${rows.length} cards, page ${PAGE} of ${Math.max(0, Math.ceil(rows.length / N) - 1)}\n` + page.join('\n');
})()
