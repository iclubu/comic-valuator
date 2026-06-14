"""
Comic Valuator — Streamlit App
Upload your CLZ CovrPrice CSV export and look up real eBay sold prices
for any comic in your collection. Handles raw and graded (CGC/CBCS) books.
"""

import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ebay_client import search_sold_listings, compute_price_stats

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="Comic Valuator",
    page_icon="📚"
)
st.title("📚 Comic Valuator")
st.markdown("Real eBay sold prices for your CLZ collection · Powered by eBay Browse API")


# ─────────────────────────────────────────────
# LOAD & PARSE CSV
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_collection(file_bytes: bytes) -> pd.DataFrame:
    """Parse the CovrPrice-format CSV export from CLZ."""
    import io
    df = pd.read_csv(io.BytesIO(file_bytes), sep=';')

    # Clean series name — strip Vol. suffix and publisher tags
    def clean_series(s):
        if not isinstance(s, str):
            return s
        s = re.sub(r',?\s*[Vv]ol\.?\s*\d+', '', s)
        s = re.sub(r'\s*\([^)]+\)', '', s)
        return s.strip()

    df['series_clean'] = df['series_name'].apply(clean_series)

    # Issue number as clean string
    df['issue_str'] = df['issue_number'].apply(
        lambda x: str(int(x)) if pd.notna(x) and x == int(x) else str(x)
        if pd.notna(x) else ""
    )

    # Is graded?
    df['is_graded'] = df['location'].astype(str).str.startswith('GC') & \
                      df['grade_type'].isin(['CGC', 'CBCS'])

    # Display label
    df['label'] = df.apply(lambda r: (
        f"{r['series_clean']} #{r['issue_str']}"
        + (f" [{r['grade_type']} {r['grade']}]" if r['is_graded'] else " [Raw]")
    ), axis=1)

    return df


# ─────────────────────────────────────────────
# SIDEBAR — FILE UPLOAD + FILTERS
# ─────────────────────────────────────────────
st.sidebar.header("1. Upload Collection")
uploaded = st.sidebar.file_uploader(
    "CLZ CovrPrice Export (.csv)",
    type=["csv"],
    help="Export from CLZ Comics → CovrPrice format (semicolon-delimited)"
)

if not uploaded:
    st.info("⬆️ Upload your CLZ CovrPrice export CSV in the sidebar to begin.")
    st.markdown("""
    **How to export from CLZ:**
    1. Open CLZ Comics (web or desktop)
    2. Menu → Export → CovrPrice format
    3. Upload the `.csv` file here

    **What this app does:**
    - Looks up real eBay **sold** prices for each comic
    - Handles raw and graded (CGC/CBCS) books separately
    - Removes lot sales and outliers automatically
    - Shows low / median / high and price trend
    - Exports enriched CSV with value estimates
    """)
    st.stop()

# Load collection
df = load_collection(uploaded.read())

st.sidebar.header("2. Filter Collection")

# View mode
view_mode = st.sidebar.radio(
    "Show",
    ["All Comics", "Graded Only (GC boxes)", "Raw Only"],
    index=0
)

if view_mode == "Graded Only (GC boxes)":
    df_view = df[df['is_graded']].copy()
elif view_mode == "Raw Only":
    df_view = df[~df['is_graded']].copy()
else:
    df_view = df.copy()

# Publisher filter
publishers = ["All"] + sorted(df['series_name'].str.split(',').str[0].unique().tolist())
series_search = st.sidebar.text_input("Search series name", "")
if series_search:
    df_view = df_view[
        df_view['series_clean'].str.contains(series_search, case=False, na=False)
    ]

# GC box filter
gc_boxes = sorted(df[df['is_graded']]['location'].unique().tolist())
if gc_boxes and view_mode != "Raw Only":
    box_filter = st.sidebar.multiselect(
        "GC Box filter", gc_boxes,
        default=gc_boxes,
        help="Filter to specific graded comic boxes"
    )
    if view_mode == "Graded Only (GC boxes)":
        df_view = df_view[df_view['location'].isin(box_filter)]

