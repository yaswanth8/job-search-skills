// LinkedIn search results (new layout): open one card and read the job in the right-hand pane, no page load.
// Paste once per results page (top-level await; output under ~950 characters), then: await __o2('<title>', '<company>')
// Prints "TITLE OK" or "TITLE MISMATCH: page is ..." (a shorter title can open a longer one: "Java Backend Developer"
// opened "Senior Java Backend Developer" on Nov 12; save the job under the title the page shows), the job id,
// `hiring:` and `contacts:` lines, and the key description sentences. Easy Apply comes from the card's `easy` tag.
window.__open = async (title, company) => {
  const main = document.querySelector('main') || document.body;
  const cands = [...main.querySelectorAll('li, div[role="button"], a, div')].filter(e => { const t = e.innerText || ''; return t.includes(title) && t.includes(company) && t.length < 600; });
  const el = cands.sort((a, b) => a.innerText.length - b.innerText.length)[0];
  if (!el) return 'NOT FOUND ' + title;
  (el.querySelector('a, [role=button]') || el).click();
  await new Promise(r => setTimeout(r, 2800));
  const id = new URLSearchParams(location.search).get('currentJobId');
  const t = main.innerText, i = t.indexOf('About the job');
  const desc = i >= 0 ? t.slice(i + 13, i + 9000) : '';
  const hi = t.indexOf('Meet the hiring team');
  const hl = hi >= 0 ? t.slice(hi + 20, hi + 300).split('\n').map(x => x.trim()).filter(x => x && !/^(•|\d|Job poster|Message)/.test(x)) : [];
  const key = /java|spring|sponsor|visa|h-?1b|citizen|clearance|green card|years|yrs|remote|hybrid|on-?site|in office|relocat|w-?2|c2c|contract|full.time|required|\$|salary|rate|react|angular|python|\.net|c#|golang|kotlin|local|public trust/i;
  const sents = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim()).filter(x => x.length > 12 && key.test(x));
  const em = [...new Set(desc.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const who = (hl.length ? `hiring: ${hl[0].replace(/\s*•.*$/, '').slice(0, 40)} | ${(hl[1] || '').slice(0, 50)}\n` : '') + (em.length ? `contacts: ${em.join(', ')}\n` : '');
  return (`id ${id}\n${who}` + sents.join(' ')).replace(/https?:\S+/g, '').replace(/\?/g, '').slice(0, 900);
};
window.__o2 = async (title, company) => {
  const r = await __open(title, company), dt = document.title.split(' | ');
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim();
  return (norm(dt[0]) === norm(title) && (dt[1] || '').includes(company) ? 'TITLE OK ' : 'TITLE MISMATCH: page is ' + dt.slice(0, 2).join(' / ') + ' ') + r.slice(0, 850);
};
'ready'
