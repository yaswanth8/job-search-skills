// Company-site application form scanner (Greenhouse, Lever, Ashby, Workable, SmartRecruiters...). Read-only.
// First line: host, sign-in wall, CAPTCHA, submit buttons. Then one line per visible field, 12 per call
// (javascript_tool cuts output past ~1,000 characters; raise PAGE for more):
// index|type|required|label|current value|options. Map every field to a sourced answer before typing.
(() => {
  const PAGE = 0, N = 12;
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const cut = (s, n) => String(s ?? '').replace(/\|/g, '/').replace(/\s+/g, ' ').trim().slice(0, n);
  const labelFor = el => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText; }
    const aria = el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') || '').split(' ').map(id => (document.getElementById(id) || {}).innerText || '').join(' ');
    const wrap = el.closest('label, fieldset, .field, .application-question, [class*="question"], [class*="field"]');
    return aria || (wrap ? (wrap.querySelector('label, legend, [class*="label"]') || wrap).innerText.split('\n')[0] : '') || el.name || el.placeholder || '';
  };
  const fields = [...document.querySelectorAll('input, select, textarea')].filter(el => el.type !== 'hidden' && (vis(el) || el.type === 'file')).map((el, i) => {
    const label = labelFor(el);
    const req = el.required || el.getAttribute('aria-required') === 'true' || /\*\s*$/.test(label.trim());
    const val = el.type === 'file' ? (el.files && el.files.length ? el.files[0].name : '') : (el.type === 'checkbox' || el.type === 'radio') ? String(el.checked) : el.value;
    const opts = el.tagName === 'SELECT' ? [...el.options].map(o => o.text.trim()).slice(0, 8).join(';') : '';
    return [i, el.type || el.tagName.toLowerCase(), req ? 'REQ' : '', cut(label, 70), cut(val, 30), cut(opts, 90)].join('|');
  });
  const text = document.body.innerText.slice(0, 3000);
  const wall = /sign in|log in|create (an )?account|verification code/i.test(text) && !!document.querySelector('input[type=password]');
  const captcha = !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], [class*="captcha"]');
  const submits = [...document.querySelectorAll('button, input[type=submit]')].filter(vis).map(b => cut(b.innerText || b.value, 20)).filter(t => /submit|apply|send|next|continue|review/i.test(t));
  return `host=${location.hostname} signInWall=${wall} captcha=${captcha} submit=${submits.join(';')} fields=${fields.length} page ${PAGE}\n` + fields.slice(PAGE * N, PAGE * N + N).join('\n');
})()
