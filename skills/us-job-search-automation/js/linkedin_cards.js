// LinkedIn search results: one line per card, 8 per call (javascript_tool cuts output past ~1,000 characters).
// Raise PAGE (0, 1, 2...) until the header says you have read them all.
// Line: id|title|company|location|pay|tags. id is blank (cards carry no ids); tags: applied, viewed, easy.
// Save the lines to a .txt file and run vet.py --mode card on it.
(() => {
  const PAGE = 0, N = 8;
  const L = (document.querySelector('main') || document.body).innerText.split('\n').map(s => s.trim()).filter(Boolean);
  const locRe = /\((Remote|Hybrid|On-site)\)$|United States$|, [A-Z]{2}( \d{5})?$|Metropolitan Area$/;
  const cut = (s, n) => String(s || '').replace(/\|/g, '/').slice(0, n);
  const rows = [], seen = new Set();
  for (let i = 2; i < L.length; i++) {
    if (!locRe.test(L[i])) continue;
    const company = L[i - 1], title = L[i - 2].replace(/\s*\(Verified job\)$/, '');
    if (title === company || title.length > 140 || seen.has(title + company + L[i])) continue;
    seen.add(title + company + L[i]);
    const tail = L.slice(i + 1, i + 7), stop = tail.findIndex(l => l === 'Easy Apply' || l === 'Applied');
    const block = (stop >= 0 ? tail.slice(0, stop + 1) : tail).join(' ');
    const pay = (block.match(/\$[\d.,]+K?\/(hr|yr)( - \$[\d.,]+K?\/(hr|yr))?/) || [''])[0];
    const tags = [/\bApplied\b/.test(block) && 'applied', /\bViewed\b/.test(block) && 'viewed', /Easy Apply/.test(block) && 'easy'].filter(Boolean);
    rows.push(['', cut(title, 70), cut(company, 30), cut(L[i], 40), pay, tags.join(',')].join('|'));
  }
  const page = rows.slice(PAGE * N, PAGE * N + N);
  return `${rows.length} cards, page ${PAGE} of ${Math.max(0, Math.ceil(rows.length / N) - 1)}\n` + page.join('\n');
})()
