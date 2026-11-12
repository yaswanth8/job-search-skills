// LinkedIn: on a search page after clicking a card, returns the selected job's id.
// On /jobs/view/<id>/, returns the header plus the description sentences vetting needs, paged by PART
// (javascript_tool cuts output past ~1,000 characters). PART = -1 gives the key sentences; 0, 1, 2... the raw text.
// PART = -1 also prints a `hiring:` line (name | title) and a `contacts:` line (emails, phones) when present:
// put them in the posting object as poster {name, title} and inside description, so the tracker row shows who to reach.
(() => {
  const PART = -1;
  const fromPath = (location.pathname.match(/\/jobs\/view\/(?:[^/]*-)?(\d+)/) || [])[1];
  const id = fromPath || new URLSearchParams(location.search).get('currentJobId');
  if (!fromPath) return 'id ' + id;
  const t = (document.querySelector('main') || document.body).innerText.replace(/\n{2,}/g, '\n');
  const s = t.indexOf('About the job');
  let e = t.length;
  for (const m of ['Benefits found in job post', 'Set alert for similar jobs', 'See how you compare', 'About the company', 'More jobs']) { const k = t.indexOf(m, s + 1); if (k > 0 && k < e) e = k; }
  const head = t.slice(0, Math.max(0, s)).split('\n').slice(0, 8).join(' / ').slice(0, 260);
  const desc = s >= 0 ? t.slice(s + 13, e).trim() : '';
  const flags = `easyApply=${!!document.querySelector('button[aria-label*="Easy Apply"]')} applied=${/Application submitted/.test(t.slice(0, 900))} chars=${desc.length}`;
  if (PART >= 0) return `${flags} part ${PART} of ${Math.ceil(desc.length / 900) - 1}\n` + desc.slice(PART * 900, PART * 900 + 900);
  const key = /java|spring|sponsor|visa|h-?1b|citizen|clearance|green card|years|yrs|remote|hybrid|on-?site|in office|relocat|resident|w-?2|c2c|contract|full.time|part.time|required|\$|salary|rate|vue|\.net|c#|python|golang|react|angular/i;
  const sents = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim()).filter(x => x.length > 12 && key.test(x));
  // who to reach: the "Meet the hiring team" person, plus any email or phone in the description
  const hi = t.indexOf('Meet the hiring team');
  const hl = hi >= 0 ? t.slice(hi + 20, hi + 300).split('\n').map(x => x.trim()).filter(x => x && !/^(•|\d|Job poster|Message)/.test(x)) : [];
  const em = [...new Set(desc.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const ph = [...new Set(desc.match(/(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}/g) || [])].slice(0, 2);
  const who = (hl.length ? `hiring: ${hl[0].replace(/\s*•.*$/, '').slice(0, 40)} | ${(hl[1] || '').slice(0, 60)}\n` : '') + (em.length || ph.length ? `contacts: ${em.concat(ph).join(', ')}\n` : '');
  return `id ${id} | ${flags}\n${head}\n${who}` + sents.join(' ').slice(0, 640 - who.length);
})()
