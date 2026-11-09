// LinkedIn content search (/search/results/content/?keywords=...): recruiter posts, 2 per call
// (javascript_tool cuts output past ~1,000 characters). Paste once; then call __lp(1), __lp(2)... (several
// in one browser_batch) until the header says you have read them all; scroll the page and start again from PAGE 0 for more.
// Each post is a "@@" header line, its key lines (role, location, rate, visa, C2C/W2), and a
// "contacts:" line with every email and phone found in the full text:
//   @@ urn|author|author title|author url|age
// LinkedIn's 2026 search page has no post ids: the header's first field is then empty and posts.py
// builds the row link from the author's profile. Run once to expand "… more", wait a second, run again.
// Save all pages to a .txt file and run posts.py on it. View-only: it expands "…more", nothing else.
window.__lp = (PAGE = 0, N = 2) => {
  const main = document.querySelector('main') || document.body;
  main.querySelectorAll('button').forEach(b => { if (/^(…|\.\.\.)?\s*(see )?more$/i.test((b.innerText || '').trim())) { try { b.click(); } catch (e) {} } });
  let nodes = [...main.querySelectorAll('[data-urn^="urn:li:activity"], [data-urn^="urn:li:ugcPost"], [data-urn^="urn:li:share"], div.feed-shared-update-v2')];
  if (!nodes.length) nodes = [...main.querySelectorAll('[role="listitem"][componentkey^="update-card"], [role="listitem"]')].filter(n => (n.innerText || '').length > 200);
  if (!nodes.length) nodes = [...main.querySelectorAll('li, article')].filter(n => (n.innerText || '').length > 200 && n.querySelector('a[href*="/in/"], a[href*="/company/"]') && !n.querySelector('li, article'));
  const cut = (s, n) => String(s || '').replace(/[|\n]/g, ' ').trim().slice(0, n);
  const key = /hiring|position|role|title|requirement|location|remote|hybrid|on-?site|rate|\$|duration|month|c2c|corp|w-?2|contract|full.?time|visa|h-?1b|usc|gc\b|citizen|sponsor|clearance|years|yrs|skills?|java|spring|react|angular|python|\.net|aws|looking for|open to work|hotlist|bench/i;
  const seen = new Set(), posts = [];
  for (const n of nodes) {
    const urn = n.getAttribute('data-urn') || ((n.querySelector('[data-urn]') || {}).getAttribute ? n.querySelector('[data-urn]').getAttribute('data-urn') : '') || '';
    const L = (n.innerText || '').replace(/[\u200b\u200c\u200d\ufeff]/g, '').split('\n').map(s => s.trim()).filter(s => s && !/^(Feed post|Follow|Join|Connect|Following|Promoted|…\s*more|•\s*(\d(st|nd|rd|th)\+?|Following)?)$/i.test(s));
    if (L.length < 3) continue;
    const ai = L.findIndex(l => /^\d+\s?(mo|yr|m|h|d|w)\b/.test(l));
    const body = n.querySelector('.update-components-text, .feed-shared-update-v2__description, .feed-shared-inline-show-more-text, [class*="commentary"]');
    let text = (body ? body.innerText : L.slice(ai >= 0 ? ai + 1 : 3).join('\n')).replace(/\s*…\s*more\s*$/i, '');
    const end = text.search(/\n(Like|Comment|Repost|Send)\n/); if (end > 0) text = text.slice(0, end);
    if (text.trim().length < 40 || seen.has(urn || text.slice(0, 120))) continue;
    seen.add(urn || text.slice(0, 120));
    const a = n.querySelector('a[href*="/in/"], a[href*="/company/"]') || n.querySelector('a[href*="/groups/"]');
    const title = L.slice(1, ai > 0 ? ai : 5).find(l => l.length > 8 && l !== L[0] && !/^(•|\d+(st|nd|rd|th)|Follow|Promoted|\d+\s?(m|h|d|w)\b)/i.test(l));
    const grp = a && /\/groups\//.test(a.href) && title;   // a post inside a group: line 1 is the group, line 2 the person
    const head = ['@@ ' + cut(urn, 40), cut((grp ? title : L[0]).replace(/\s*(•.*|View .* profile.*)$/i, ''), 40), cut(grp ? L[0] : title, 60), cut(a ? a.href.split('?')[0] : '', 70), ai >= 0 ? (L[ai].match(/^\d+\s?(?:mo|yr|m|h|d|w)/) || [''])[0] : ''].join('|');
    const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
    let keep = '', first = true;
    for (const l of lines) { if ((first || key.test(l)) && keep.length < 250) keep += l.slice(0, 110) + '\n'; first = false; }
    const em = [...new Set(text.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].slice(0, 2);
    const ph = [...new Set(text.match(/(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}/g) || [])].slice(0, 2);
    posts.push(head + '\n' + keep + 'contacts: ' + em.concat(ph).join(', '));
  }
  if (!posts.length) return 'NO POSTS FOUND (markup changed or not signed in). Read the page text instead:\n' + main.innerText.replace(/\n{2,}/g, '\n').slice(PAGE * 800, PAGE * 800 + 800);
  return `${posts.length} posts, page ${PAGE} of ${Math.max(0, Math.ceil(posts.length / N) - 1)}\n` + posts.slice(PAGE * N, PAGE * N + N).join('\n');
};
window.__lp(0)
