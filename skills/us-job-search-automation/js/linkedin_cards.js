// LinkedIn search results (/jobs/search-results/): parse the visible cards from the page text.
// Run with javascript_tool on the results page. Returns a JSON string:
// [{title, company, location, workType, pay, applied, viewed, easyApply}]
// Cards carry no job ids in the DOM; to get an id, click the card and run linkedin_current_id.js.
// Feed the result to vet.py --mode card before opening anything.
(() => {
  const main = document.querySelector('main') || document.body;
  const lines = main.innerText.split('\n').map(s => s.trim()).filter(Boolean);
  const locRe = /\((Remote|Hybrid|On-site)\)$|United States$|, [A-Z]{2}( \d{5})?$|Metropolitan Area$/;
  const cards = [];
  for (let i = 2; i < lines.length; i++) {
    if (!locRe.test(lines[i])) continue;
    // title is usually duplicated (accessible name + visible text) right above the company line
    let company = lines[i - 1], title = lines[i - 2];
    if (/\(Verified job\)$/.test(title)) title = title.replace(/\s*\(Verified job\)$/, '');
    if (title === company || !title || title.length > 140) continue;
    const tail = lines.slice(i + 1, i + 7);
    const stop = tail.findIndex(l => l === 'Easy Apply' || /^Applied$/.test(l));
    const block = stop >= 0 ? tail.slice(0, stop + 1) : tail;
    const wt = (lines[i].match(/\((Remote|Hybrid|On-site)\)/) || [])[1] || '';
    cards.push({
      title, company, location: lines[i], workType: wt,
      pay: (block.find(l => /^\$/.test(l)) || ''),
      applied: block.includes('Applied'), viewed: block.includes('Viewed'),
      easyApply: block.includes('Easy Apply'),
    });
  }
  const seen = new Set();
  return JSON.stringify(cards.filter(c => { const k = c.title + '|' + c.company + '|' + c.location; if (seen.has(k)) return false; seen.add(k); return true; }));
})()
