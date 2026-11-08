// Dice search results: one row per card (best effort; Dice changes its markup often).
// Each card links to /job-detail/<uuid>; the card text carries title, company, location, type and age.
// If this returns [], fall back to get_page_text and read the cards by eye.
(() => {
  const seen = new Set();
  const rows = [];
  for (const a of document.querySelectorAll('a[href*="/job-detail/"]')) {
    const m = a.href.match(/job-detail\/([0-9a-f-]{36})/);
    if (!m || seen.has(m[1])) continue;
    seen.add(m[1]);
    const card = a.closest('[data-testid*="card"], dhi-search-card, article, li, div[class*="card"]') || a.parentElement;
    const lines = (card ? card.innerText : a.innerText).split('\n').map(s => s.trim()).filter(Boolean);
    rows.push({
      uuid: m[1], link: `https://www.dice.com/job-detail/${m[1]}`,
      title: a.innerText.trim() || lines[0], lines: lines.slice(0, 10),
      remote: lines.some(l => /remote/i.test(l)),
      age: lines.find(l => /(ago|today|yesterday|Posted)/i.test(l)) || '',
    });
  }
  return JSON.stringify(rows);
})()
