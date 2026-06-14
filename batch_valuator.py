"""
batch_valuator.py
Bulk eBay price lookup for your entire CLZ comic collection.
Run from terminal — processes all comics overnight and outputs an
enriched CSV with value estimates.

Usage:
    python3 batch_valuator.py --input comic_export.csv
    python3 batch_valuator.py --input comic_export.csv --graded-only
    python3 batch_valuator.py --input comic_export.csv --resume
    python3 batch_valuator.py --input comic_export.csv --limit 500

Options:
    --input        Path to CLZ CovrPrice CSV export (required)
    --graded-only  Only process GC box / graded comics (faster)
    --resume       Resume from last checkpoint if previous run was interrupted
    --limit N      Stop after N comics (useful for testing)
    --delay N      Seconds between eBay calls (default: 1.0)
    --min-score N  Only process comics where purchase_price >= N (default: 0)
"""

import os
import sys
import csv
import time
import json
import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from ebay_client import search_sold_listings, compute_price_stats

load_dotenv()

CHECKPOINT_FILE = "batch_checkpoint.json"
OUTPUT_FILE     = "comic_valuations_{date}.csv"

OUTPUT_COLUMNS = [
    "series_name", "issue_number", "issue_str", "grade_type", "grade",
    "location", "purchase_price", "covrprice_id",
    "ebay_sales_found", "ebay_low", "ebay_median", "ebay_high",
    "ebay_mean", "ebay_trend", "gain_loss", "gain_loss_pct",
    "valuation_date", "ebay_query",
]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def clean_series(s: str) -> str:
    if not isinstance(s, str):
        return str(s)
    s = re.sub(r',?\s*[Vv]ol\.?\s*\d+', '', s)
    s = re.sub(r'\s*\([^)]+\)', '', s)
    return s.strip()


def issue_to_str(x) -> str:
    try:
        f = float(x)
        return str(int(f)) if f == int(f) else str(f)
    except (TypeError, ValueError):
        return str(x) if x else ""


def load_collection(path: str, graded_only: bool) -> pd.DataFrame:
    print(f"Loading collection from {path}...")

    # Try semicolon delimiter first (CovrPrice format)
    try:
        df = pd.read_csv(path, sep=';')
        if len(df.columns) < 3:
            raise ValueError("Too few columns with semicolon — trying comma")
    except Exception:
        df = pd.read_csv(path)

    print(f"  Loaded {len(df):,} comics")

    # Add derived columns
    df['series_clean'] = df['series_name'].apply(clean_series)
    df['issue_str']    = df['issue_number'].apply(issue_to_str)
    df['is_graded']    = (
        df['location'].astype(str).str.startswith('GC') &
        df['grade_type'].isin(['CGC', 'CBCS'])
    )

    if graded_only:
        df = df[df['is_graded']].copy()
        print(f"  Filtered to {len(df):,} graded comics")

    return df.reset_index(drop=True)


def load_checkpoint() -> set:
    """Return set of already-processed covrprice_ids."""
    if not Path(CHECKPOINT_FILE).exists():
        return set()
    with open(CHECKPOINT_FILE) as f:
        data = json.load(f)
    done = set(data.get("completed", []))
    print(f"  Resuming — {len(done):,} comics already processed")
    return done


def save_checkpoint(completed_ids: set):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"completed": list(completed_ids), "updated": datetime.now().isoformat()}, f)


