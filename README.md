# Comic Valuator

A local inventory viewer for a [CLZ](https://clz.com)-style comic collection export that helps you value each book
from **eBay sold data**, with photos, without leaving your own browser.

Pick a comic, click **Fetch from eBay**, and the sold listings from eBay's Product Research page arrive in the
bottom panel with their photos. Untick the wrong covers, lots and grades, and save the median as that book's value.

> Everything runs on your computer. Nothing is uploaded anywhere, and no eBay login or API key is used or stored.


<img width="2352" height="1067" alt="Screenshot 2026-10-17 at 7 32 06 PM" src="https://github.com/user-attachments/assets/375b7361-ead8-4dd9-908f-fc0708d6eb7c" />
Pulled from Ebay sold listing
<img width="2342" height="1044" alt="Screenshot 2026-10-17 at 7 32 27 PM" src="https://github.com/user-attachments/assets/b8a14db6-d082-4779-b47e-e4c629e89e22" />


## What you get

- **Inventory list** built from your XML export: search by series, issue, variant, box or signer.
- **Duplicates as a tree**: a book you own several times shows `x3`; expand it to see each copy and its box.
- **Filters**: raw books by default; turn on **CGC**, **CBCS** (or other graders) to include graded books; **Signed** to
  show books with a signer.
- **Sortable Box column** (numeric boxes first, then text names like `A7`, then books with no box).
- **eBay sold data with photos**, per-sale links, and an automatic first pass that unticks likely lots/sets, other
  issue numbers and wrong grades.
- **Median / average / low / high** over the ticked sales, a running total, and **Export CSV** of every saved value.

## How it works (and what it deliberately does not do)

eBay shows a human-verification page to scripts, and its official API does not return sold prices. So this project
does **not** scrape eBay. Instead:

1. `build_inventory_page.py` turns your XML into one self-contained `comic_inventory.html`.
2. You serve it locally and open it in Chrome.
3. **Fetch from eBay** opens eBay's *Product Research* page (Seller Hub → Research) in a new tab, in your own
   signed-in browser, for that comic.
4. A small Chrome extension (`comic_bridge_extension/`) reads the page *you are looking at* and sends it to the
   inventory tab. It makes no requests of its own and never touches your login.

You are responsible for using eBay in line with its terms. This project is not affiliated with or endorsed by eBay or CLZ.

## Quick start

Requirements: Python 3, Google Chrome, and an eBay account that can open **Seller Hub → Research → Product research**.

```bash
# 1. Build the page from your export (uses the newest .xml in this folder, or pass a path)
python3 build_inventory_page.py                    # or: python3 build_inventory_page.py my_export.xml

# 2. Serve it locally (leave this running)
python3 -m http.server 8765
```

Then open <http://localhost:8765/comic_inventory.html>.

**Try it first with the fictional sample data:** `python3 build_inventory_page.py sample/sample_export.xml`

### Load the Chrome extension (once)

1. Open `chrome://extensions` and switch on **Developer mode** (top right).
2. Click **Load unpacked** and choose the `comic_bridge_extension` folder (the one that directly contains `manifest.json`).
3. Hard-refresh the inventory page (Cmd/Ctrl+Shift+R). The top bar should show a green **Extension: connected**.
4. After updating the extension files, click the reload arrow (⟳) on its card in `chrome://extensions`.

The page must be opened at `localhost:8765` or `127.0.0.1:8765`, not as a `file://` path.

## Using it

1. Click a comic. Its cover, boxes and any signers appear.
2. Click **Fetch from eBay (90d)** (or **1y**). Sign in to eBay if asked. The tab reads itself, closes, and the results
   appear at the bottom with a status line such as
   `Received 49 sales ... | extension v1.6 read 49 listing rows, 49 photos`.
3. Untick anything that is the wrong cover, grade or a lot (the page unticks likely ones for you, labelled in red).
4. Click **Save median $X**. Repeat. **Export CSV** downloads every saved value.

No extension? Use **Research 90d (manual)**, press Cmd/Ctrl+A then Cmd/Ctrl+C on eBay's results, and paste into the
box at the bottom. Photos need the extension.

## How the value is calculated

The saved value is the **median** of the ticked sales (the average, low and high are shown too). The line total in
the CSV is median × quantity. Copies of the same book (same series, issue, variant and grade) share one value.
Rows are unticked automatically when the title looks like a lot/set or range (`#1-6`), has a different issue number,
or has the wrong grading status for the book you selected. Tick them back if they are right.

## Status line cheat sheet

| Status says | Meaning |
|---|---|
| `extension v1.6 read 49 listing rows, 49 photos` | Working. |
| `extension (version unknown, older than 1.6)` | An old extension copy is still running. Reload it in `chrome://extensions`. |
| `extension v1.6 read 0 listing rows` | The extension is current but could not find eBay's listing labels. eBay may have changed its page. |
| Red **Extension: not detected** | The extension is not loaded, or the page is not open at `localhost:8765`. Click the badge for setup steps. |

## Privacy

- The generated `comic_inventory.html` **contains your whole inventory** (titles, boxes, signers, cover links). It and
  your XML/CSV files are listed in `.gitignore` so they are not committed by accident. Do not publish them.
- Saved values live in your browser's `localStorage` for `localhost:8765`. Use **Export CSV** to keep a copy.
- The extension only runs on `https://www.ebay.com/sh/research*` and your local `localhost:8765` / `127.0.0.1:8765` page.

## Project layout

```
build_inventory_page.py      builds comic_inventory.html from the XML
comic_bridge_extension/      Chrome extension (Manifest V3): reads the eBay page you open, relays it to the inventory tab
sample/sample_export.xml     fictional collection for trying the project
```

Notes for tinkering: the eBay category used for Research links is `CAT=259104` (Comics & Graphic Novels) in
`build_inventory_page.py`. Fields read from the XML: series, issue number, edition/variant, grade, grading company,
slabbed flag, key-issue flag and reason, quantity, storage location, signers and cover URL.

## Limitations

- Depends on eBay's Product Research page structure. If eBay redesigns it, the reader may need updating.
- Sold data covers whatever date range you choose in Research; thinly traded books may have few sales.
- Chrome only.
