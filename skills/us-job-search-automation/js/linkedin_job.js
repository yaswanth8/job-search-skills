// LinkedIn: two jobs in one snippet.
// On a search page after clicking a card: returns the selected job's id (currentJobId).
// On /jobs/view/<id>/: returns {id, header, description} with the description trimmed,
// so the huge footer and "More jobs" list never reach the transcript.
(() => {
  const params = new URLSearchParams(location.search);
  const fromPath = (location.pathname.match(/\/jobs\/view\/(?:[^/]*-)?(\d+)/) || [])[1];
  const id = fromPath || params.get('currentJobId');
  if (!fromPath) return JSON.stringify({ id });
  const main = document.querySelector('main') || document.body;
  const text = main.innerText.replace(/\n{2,}/g, '\n');
  const start = text.indexOf('About the job');
  const endMarkers = ['Benefits found in job post', 'Set alert for similar jobs', 'See how you compare', 'About the company', 'More jobs'];
  let end = text.length;
  for (const m of endMarkers) { const k = text.indexOf(m, start + 1); if (k > 0 && k < end) end = k; }
  return JSON.stringify({
    id,
    header: text.slice(0, Math.max(0, start)).slice(0, 600),
    easyApply: !!document.querySelector('button[aria-label*="Easy Apply"]') || /Easy Apply/.test(text.slice(0, 600)),
    applied: /Application submitted|Applied \d|\bApplied\b/.test(text.slice(0, 900)),
    description: (start >= 0 ? text.slice(start + 13, end) : text).trim().slice(0, 6000),
  });
})()
