// LinkedIn: on a search page after clicking a card, returns the selected job's id.
// On /jobs/view/<id>/, returns the header plus the description sentences vetting needs, paged by PART
// (javascript_tool cuts output past ~1,000 characters). PART = -1 gives the key sentences; 0, 1, 2... the raw text.
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
  return `id ${id} | ${flags}\n${head}\n` + sents.join(' ').slice(0, 640);
})()
