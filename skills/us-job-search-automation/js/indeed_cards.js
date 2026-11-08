// Indeed search results: one JSON row per card. Run with javascript_tool on /jobs?q=...&l=...&fromage=3.
// Drops ghost duplicates (ids that are runs like 890abcdef0123456 / 456789abcdef0123 that Indeed injects).
(() => {
  const SEQ = '0123456789abcdef';
  const ghost = id => [...Array(Math.max(0, id.length - 5)).keys()].some(k => SEQ.includes(id.slice(k, k + 6)));
  const rows = [...document.querySelectorAll('.job_seen_beacon, [data-testid="slider_item"]')].map(c => {
    const a = c.querySelector('a[data-jk]');
    const jk = a && a.getAttribute('data-jk');
    const t = c.innerText.split('\n').map(s => s.trim()).filter(Boolean);
    const title = (c.querySelector('h2 span[title]') || {}).title || t[0];
    const company = (c.querySelector('[data-testid="company-name"]') || {}).innerText || '';
    const location = (c.querySelector('[data-testid="text-location"]') || {}).innerText || '';
    const pay = t.find(l => /^\$/.test(l)) || '';
    return { jk, link: jk ? `https://www.indeed.com/viewjob?jk=${jk}` : '', title, company, location, pay,
             easyApply: /Easily apply/.test(c.innerText), isNew: /\bNew\b/.test(c.innerText), ghost: jk ? ghost(jk) : true };
  });
  const seen = new Set();
  return JSON.stringify(rows.filter(r => r.jk && !r.ghost && !seen.has(r.jk) && seen.add(r.jk)));
})()
