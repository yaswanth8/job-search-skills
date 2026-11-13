// Indeed job page (/viewjob?jk=...): apply mode, header facts and the description sentences vetting needs.
// PART = -1 gives the key sentences, plus `hiring:` and `contacts:` lines when the posting names someone to reach; 0, 1, 2... page through the raw description (900 characters each).
// applyMode company_site sends the job to the company-site flow. The apply link's URL is hidden by the
// browser's privacy filter: click it and read the host of the tab it opens.
window.__ij = (PART = -1) => {
;
  const t = document.body.innerText.replace(/\s+\n/g, '\n');
  const i = t.indexOf('Full job description');
  const end = ['Report job', 'Hiring Lab', 'Return to Search Result'].map(m => t.indexOf(m, i + 1)).filter(k => k > 0).sort((a, b) => a - b)[0] || t.length;
  const btn = [...document.querySelectorAll('button, a')].map(e => e.innerText.trim()).find(s => /Apply (now|with Indeed|on company site)/i.test(s)) || '';
  const mode = /company site/i.test(btn) || document.querySelector('#applyButtonLinkContainer a[href]') ? 'company_site' : 'indeed_apply';
  const desc = i >= 0 ? t.slice(i + 20, end).trim() : '';
  const head = t.slice(0, i > 0 ? i : 600).split('\n').slice(-12).join(' / ').slice(0, 260);
  const top = `jk ${new URLSearchParams(location.search).get('jk')} | applyMode=${mode} chars=${desc.length}`;
  if (PART >= 0) return `${top} part ${PART} of ${Math.ceil(desc.length / 900) - 1}\n` + desc.slice(PART * 900, PART * 900 + 900);
  const key = /java|spring|sponsor|visa|h-?1b|citizen|clearance|green card|years|yrs|remote|hybrid|on-?site|in office|relocat|resident|w-?2|c2c|contract|full.time|part.time|required|\$|salary|rate|vue|\.net|c#|python|golang|react|angular/i;
  const sents = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim()).filter(x => x.length > 12 && key.test(x));
  // who to reach: any email or phone in the description, plus a recruiter named on the page
  const em = [...new Set(desc.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/\.(png|jpg|gif)$/i.test(x) && !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const ph = [...new Set(desc.match(/(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}/g) || [])].slice(0, 2);
  const rl = t.split('\n').map(x => x.trim()); const ri = rl.findIndex(x => /^(Recruiter|Contact|Hiring manager|Point of contact)\b:?/i.test(x));
  const rn = ri >= 0 ? (rl[ri].replace(/^(Recruiter|Contact|Hiring manager|Point of contact)\b:?/i, '').replace(/^[:\s-]+/, '') || rl[ri + 1] || '').slice(0, 40) : '';
  const who = (rn ? `hiring: ${rn} | Recruiter\n` : '') + (em.length || ph.length ? `contacts: ${em.concat(ph).join(', ')}\n` : '');
  return `${top}\n${head}\n${who}` + sents.join(' ').slice(0, 640 - who.length);
};
__ij(-1)