def print_progress(i: int, total: int, series: str, issue: str,
                   stats: dict, start_time: float):
    elapsed   = time.time() - start_time
    per_comic = elapsed / max(i, 1)
    remaining = (total - i) * per_comic
    pct       = (i / total) * 100

    median_str = f"${stats['median']:.2f}" if stats.get('median') else "no data"
    trend_str  = stats.get('trend') or ""
    eta_str    = f"{int(remaining // 60)}m {int(remaining % 60)}s"

    print(
        f"  [{i:>4}/{total}] {pct:>5.1f}% | "
        f"{series[:30]:<30} #{issue:<6} | "
        f"Median: {median_str:<10} {trend_str:<12} | "
        f"ETA: {eta_str}"
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bulk comic valuation from eBay sold data")
    parser.add_argument("--input",       required=True, help="CLZ CovrPrice CSV export path")
    parser.add_argument("--graded-only", action="store_true", help="Only process graded comics")
    parser.add_argument("--resume",      action="store_true", help="Resume from checkpoint")
    parser.add_argument("--limit",       type=int, default=0, help="Max comics to process")
    parser.add_argument("--delay",       type=float, default=1.0, help="Seconds between API calls")
    parser.add_argument("--min-price",   type=float, default=0, help="Only process if purchase_price >= N")
    args = parser.parse_args()

    # Load collection
    df = load_collection(args.input, args.graded_only)

    # Filter by min purchase price
    if args.min_price > 0:
        has_price = df['purchase_price'].notna() & (df['purchase_price'] >= args.min_price)
        df = df[has_price].copy()
        print(f"  Filtered to {len(df):,} comics with purchase price >= ${args.min_price:.2f}")

    # Apply limit
    if args.limit > 0:
        df = df.head(args.limit)
        print(f"  Limited to first {args.limit} comics")

    # Load checkpoint for resume
    completed_ids = load_checkpoint() if args.resume else set()

    # Output file
    date_str    = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_FILE.format(date=date_str)

    # Open output CSV for streaming writes
    # This way if the script is interrupted results are not lost
    output_file = open(output_path, "w", newline="", encoding="utf-8")
    writer      = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
    writer.writeheader()

    total      = len(df)
    processed  = 0
    valued     = 0
    no_data    = 0
    errors     = 0
    start_time = time.time()
    today      = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*70}")
    print(f"  COMIC VALUATOR — Batch Run")
    print(f"  Comics to process : {total:,}")
    print(f"  Delay between calls: {args.delay}s")
    print(f"  Output file        : {output_path}")
    print(f"{'='*70}\n")

    for _, row in df.iterrows():

        # Resume — skip already done
        comic_id = str(row.get('covrprice_id', f"{row['series_clean']}_{row['issue_str']}"))
        if comic_id in completed_ids:
            continue

        processed += 1

        try:
            listings = search_sold_listings(
                series     = row['series_clean'],
                issue      = row['issue_str'],
                grade_type = row.get('grade_type') if row['is_graded'] else None,
                grade      = row.get('grade')      if row['is_graded'] else None,
                max_results= 40,
            )
            stats = compute_price_stats(listings)
            query = listings[0]['query'] if listings else ""

        except Exception as e:
            print(f"  ⚠️  Error on {row['series_clean']} #{row['issue_str']}: {e}")
            stats = {"count": 0, "low": None, "high": None,
                     "median": None, "mean": None, "trend": None}
            query = ""
            errors += 1

        # Compute gain/loss
        paid      = row.get('purchase_price')
        gain      = None
        gain_pct  = None
        if stats.get('median') and pd.notna(paid) and paid > 0:
            gain     = round(stats['median'] - paid, 2)
            gain_pct = round((gain / paid) * 100, 1)

        if stats['count'] > 0:
            valued += 1
        else:
            no_data += 1

        # Write row
        writer.writerow({
            "series_name":     row['series_name'],
            "issue_number":    row['issue_number'],
            "issue_str":       row['issue_str'],
            "grade_type":      row.get('grade_type', ''),
            "grade":           row.get('grade', ''),
            "location":        row.get('location', ''),
            "purchase_price":  row.get('purchase_price', ''),
            "covrprice_id":    row.get('covrprice_id', ''),
            "ebay_sales_found":stats['count'],
            "ebay_low":        stats['low']    or '',
            "ebay_median":     stats['median'] or '',
            "ebay_high":       stats['high']   or '',
            "ebay_mean":       stats['mean']   or '',
            "ebay_trend":      stats['trend']  or '',
            "gain_loss":       gain      if gain      is not None else '',
            "gain_loss_pct":   gain_pct  if gain_pct  is not None else '',
            "valuation_date":  today,
            "ebay_query":      query,
        })
        output_file.flush()  # Write immediately — safe against interruption

        # Progress
        print_progress(processed, total, row['series_clean'],
                       row['issue_str'], stats, start_time)

        # Save checkpoint every 25 comics
        completed_ids.add(comic_id)
        if processed % 25 == 0:
            save_checkpoint(completed_ids)

        # Respect rate limit
        time.sleep(args.delay)

    output_file.close()
    save_checkpoint(completed_ids)

    # ── Final summary ──────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"  ✅ BATCH COMPLETE")
    print(f"  Processed  : {processed:,} comics in {elapsed/60:.1f} min")
    print(f"  Valued     : {valued:,} (eBay data found)")
    print(f"  No data    : {no_data:,} (no recent eBay sales)")
    print(f"  Errors     : {errors:,}")
    print(f"  Output     : {output_path}")

    # Load results for summary stats
    try:
        results = pd.read_csv(output_path)
        with_median = results[results['ebay_median'].notna() & (results['ebay_median'] > 0)]
        if not with_median.empty:
            print(f"\n  📊 COLLECTION VALUE ESTIMATE")
            print(f"  Comics valued            : {len(with_median):,}")
            print(f"  Est. total (median)      : ${with_median['ebay_median'].sum():,.2f}")
            print(f"  Highest value comic      : ${with_median['ebay_median'].max():,.2f}")
            print(f"       → {with_median.loc[with_median['ebay_median'].idxmax(), 'series_name']} "
                  f"#{with_median.loc[with_median['ebay_median'].idxmax(), 'issue_str']}")

            gains = with_median[with_median['gain_loss'].notna()]
            if not gains.empty:
                total_paid  = gains['purchase_price'].sum()
                total_value = gains['ebay_median'].sum()
                total_gain  = gains['gain_loss'].sum()
                print(f"\n  💰 RETURN ON INVESTMENT")
                print(f"  Total paid               : ${total_paid:,.2f}")
                print(f"  Total current value      : ${total_value:,.2f}")
                print(f"  Total gain/loss          : ${total_gain:,.2f} "
                      f"({(total_gain/total_paid*100):.1f}%)")
    except Exception:
        pass

    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()