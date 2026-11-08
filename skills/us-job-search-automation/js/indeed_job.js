// Indeed job page (/viewjob?jk=...): header facts, apply mode and the trimmed description.
// applyMode: "indeed_apply" (Apply with Indeed / Easily apply) or "company_site" (Apply on company site).
(() => {
  const t = document.body.innerText.replace(/\s+\n/g, '\n');
  const i = t.indexOf('Full job description');
  const end = ['Report job', 'Hiring Lab', 'Return to Search Result'].map(m => t.indexOf(m, i + 1)).filter(k => k > 0).sort((a, b) => a - b)[0] || t.length;
  const btn = [...document.querySelectorAll('button, a')].map(e => e.innerText.trim()).find(s => /Apply (now|with Indeed|on company site)/i.test(s)) || '';
  const companySite = /company site/i.test(btn) || !!document.querySelector('#applyButtonLinkContainer a[href]');
  const ext = document.querySelector('#applyButtonLinkContainer a[href]');
  return JSON.stringify({
    jk: new URLSearchParams(location.search).get('jk'),
    header: t.slice(0, i > 0 ? i : 600).split('\n').slice(-25).join('\n').slice(0, 1200),
    applyMode: companySite ? 'company_site' : 'indeed_apply',
    applyUrl: ext ? ext.href : '',
    description: (i >= 0 ? t.slice(i + 20, end) : '').trim().slice(0, 6000),
  });
})()
