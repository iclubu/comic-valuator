// Runs on your local inventory page (http://localhost:8765). Relays data from the extension to the page.
(function () {
  const hello = () => window.postMessage({ type: 'CI_EXT_READY' }, '*');
  window.addEventListener('message', (e) => {
    if (e.source === window && e.data && e.data.type === 'CI_PING') hello();
  });
  chrome.runtime.onMessage.addListener((m, sender, sendResponse) => {
    if (m.type === 'EBAY_DATA') {
      window.postMessage({ type: 'EBAY_DATA', kw: m.kw, text: m.text, rows: m.rows, v: m.v }, '*');
      sendResponse({ ok: true });
    }
  });
  hello();
})();
