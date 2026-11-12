// Dice job pages without page loads: one same-site fetch per job, read from the page's JobPosting data.
// Paste once on any dice.com page, then: await __dr('<uuid>'). Prints title, company, employment type, datePosted
// (use it for age_hours: Dice's "Today" filter also lists reposted jobs a week or more old), contacts, key sentences.
window.__dr = async (uuid) => {
  const h = await (await fetch('/job-detail/' + uuid)).text();
  const d = new DOMParser().parseFromString(h, 'text/html');
  let ld = {};
  d.querySelectorAll('script[type="application/ld+json"]').forEach(s => { try { const j = JSON.parse(s.textContent); if (j['@type'] === 'JobPosting') ld = j; } catch (e) {} });
  const desc = new DOMParser().parseFromString(ld.description || '', 'text/html').body.innerText || '';
  const em = [...new Set(desc.match(/[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g) || [])].filter(x => !/accomm?odation|accessib|disabilit/i.test(x)).slice(0, 2);
  const ph = [...new Set(desc.match(/(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}/g) || [])].slice(0, 2);
  const key = /java|spring|sponsor|visa|h-?1b|citizen|clearance|green card|years|yrs|remote|hybrid|on-?site|local|w-?2|c2c|corp|contract|full.time|required|\$|rate|react|angular|python|\.net|c#|kotlin/i;
  const sents = desc.split(/(?<=[.!?])\s+|\n/).map(x => x.trim()).filter(x => x.length > 12 && key.test(x));
  const org = (ld.hiringOrganization || {}).name || '', typ = [].concat(ld.employmentType || []).join(',');
  return (`${uuid.slice(0, 8)} | ${ld.title} | ${org} | ${typ} | posted ${ld.datePosted} | contacts: ${em.concat(ph).join(', ')}\n` + sents.join(' ')).replace(/https?:\S+/g, '').replace(/\?/g, '').slice(0, 900);
};
'ready'