st.sidebar.markdown("---")
st.sidebar.metric("Showing", f"{len(df_view):,} comics")
st.sidebar.metric("Total collection", f"{len(df):,} comics")
graded_count = len(df[df['is_graded']])
st.sidebar.metric("Graded (GC)", f"{graded_count:,}")


# ─────────────────────────────────────────────
# MAIN — TWO TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔍 Single Comic Lookup",
    "📊 Collection Overview",
    "⚡ Batch Valuator"
])


# ══════════════════════════════════════════════
# TAB 1 — SINGLE COMIC LOOKUP
# ══════════════════════════════════════════════
with tab1:
    st.subheader("Look Up a Single Comic")
    st.markdown("Select a comic from your collection and fetch its current eBay sold prices.")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        # Search / select comic
        search_term = st.text_input("Search your collection", placeholder="Batman, X-Men, Spawn...")

        filtered = df_view.copy()
        if search_term:
            filtered = filtered[
                filtered['series_clean'].str.contains(search_term, case=False, na=False)
            ]

        if filtered.empty:
            st.warning("No comics found. Try a different search term.")
            st.stop()

        selected_label = st.selectbox(
            "Select comic",
            filtered['label'].tolist(),
            help="Showing filtered results from your collection"
        )

        selected = filtered[filtered['label'] == selected_label].iloc[0]

        # Show comic details
        st.markdown("**Comic details:**")
        detail_data = {
            "Series":    selected['series_name'],
            "Issue":     selected['issue_str'],
            "Year":      selected.get('issue_year', ''),
            "Grade Type": selected.get('grade_type', 'RAW'),
            "Grade":     selected.get('grade', ''),
            "Location":  selected.get('location', ''),
            "Paid":      f"${selected['purchase_price']:.2f}" if pd.notna(selected.get('purchase_price')) and selected.get('purchase_price', 0) > 0 else "—",
            "Variant":   selected.get('variant_description', '') or "—",
        }
        for k, v in detail_data.items():
            if v and str(v) not in ('nan', ''):
                st.markdown(f"**{k}:** {v}")

        fetch_btn = st.button("🔍 Fetch eBay Sold Prices", type="primary", use_container_width=True)

    with col_right:
        if fetch_btn:
            with st.spinner(f"Searching eBay sold listings for {selected_label}…"):
                listings = search_sold_listings(
                    series     = selected['series_name'],  # use original — parser handles Vol.
                    issue      = selected['issue_str'],
                    grade_type = selected.get('grade_type') if selected['is_graded'] else None,
                    grade      = selected.get('grade') if selected['is_graded'] else None,
                    issue_year = int(selected['issue_year']) if pd.notna(selected.get('issue_year')) else None,
                    variant    = selected.get('variant_description'),
                    max_results= 50
                )

            if not listings:
                st.warning(
                    "No sold listings found. eBay may not have recent sales for this book, "
                    "or the search query didn't match. Try adjusting the series name."
                )
            else:
                stats = compute_price_stats(listings)

                # ── Stats row ──────────────────────────────────────
                s1, s2, s3, s4, s5 = st.columns(5)
                s1.metric("Sales Found", stats['count'])
                s2.metric("Low",    f"${stats['low']:.2f}"    if stats['low']    else "—")
                s3.metric("Median", f"${stats['median']:.2f}" if stats['median'] else "—")
                s4.metric("High",   f"${stats['high']:.2f}"   if stats['high']   else "—")
                s5.metric("Trend",  stats['trend'] or "—")

                # Paid vs median comparison
                paid = selected.get('purchase_price', 0)
                if pd.notna(paid) and paid > 0 and stats['median']:
                    diff     = stats['median'] - paid
                    diff_pct = (diff / paid) * 100
                    if diff > 0:
                        st.success(f"📈 Worth **${diff:.2f} more** than you paid "
                                   f"(+{diff_pct:.0f}% · bought at ${paid:.2f})")
                    else:
                        st.info(f"📉 Worth **${abs(diff):.2f} less** than you paid "
                                f"({diff_pct:.0f}% · bought at ${paid:.2f})")

                # ── Price distribution chart ───────────────────────
                prices = [l['price'] for l in listings]
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=prices, nbinsx=20,
                    marker_color="#00ff88", opacity=0.8,
                    name="Sold prices"
                ))
                if stats['median']:
                    fig.add_vline(
                        x=stats['median'], line_dash="dash",
                        line_color="#ff4444",
                        annotation_text=f"Median ${stats['median']:.2f}",
                        annotation_position="top right"
                    )
                fig.update_layout(
                    plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                    font=dict(color="white"),
                    xaxis_title="Sale Price (USD)",
                    yaxis_title="Number of Sales",
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=280,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Listings table ─────────────────────────────────
                st.markdown("**Recent sold listings:**")
                listings_df = pd.DataFrame(listings)[
                    ['date', 'price', 'condition', 'title', 'url']
                ].rename(columns={
                    'date': 'Date', 'price': 'Price ($)',
                    'condition': 'Condition', 'title': 'Title', 'url': 'Link'
                })
                listings_df['Price ($)'] = listings_df['Price ($)'].map("${:.2f}".format)
                listings_df['Link'] = listings_df['Link'].apply(
                    lambda u: f"[View]({u})" if u else ""
                )
                st.dataframe(
                    listings_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={"Link": st.column_config.LinkColumn("Link")}
                )

                # Search query used
                if listings:
                    st.caption(f"eBay query: `{listings[0]['query']}`")


# ══════════════════════════════════════════════
# TAB 2 — COLLECTION OVERVIEW
# ══════════════════════════════════════════════
with tab2:
    st.subheader("Collection Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Comics",    f"{len(df):,}")
    c2.metric("Graded (GC)",     f"{len(df[df['is_graded']]):,}")
    c3.metric("Raw",             f"{len(df[~df['is_graded']]):,}")
    c4.metric("With Purchase $", f"{len(df[df['purchase_price'].notna() & (df['purchase_price'] > 0)]):,}")

    col_a, col_b = st.columns(2)

    with col_a:
        # Grade distribution
        graded = df[df['is_graded']]
        if not graded.empty:
            grade_counts = graded['grade'].value_counts().sort_index(ascending=False)
            fig_grade = go.Figure(go.Bar(
                x=grade_counts.values,
                y=grade_counts.index.astype(str),
                orientation='h',
                marker_color="#00ff88",
            ))
            fig_grade.update_layout(
                title="Graded Comics by Grade",
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font=dict(color="white"),
                height=350, margin=dict(l=0, r=0, t=40, b=0),
                xaxis_title="Count",
            )
            st.plotly_chart(fig_grade, use_container_width=True)

    with col_b:
        # Grading company breakdown
        if not graded.empty:
            gt_counts = graded['grade_type'].value_counts()
            fig_gt = go.Figure(go.Pie(
                labels=gt_counts.index,
                values=gt_counts.values,
                marker=dict(colors=["#00ff88", "#00ccff", "#ffaa00"]),
                hole=0.4,
            ))
            fig_gt.update_layout(
                title="Grading Company",
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font=dict(color="white"),
                height=350, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig_gt, use_container_width=True)

    # GC box breakdown
    st.markdown("**Graded Comics by Box:**")
    if not graded.empty:
        box_counts = graded.groupby('location').agg(
            Count=('series_name', 'count'),
            CGC=('grade_type', lambda x: (x == 'CGC').sum()),
            CBCS=('grade_type', lambda x: (x == 'CBCS').sum()),
            At_9_8=('grade', lambda x: (x == 9.8).sum()),
        ).reset_index().rename(columns={'location': 'Box'})
        box_counts = box_counts.sort_values('Box')
        st.dataframe(box_counts, use_container_width=True, hide_index=True)

    # Purchase price distribution
    has_price = df[df['purchase_price'].notna() & (df['purchase_price'] > 0)]
    if not has_price.empty:
        st.markdown("**Purchase Price Distribution:**")
        fig_price = go.Figure(go.Histogram(
            x=has_price['purchase_price'],
            nbinsx=40,
            marker_color="#00ccff", opacity=0.8,
        ))
        fig_price.update_layout(
            plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
            font=dict(color="white"),
            xaxis_title="Purchase Price (USD)",
            yaxis_title="Count",
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_price, use_container_width=True)
        total_paid = has_price['purchase_price'].sum()
        st.caption(
            f"Total recorded spend: **${total_paid:,.2f}** "
            f"across {len(has_price):,} comics · "
            f"Average: **${has_price['purchase_price'].mean():.2f}**"
        )


# ══════════════════════════════════════════════
# TAB 3 — BATCH VALUATOR
# ══════════════════════════════════════════════
with tab3:
    st.subheader("Batch eBay Valuation")
    st.markdown(
        "Run eBay price lookups on a subset of your collection. "
        "Results are cached so you can stop and resume. "
        "For the full collection, use `batch_valuator.py` from the terminal."
    )

    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        batch_filter = st.radio(
            "Which comics to value",
            ["Graded Only (faster, higher value)", "All Comics (very slow — use batch script)"],
            index=0
        )
        max_batch = st.slider(
            "Max comics to look up this session",
            min_value=5, max_value=100, value=20,
            help="eBay allows ~5,000 calls/day. Each comic = 1 call."
        )

    with col_cfg2:
        st.markdown("**Estimated time:**")
        rate = 2  # seconds per lookup
        est_mins = (max_batch * rate) / 60
        st.metric("Est. time", f"{est_mins:.1f} min")
        st.metric("eBay calls", f"{max_batch}")
        st.info(
            "💡 Tip: Run graded comics first — they have the most "
            "price variance and highest value."
        )

    run_batch = st.button("🚀 Start Batch Valuation", type="primary")

    if run_batch:
        if batch_filter.startswith("Graded"):
            batch_df = df[df['is_graded']].head(max_batch).copy()
        else:
            batch_df = df_view.head(max_batch).copy()

        results = []
        progress = st.progress(0, text="Starting…")
        status   = st.empty()

        for i, (_, row) in enumerate(batch_df.iterrows()):
            pct  = int((i / len(batch_df)) * 100)
            label = f"{row['series_clean']} #{row['issue_str']}"
            progress.progress(pct / 100, text=f"Looking up {label}…")
            status.caption(f"Processing {i+1} of {len(batch_df)}: {label}")

            try:
                listings = search_sold_listings(
                    series     = row['series_clean'],
                    issue      = row['issue_str'],
                    grade_type = row.get('grade_type') if row['is_graded'] else None,
                    grade      = row.get('grade')      if row['is_graded'] else None,
                    max_results= 30
                )
                stats = compute_price_stats(listings)
            except Exception as e:
                stats = {"count": 0, "low": None, "high": None,
                         "median": None, "mean": None, "trend": None}

            results.append({
                "Series":       row['series_name'],
                "Issue":        row['issue_str'],
                "Grade Type":   row.get('grade_type', 'RAW'),
                "Grade":        row.get('grade', ''),
                "Location":     row.get('location', ''),
                "Paid ($)":     row.get('purchase_price', ''),
                "Sales Found":  stats['count'],
                "Low ($)":      stats['low'],
                "Median ($)":   stats['median'],
                "High ($)":     stats['high'],
                "Mean ($)":     stats['mean'],
                "Trend":        stats['trend'] or '',
                "Gain/Loss":    round(stats['median'] - row['purchase_price'], 2)
                                if stats['median'] and pd.notna(row.get('purchase_price'))
                                and row.get('purchase_price', 0) > 0 else None,
            })

            import time
            time.sleep(0.5)  # be gentle with the API

        progress.progress(1.0, text="Complete!")
        status.empty()

        results_df = pd.DataFrame(results)
        st.success(f"✅ Valued {len(results_df)} comics")

        # Summary stats
        valued = results_df[results_df['Median ($)'].notna()]
        if not valued.empty:
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Successfully Valued", len(valued))
            r2.metric("Est. Total (Median)", f"${valued['Median ($)'].sum():,.2f}")
            r3.metric("Highest Value",
                      f"${valued['Median ($)'].max():,.2f}")
            gains = valued[valued['Gain/Loss'].notna()]
            if not gains.empty:
                r4.metric("Total Gain/Loss",
                          f"${gains['Gain/Loss'].sum():,.2f}")

        # Show results table
        st.dataframe(
            results_df.sort_values("Median ($)", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        # Download button
        csv_out = results_df.to_csv(index=False)
        st.download_button(
            "⬇️ Download Results CSV",
            csv_out,
            "comic_valuations.csv",
            "text/csv",
        )