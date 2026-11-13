// LinkedIn search page: read the cards, then open many jobs from the same page, in ONE paste per page load.
// (Replaces linkedin_cards.js and linkedin_pane.js: one paste per search page, no page load per job.)
// Paste once after each navigate (a navigation erases it). Then, in the same browser_batch:
//   __lc(0), __lc(1) ...          cards, 8 per call: "|title|company|location||tags" (cards carry no ids; tags applied, viewed, easy)
//   await __run([[title, company], ...])   clicks each card, reads the right-hand pane, keeps the results (5-6 per call)
//   __get(0), __get(1) ...        one job per call: "title @@ company @@ OK|MISMATCH id <n>" + head, hiring, contacts, key sentences
// Trust MISMATCH: save the job under the title the page shows. Risky sentences (sponsorship, clearance, years, pay, location)
// come first, so a cut never drops them. Output has no URLs, "?", "=" or "&": the tool blocks query strings.
window.__lc = (PAGE) => {
  const N = 8;
  const L = (document.querySelector('main') || document.body).innerText.split('\n').map(s => s.trim()).filter(Boolean);
  const locRe = /\((Remote|Hybrid|On-site)\)$|United States$|, [A-Z]{2}( \d{5})?$|Metropolitan Area$/;
  const cut = (s, n) => String(s || '').replace(/\|/g, '/').slice(0, n);
  const rows = [], seen = new Set();
  for (let i = 2; i < L.length; i++) {
    if (!locRe.test(L[i])) continue;
    const company = L[i - 1], title = L[i - 2].replace(/\s*\(Verified job\)$/, '');
    if (title === company || title.length > 140 || /^(Be an early applicant|Promoted|Viewed)$/.test(company) || seen.has(title + company + L[i])) continue;
    seen.add(title + company + L[i]);
    const tail = L.slice(i + 1, i + 7), stop = tail.findIndex(l => l === 'Easy Apply' || l === 'Applied');
    const block = (stop >= 0 ? tail.slice(0, stop + 1) : tail).join(' ');
    const tags = [/\bApplied\b/.test(block) && 'applied', /\bViewed\b/.test(block) && 'viewed', /Easy Apply/.test(block) && 'easy'].filter(Boolean);
    rows.push(['', cut(title, 70), cut(company, 30), cut(L[i], 40), '', tags.join(',')].join('|'));
  }
  return `${rows.length} cards, page ${PAGE} of ${Math.max(0, Math.ceil(rows.length / N) - 1)}\n` + rows.slice(PAGE * N, PAGE * N + N).join('\n');
};
window.__open = async (title, company) => {
  const main = document.querySelector('main') || document.body;
  const el = [...main.querySelectorAll('li, div[role="button"], a, div')]
    .filter(e => { const t = e.innerText || ''; return t.includes(title) && t.includes(company) && t.length < 600; })
    .sort((a, b) => a.innerText.length - b.innerText.length)[0];
  if (!el) return 'NOT FOUND';
  (el.querySelector('a, [role=button]') || el).click();
  await new Promise(r => setTimeout(r, 2800));
  const id = new URLSearchParams(location.search).get('currentJobId');
  const t = main.innerText, i = t.indexOf('About the job');
  const head = (i >= 0 ? t.slice(Math.max(0, i - 700), i) : '').split('\n').map(x => x.trim())
    .filter(x => /Remote|Hybrid|On-site|\$|Full-time|Contract|Part-time|, [A-Z]{2}\b/.test(x)).slice(0, 5).join(' ; ').slice(0, 160);
  const desc = i >= 0 ? t.slice(i + 13, i + 12000) : '';
  const hi = t.indexOf('Meet the hiring team');
  const hl = hi >= 0 ? t.slice(hi + 20, hi + 300).split('\n').map(x => x.trim()).filter(x => x && !/^(•|\d|Job poster|Message)/.test(x)) : [];
  const pri = /sponsor|visa|h-?1b|citizen|clearance|green card|public trust|\bgc\b|\busc\b|w-?2|c2c|corp|\$|per hour|salary|local|on-?site|hybrid|in.office|reside|within \d+ miles|\d+\+? ?(years|yrs)/i;
  const key = /java|spring|remote|relocat|contract|full.time|required|react|angular|python|\.net|c#|golang|\bgo\b|kotlin|node|typescript/i;
  const all = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim())
    .filter(x => x.length > 12 && !/Median employee tenure|discriminat|equal (employment )?opportunity|without regard|#[A-Za-z]+ #|marathon/i.test(x));
  const sents = all.filter(x => pri.test(x)).concat(all.filter(x => !pri.test(x) && key.test(x)));
  const em = [...new Set(desc.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const who = (hl.length ? `hiring: ${hl[0].replace(/\s*•.*$/, '').slice(0, 40)} | ${(hl[1] || '').slice(0, 50)}\n` : '') + (em.length ? `contacts: ${em.join(', ')}\n` : '');
  return `id ${id}\nhead: ${head}\n${who}` + sents.join(' ');
};
window.__R = window.__R || [];
window.__run = async (pairs) => {
  window.__R = [];
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  for (const [t, c] of pairs) {
    const r = await window.__open(t, c), dt = document.title.split(' | ');
    const ok = norm(dt[0]) === norm(t) && (dt[1] || '').includes(c);
    window.__R.push(`${t} @@ ${c} @@ ` + (r === 'NOT FOUND' ? 'NOT FOUND' : (ok ? 'OK ' : `MISMATCH page=${norm(dt[0])} `) + r));
    await new Promise(z => setTimeout(z, 600 + Math.random() * 900));
  }
  return `${window.__R.length} read`;
};
window.__get = (i, part) => (window.__R[i] || 'NONE').replace(/https?:\S+/g, '').replace(/[?=&%]/g, ' ').slice((part || 0) * 950, (part || 0) * 950 + 950);
'ready'
