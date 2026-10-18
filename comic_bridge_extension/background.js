// Relays the message from the eBay tab to your inventory tab, then switches to it.
// If the inventory tab was opened before the extension was loaded, it has no receiver yet:
// we inject one and retry once.
function deliver(t, m, done, retried) {
  chrome.tabs.sendMessage(t.id, { type: 'EBAY_DATA', kw: m.kw, text: m.text, rows: m.rows, v: m.v }, (resp) => {
    const err = chrome.runtime.lastError;
    if (!err && resp && resp.ok) {
      chrome.tabs.update(t.id, { active: true });
      chrome.windows.update(t.windowId, { focused: true });
      done({ ok: true });
    } else if (!retried) {
      chrome.scripting.executeScript({ target: { tabId: t.id }, files: ['inventory.js'] }, () => {
        if (chrome.runtime.lastError) { done({ ok: false, why: 'inject-failed' }); return; }
        deliver(t, m, done, true);
      });
    } else {
      done({ ok: false, why: 'no-receiver' });
    }
  });
}
chrome.runtime.onMessage.addListener((m, sender, sendResponse) => {
  if (m.type !== 'SEND') return;
  chrome.tabs.query({ url: ['http://localhost:8765/*', 'http://127.0.0.1:8765/*'] }, (tabs) => {
    if (!tabs || !tabs.length) { sendResponse({ ok: false, why: 'no-tab' }); return; }
    deliver(tabs[0], m, sendResponse, false);
  });
  return true; // keep the channel open for the async response
});
