# 📚 Comic Valuator

A real-time eBay market valuation tool for your CLZ comic collection.
Pulls actual **sold** listing prices from eBay — not asking prices, not
guide values — so you know what your books are genuinely worth today.

Built specifically around a CLZ CovrPrice CSV export with full support
for raw and graded (CGC/CBCS) comics stored in GC boxes.

---

## 🗂 Project Structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit visual explorer — single lookup, overview, batch UI |
| `ebay_client.py` | eBay Browse API client — OAuth, search, price stats |
| `batch_valuator.py` | Terminal batch processor for the full collection |
| `requirements.txt` | Python dependencies |
| `start.sh` | Launch script for the Streamlit app |
| `.env` | Your eBay API credentials (never commit this to git) |

---

## 🛠 Setup

### 1. Prerequisites
- Python 3.10+ (you have 3.14.5 ✅)
- eBay Developer account — developer.ebay.com
- CLZ Comics app with CovrPrice export

### 2. eBay API Credentials
1. Go to [developer.ebay.com](https://developer.ebay.com)
2. Sign in → **My Account → Application Access Keys**
3. Click the **Production** tab (not Sandbox)
4. Copy your **App ID (Client ID)** and **Cert ID (Client Secret)**

### 3. Environment Setup
```bash
cd /Users/Projects/Comic-Valuator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Add Your eBay Keys
Edit your `.env` file:
```
EBAY_CLIENT_ID=YourAppName-PRD-xxxxxxxxxxxxxxxxx
EBAY_CLIENT_SECRET=PRD-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Shell Alias (already set up)
```bash
alias comics='cd /Users/Projects/Comic-Valuator && source venv/bin/activate && python3 -m streamlit run app.py'
```
Make it permanent:
```bash
echo 'alias comics="cd /Users/Projects/Comic-Valuator && source venv/bin/activate && python3 -m streamlit run app.py"' >> ~/.zshrc
source ~/.zshrc
```

### 6. Launch
```bash
comics
```
Opens at **http://localhost:8502**

---

## 📤 Exporting from CLZ

1. Open CLZ Comics (web or desktop app)
2. Go to **Menu → Export**
3. Choose **CovrPrice format** (semicolon-delimited `.csv`)
4. Save the file and upload it in the app sidebar

The CovrPrice export includes grade, grade_type, purchase_price,
location (GC box), covrprice_id and series metadata — all required
for accurate eBay queries.

---

## 🖥 Streamlit App — Three Tabs

### Tab 1 — Single Comic Lookup
Search your collection by series name, select a specific issue, and
fetch its current eBay sold prices in real time.

**What you see:**
- Sales count, Low / Median / High / Mean price
- Price trend arrow (↑ rising / ↓ falling / → stable) based on
  last 30 days vs 60-90 days of sold data
- Gain/loss vs what you paid (if purchase price is recorded in CLZ)
- Price distribution histogram
- Full table of recent sold listings with direct eBay links

**How queries work:**
- **Graded comics** (GC boxes, CGC/CBCS): searches `"Series" #Issue CGC 9.8`
- **Raw comics**: searches `"Series" #Issue comic`
- Vol. suffixes and publisher tags are automatically stripped from
  series names for cleaner results
- Lot sales, digital items and wrong-grade slabs are filtered out

---

### Tab 2 — Collection Overview
Visual dashboard of your entire collection:

- Total comics / graded / raw counts
- Grade distribution chart (how many 9.8s, 9.6s, etc.)
- CGC vs CBCS breakdown pie chart
- GC box summary table (Count, CGC, CBCS, 9.8s per box)
- Purchase price distribution histogram
- Total recorded spend and average price paid

---

### Tab 3 — Batch Valuator (In-App)
Run up to 100 eBay lookups in the browser with a live progress bar.
Results download as a CSV when complete.

**Best for:** spot-checking your graded books or a specific series.
**For the full collection:** use the terminal batch script instead.

---

## ⚡ Batch Script — Full Collection

The batch script runs from your terminal, processes the entire collection
overnight, and streams results to a CSV as it goes — so nothing is lost
if it's interrupted.

### Basic Usage
```bash
source venv/bin/activate

# Test run — first 20 comics
python3 batch_valuator.py --input comic_2026-06-13_16-29-07-export.csv --limit 20

# Graded only — 593 comics, ~15 minutes
python3 batch_valuator.py --input comic_2026-06-13_16-29-07-export.csv --graded-only

# Full collection — run overnight
python3 batch_valuator.py --input comic_2026-06-13_16-29-07-export.csv --delay 1.5

# Resume after interruption
python3 batch_valuator.py --input comic_2026-06-13_16-29-07-export.csv --resume

# Only comics you paid $20+ for
python3 batch_valuator.py --input comic_2026-06-13_16-29-07-export.csv --min-price 20
```

### All Options
| Flag | Default | Description |
|---|---|---|
| `--input` | required | Path to CLZ CovrPrice CSV export |
| `--graded-only` | off | Only process GC box / graded comics |
| `--resume` | off | Resume from last checkpoint |
| `--limit N` | 0 (all) | Stop after N comics |
| `--delay N` | 1.0 | Seconds between eBay API calls |
| `--min-price N` | 0 | Only process if purchase_price >= N |

### Output
Creates `comic_valuations_YYYYMMDD_HHMMSS.csv` with these columns:

| Column | Description |
|---|---|
| `series_name` | Original series name from CLZ |
| `issue_str` | Cleaned issue number |
| `grade_type` | CGC / CBCS / blank for raw |
| `grade` | Numeric grade (9.8, 9.6, etc.) |
| `location` | GC box or storage location |
| `purchase_price` | What you paid (from CLZ) |
| `ebay_sales_found` | Number of sold listings found |
| `ebay_low` | Lowest sold price (IQR filtered) |
| `ebay_median` | Median sold price — best value estimate |
| `ebay_high` | Highest sold price |
| `ebay_mean` | Average sold price |
| `ebay_trend` | ↑/↓/→ based on recent vs older sales |
| `gain_loss` | Median minus purchase price |
| `gain_loss_pct` | Gain/loss as percentage |
| `valuation_date` | Date the lookup was run |
| `ebay_query` | Exact eBay search query used |

### Final Summary
At the end of every batch run the script prints:
```
======================================================================
  ✅ BATCH COMPLETE
  Processed  : 593 comics in 12.4 min
  Valued     : 481 (eBay data found)
  No data    : 112 (no recent eBay sales)
  Errors     : 0

  📊 COLLECTION VALUE ESTIMATE
  Comics valued            : 481
  Est. total (median)      : $47,320.00
  Highest value comic      : $2,400.00
       → Amazing Spider-Man #300 CGC 9.8

  💰 RETURN ON INVESTMENT
  Total paid               : $18,450.00
  Total current value      : $47,320.00
  Total gain/loss          : $28,870.00 (156.5%)
======================================================================
```

### Checkpoint / Resume
The script saves a `batch_checkpoint.json` every 25 comics. If it's
interrupted (power, sleep, network) just add `--resume` to pick up
exactly where it stopped — already-processed comics are skipped.

---

## 💡 Tips for Best Results

**Graded comics first**
Run `--graded-only` before the full collection. Graded books have
the most standardised eBay titles so the search queries are very
accurate. Raw books vary more.

**eBay rate limits**
eBay allows approximately 5,000 Browse API calls per day on a
standard developer account. Your full collection of 10,771 comics
would need 2+ days at 5,000/day. Run with `--graded-only` first,
then do raw books in batches using `--limit` and `--resume`.

**No recent sales**
Some older or lower-demand books won't have eBay sales in the last
90 days. The script marks these as `ebay_sales_found: 0` — they're
not errors, just genuinely thinly traded books. CovrPrice guide
values remain your best reference for those.

**Lot sales filtered**
The eBay client automatically excludes lot sales, bundle listings,
and digital items from the price calculations.

**Price variance**
Outliers are removed using the IQR method before computing stats —
so a single $5,000 sale of a 9.9 won't skew the median for your 9.8.

---

## 🔄 Recommended Workflow

```
Monthly valuation run:
1. Export fresh CSV from CLZ (CovrPrice format)
2. Run: python3 batch_valuator.py --input <new_export.csv> --graded-only
3. Review output CSV — sort by gain_loss_pct to see biggest movers
4. For specific books: use the Streamlit app (comics alias) for
   deep-dive with full listing history and price chart
5. Update CLZ with any books you decide to sell or upgrade
```

---

## 🚫 What This Tool Does Not Do

- **CGC census population** — how many copies exist at each grade.
  GoCollect and GPAnalysis have this; a future version could add it.
- **Key issue detection** — use Key Collector for first appearances,
  deaths, and origin stories. Those command premiums the raw eBay
  median won't fully reflect.
- **Price history beyond 90 days** — eBay's API only returns the
  last 90 days of sold data. For longer history use GoCollect ($9/mo)
  or GPAnalysis (paid).
- **Automatic CLZ sync** — the output is a separate CSV; you'd need
  to manually import value estimates back into CLZ.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `pandas` | CSV parsing and data manipulation |
| `requests` | eBay API HTTP calls |
| `python-dotenv` | Load .env credentials |
| `plotly` | Price charts and visualisations |
| `numpy` | IQR outlier removal and statistics |

Install all:
```bash
pip install -r requirements.txt
```
