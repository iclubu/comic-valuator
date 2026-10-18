// Runs on eBay's Product Research page (your own logged-in browser).
// - Adds a "Send to inventory" button; clicking it sends what is on the page to your inventory tab.
// - If the page was opened by the inventory page's Fetch button (#ci in the URL, or window.name 'ci_fetch'),
//   it waits for the results to appear, sends them once, and closes the tab. It makes no requests of its own.
// For each sold listing it sends: the thumbnail photo URL, the listing link, and the row's text.
// Open DevTools > Console and look for "[Comic Bridge]" lines if anything misbehaves.
(function () {
  if (document.getElementById('ci-send')) return;
  const log = (...a) => console.log('[Comic Bridge]', ...a);
  const txt = (el) => (el && (el.innerText !== undefined ? el.innerText : el.textContent)) || '';
  const prices = (el) => (txt(el).match(/\$\s?\d/g) || []).length;
  const root = () => { const m = document.querySelector('main'), b = document.body; return (m && prices(m) >= prices(b)) ? m : b; };
  const MARK = /preview full size image/i;

  // Each sold listing contains a hidden "..., preview full size image" label. Listings are found by READING ORDER:
  // everything from one label up to the next label is that listing's text. That works whether or not each listing
  // has its own wrapper element (flat grids), and it also looks inside open shadow DOMs. If no label exists as
  // text, labels in image alt/aria-label/title attributes are used instead. Each photo and link is then attached
  // to the nearest label.
  const SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEMPLATE: 1 };
  const up = (n) => n.parentElement || (n.getRootNode && n.getRootNode().host) || null;   // crosses shadow boundaries
  const depth = (el) => { let d = 0; for (; el; el = up(el)) d++; return d; };
  const isAnc = (a, b) => { for (; b; b = up(b)) if (b === a) return true; return false; };
  const lcaDepth = (a, b) => {
    const chain = new Set();
    for (let x = a; x; x = up(x)) chain.add(x);
    for (let y = b; y; y = up(y)) if (chain.has(y)) return depth(y);
    return 0;
  };
  const bgUrl = (el) => { const m = /url\(["']?([^"')]+)["']?\)/.exec(el.getAttribute('style') || ''); return m ? m[1] : ''; };

  function extractRows() {
    let order = 0;
    const items = [];                      // everything in reading order: text lines and elements
    const visit = (node) => {
      for (let c = node.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) {
          const s = c.nodeValue.replace(/\s+/g, ' ').trim();
          if (s && c.parentElement && !SKIP[c.parentElement.tagName]) items.push({ t: s, el: c.parentElement, i: order++ });
        } else if (c.nodeType === 1 && !SKIP[c.tagName]) {
          items.push({ e: c, el: c, i: order++ });
          if (c.shadowRoot) visit(c.shadowRoot);
          visit(c);
          if (items.length > 60000) return;
        }
      }
    };
    visit(document.body);
    const attrMark = (el) => ['alt', 'aria-label', 'title'].map((k) => el.getAttribute(k) || '').find((v) => MARK.test(v)) || '';
    const rows = [];
    let cur = null;
    const hasTextMarks = items.some((x) => x.t && MARK.test(x.t));
    for (const x of items) {
      if (x.t) {
        if (hasTextMarks && MARK.test(x.t)) { cur = { el: x.el, i: x.i, lines: [], img: '', url: '' }; rows.push(cur); }
        if (cur && cur.lines.length < 40) cur.lines.push(x.t);
      } else if (!hasTextMarks && attrMark(x.e)) {
        cur = { el: x.e, i: x.i, lines: [attrMark(x.e)], img: '', url: '' }; rows.push(cur);
      }
      if (rows.length > 300) break;
    }
    if (!rows.length) return [];
    let grid = rows[0].el;                                   // the area holding all listings
    for (const r of rows) while (grid && !isAnc(grid, r.el)) grid = up(grid);
    if (!grid) return rows.map((r) => ({ img: '', url: '', text: r.lines.join('\n') }));
    if (rows.length === 1) {   // one listing: widen until the area holds a photo and a link, so they can be attached
      let g = rows[0].el;
      for (let k = 0; k < 8 && up(g) && up(g) !== document.body && !(g.querySelector && g.querySelector('img, [style*="background-image"]') && g.querySelector('a[href]')); k++) g = up(g);
      grid = g;
    }
    const gD = depth(grid);
    for (const x of items) {
      const el = x.e;
      if (!el || !(el.tagName === 'IMG' || el.tagName === 'A' || /background-image/.test(el.getAttribute('style') || '')) || !isAnc(grid, el)) continue;
      let best = -1, bestD = -1, bestBefore = false;
      rows.forEach((r, k) => {
        const d = lcaDepth(el, r.el), before = r.i < x.i;
        if (d > bestD || (d === bestD && before)) { bestD = d; best = k; bestBefore = before; }
      });
      const lonePhoto = rows.length === 1 && el.tagName !== 'A';   // single listing: a photo may sit before its label
      if (best < 0 || !(bestD > gD || bestBefore || lonePhoto)) continue;   // skip column headers etc. before the first listing
      const r = rows[best];
      if (el.tagName === 'A') {
        const h = el.href || '';
        if (!h || /^javascript:|#$/.test(h)) continue;
        if (!r.url || (!/\/itm\//.test(r.url) && /\/itm\//.test(h))) r.url = h;
      } else {
        const u = el.tagName === 'IMG' ? (el.currentSrc || el.src || el.getAttribute('data-src') || '') : bgUrl(el);
        if (u && (!r.img || (!/ebayimg/.test(r.img) && /ebayimg/.test(u)))) r.img = u;
      }
    }
    return rows.map((r) => ({ img: r.img, url: r.url, text: r.lines.join('\n') }));
  }

  const WHY = {
    'no-tab': 'Open the inventory page at http://localhost:8765 first',
    'inject-failed': 'Reload the inventory tab, then try again',
    'no-receiver': 'Reload the inventory tab, then try again'
  };
  const b = document.createElement('button');
  b.id = 'ci-send';
  b.textContent = 'Send to inventory';
  Object.assign(b.style, {
    position: 'fixed', right: '16px', bottom: '16px', zIndex: 2147483647, padding: '10px 14px',
    font: '14px sans-serif', background: '#0b63ce', color: '#fff', border: '0',
    borderRadius: '8px', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,.35)', maxWidth: '320px'
  });
  const reset = () => setTimeout(() => (b.textContent = 'Send to inventory'), 4000);
  function send(auto) {
    const r = root(), n = prices(r), text = txt(r).slice(0, 400000);
    let rows = [];
    try { rows = extractRows(); } catch (e) { log('row extraction failed', e && e.message); }
    log('sending', text.length, 'characters,', n, 'prices,', rows.length, 'listing rows,', rows.filter((x) => x.img).length, 'photos');
    if (!n) { b.textContent = 'No prices found on this page yet - wait for results to load'; reset(); return; }
    const kw = new URL(location.href).searchParams.get('keywords') || '';
    try {
      const v = (chrome.runtime.getManifest && chrome.runtime.getManifest().version) || '';
      chrome.runtime.sendMessage({ type: 'SEND', kw, text, rows, v }, (resp) => {
        if (chrome.runtime.lastError) { b.textContent = 'Extension was reloaded - refresh this eBay page'; reset(); return; }
        const ok = resp && resp.ok;
        log('result', JSON.stringify(resp));
        b.textContent = ok ? 'Sent \u2713 (' + (rows.length || n) + (rows.length ? ' sales' : ' prices') + ')' : (WHY[resp && resp.why] || 'Not delivered');
        if (ok && auto) setTimeout(() => window.close(), 800); else reset();
      });
    } catch (e) {
      b.textContent = 'Extension was reloaded - refresh this eBay page'; reset();
    }
  }
  b.onclick = () => send(false);
  document.body.appendChild(b);
  log('ready on', location.href);

  if (location.hash.indexOf('ci') >= 0 || window.name === 'ci_fetch') {  // eBay may drop the hash; window.name survives
    b.textContent = 'Waiting for results...';
    let last = -1, stable = 0, tries = 0;
    const iv = setInterval(() => {
      tries++;
      const n = prices(root());
      stable = (n > 1 && n === last) ? stable + 1 : 0;
      last = n;
      if (stable >= 2) { clearInterval(iv); send(true); }
      else if (tries >= 25) { clearInterval(iv); b.textContent = 'No results detected (' + n + ' prices) - sign in or check this page'; log('gave up waiting'); }
    }, 1000);
  }
})();
