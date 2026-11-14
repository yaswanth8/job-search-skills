// LinkedIn post search: make sure the sort dropdown is on "Latest" (newest posts first), not "Top Match".
// The plan's URLs carry sortBy="date_posted", which selects Latest; LinkedIn can drop it (a typed search, a
// filter change, a layout change), so run this after every post-search load, before linkedin_posts.js.
// With no sort chosen the pill reads "Sort by" (Top Match applies). Top-level await; prints "already Latest", "switched to Latest", or what it found instead.
// The pill is a <div aria-label="Filter by Latest"> (not a <button>) in the Nov 2026 layout.
const sortPill = () => [...document.querySelectorAll('[aria-label^="Filter by"], button')].find(b =>
  /^(Filter by )?(Top match|Latest|Sort by)$/i.test((b.getAttribute('aria-label') || b.innerText || '').trim()));
const pillText = b => (b.innerText || b.getAttribute('aria-label') || '').replace(/^Filter by /i, '').trim();
const wait = ms => new Promise(r => setTimeout(r, ms));
let pill = sortPill(), result;
if (!pill) result = 'NO SORT DROPDOWN: not a posts search page, or the layout changed';
else if (/^latest$/i.test(pillText(pill))) result = 'already Latest';
else {
  pill.click(); await wait(1200);
  // Options are plain text beside an unlabelled radio input: take the radio whose nearby text is exactly "Latest".
  const near = r => { let e = r; for (let k = 0; k < 4 && e; k++) { e = e.parentElement; const t = ((e && e.innerText) || '').trim(); if (/^latest$/i.test(t)) return true; if (t.length > 40) return false; } return false; };
  const opt = [...document.querySelectorAll('input[type=radio], [role=radio], [role=menuitemradio]')].find(near)
    || [...document.querySelectorAll('label, span, p, div')].filter(e => /^latest$/i.test((e.innerText || '').trim())).sort((a, b) => a.children.length - b.children.length)[0];
  if (!opt) result = 'LATEST OPTION NOT FOUND in the dropdown';
  else {
    opt.click(); await wait(500);
    const show = [...document.querySelectorAll('a, button, [role=button]')].find(b => /^show( \d+\+?)? results$/i.test((b.innerText || '').trim()));
    if (show) show.click();   // "Show results" is a link (<a>) in the Nov 2026 layout
    await wait(3500);
    pill = sortPill();
    result = pill && /^latest$/i.test(pillText(pill)) ? 'switched to Latest' : 'SWITCH FAILED: pill shows ' + (pill ? pillText(pill) : 'nothing');
  }
}
result
