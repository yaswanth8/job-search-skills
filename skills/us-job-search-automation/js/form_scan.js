// Company-site application form scanner (Greenhouse, Lever, Ashby, Workable, SmartRecruiters...).
// Lists every visible field with its label, type, required flag, current value and options,
// so each one can be mapped to a profile answer BEFORE anything is typed. Read-only.
// Also reports whether the page is a sign-in / account wall (then the user applies, not Claude).
(() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const labelFor = el => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText.trim(); }
    const wrap = el.closest('label, fieldset, .field, .application-question, [class*="question"], [class*="field"], div');
    const aria = el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') || '').split(' ').map(id => (document.getElementById(id) || {}).innerText || '').join(' ');
    return (aria || (wrap ? (wrap.querySelector('label, legend, .label, [class*="label"]') || wrap).innerText : '') || el.name || el.placeholder || '').trim().split('\n')[0].slice(0, 160);
  };
  const fields = [...document.querySelectorAll('input, select, textarea')].filter(el => el.type !== 'hidden' && (vis(el) || el.type === 'file')).map((el, i) => ({
    i, tag: el.tagName.toLowerCase(), type: el.type || '', name: el.name || el.id || '',
    label: labelFor(el), required: el.required || el.getAttribute('aria-required') === 'true' || /\*\s*$/.test(labelFor(el)),
    value: el.type === 'file' ? (el.files && el.files.length ? el.files[0].name : '') : (el.type === 'checkbox' || el.type === 'radio') ? el.checked : (el.value || '').slice(0, 80),
    options: el.tagName === 'SELECT' ? [...el.options].map(o => o.text.trim()).slice(0, 25) : undefined,
  }));
  const text = document.body.innerText;
  return JSON.stringify({
    host: location.hostname,
    signInWall: /sign in|log in|create (an )?account|verification code/i.test(text.slice(0, 3000)) && fields.some(f => f.type === 'password'),
    hasCaptcha: !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], [class*="captcha"]'),
    submitButtons: [...document.querySelectorAll('button, input[type=submit]')].filter(vis).map(b => (b.innerText || b.value || '').trim()).filter(t => /submit|apply|send|next|continue|review/i.test(t)),
    fields,
  });
})()
