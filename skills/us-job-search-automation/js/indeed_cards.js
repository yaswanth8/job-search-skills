// Indeed search results: one line per card, 8 per call (javascript_tool cuts output past ~1,000 characters).
// Line: id|title|company|location|pay|tags (id indeed-<jk>; tags: easy, new). Raise PAGE for more.
// Drops ghost ids (runs like 890abcdef0123456). When Indeed found nothing it fills the page with
// "similar jobs": the header then says so, and those cards are not search results.
(() => {
  const PAGE = 0, N = 8, SEQ = '0123456789abcdef';
  const ghost = id => [...Array(Math.max(0, id.length - 5)).keys()].some(k => SEQ.includes(id.slice(k, k + 6)));
  const cut = (s, n) => String(s || '').replace(/\|/g, '/').replace(/\s+/g, ' ').trim().slice(0, n);
  const noResults = /did not match any jobs|didn.t find any results|no results found/i.test(document.body.innerText.slice(0, 4000));
  const rows = [], seen = new Set();
  document.querySelectorAll('.job_seen_beacon, [data-testid="slider_item"]').forEach(c => {
    const a = c.querySelector('a[data-jk]'), jk = a && a.getAttribute('data-jk');
    if (!jk || ghost(jk) || seen.has(jk)) return;
    seen.add(jk);
    const q = sel => (c.querySelector(sel) || {}).innerText || '';
    const title = (c.querySelector('h2 span[title]') || {}).title || c.innerText.split('\n')[0];
    const pay = c.innerText.split('\n').map(s => s.trim()).find(l => /^\$/.test(l)) || '';
    const tags = [/Easily apply/.test(c.innerText) && 'easy', /\bNew\b/.test(c.innerText) && 'new'].filter(Boolean);
    rows.push(['indeed-' + jk, cut(title, 70), cut(q('[data-testid="company-name"]'), 30), cut(q('[data-testid="text-location"]'), 40), cut(pay, 40), tags.join(',')].join('|'));
  });
  const page = rows.slice(PAGE * N, PAGE * N + N);
  return (noResults ? 'NO RESULTS: these are Indeed suggestions, not matches. ' : '') + `${rows.length} cards, page ${PAGE} of ${Math.max(0, Math.ceil(rows.length / N) - 1)}\n` + page.join('\n');
})()
