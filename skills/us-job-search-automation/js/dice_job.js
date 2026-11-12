// Dice job page (/job-detail/<uuid>): the facts vetting needs in one short read.
// Returns employment type, workplace, "Able to Sponsor", pay, applied state, who to reach (hiring: name, contacts: emails
// and phones anywhere in the description or the recruiter card), and the key description sentences.
// The header's "Remote in <city>" is Dice's search label: trust the workplace field (Remote / Hybrid / On-site).
(() => {
  const t = (document.querySelector('main') || document.body).innerText;
  const head = t.slice(0, 700);
  const pick = re => (head.match(re) || [''])[0];
  const facts = [
    'type=' + (pick(/Full Time|Part Time|Contract (W2|Corp-To-Corp|Independent)[^\n]*|Contract to Hire|Third Party/i) || '?'),
    'workplace=' + (pick(/\n(Remote|Hybrid|On-site)\n/).trim() || '?'),
    'sponsor=' + /Able to Sponsor/i.test(head),
    'pay=' + (pick(/USD[^\n]+|\$[\d.,]+[^\n]{0,40}|Depends on Experience/) || '?'),
    'applied=' + /\bApplied\b/.test(head) + ' continue=' + /Continue Application/.test(head),
  ].join(' ');
  const title = (t.split('\n').map(s => s.trim()).filter(Boolean).find(l => l.length > 8 && !/^(Job Search|Companies|Career Resources|Apply|Continue Application)$/.test(l)) || '');
  const s = t.indexOf('Summary'), e = t.indexOf('Dice Id:');
  const desc = s >= 0 ? t.slice(s + 7, e > s ? e : s + 9000) : '';
  const key = /java|spring|sponsor|visa|h-?1b|citizen|clearance|green card|years|yrs|remote|hybrid|on-?site|in office|relocat|resident|w-?2|c2c|contract|full.time|required|\$|rate|vue|\.net|c#|python|golang|react|angular/i;
  const sents = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim()).filter(x => x.length > 12 && key.test(x));
  // who to reach: any email or phone in the description, plus a recruiter named on the page
  const em = [...new Set(t.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/\.(png|jpg|gif)$/i.test(x) && !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const ph = [...new Set(t.match(/(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}/g) || [])].slice(0, 2);
  const rl = t.split('\n').map(x => x.trim()); const ri = rl.findIndex(x => /^(Posted by|Recruiter|Contact|Recruiting contact|Point of contact)\b:?/i.test(x));
  const rn = ri >= 0 ? (rl[ri].replace(/^(Posted by|Recruiter|Contact|Recruiting contact|Point of contact)\b:?/i, '').replace(/^[:\s-]+/, '') || rl[ri + 1] || '').slice(0, 40) : '';
  const who = (rn ? `hiring: ${rn} | Recruiter\n` : '') + (em.length || ph.length ? `contacts: ${em.concat(ph).join(', ')}\n` : '');
  return `${facts}\n${head.split('\n').filter(Boolean).slice(0, 6).join(' / ').slice(0, 200)}\n${who}` + sents.join(' ').slice(0, 600 - who.length);
})()
