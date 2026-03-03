"""
TX Primary Election Results — Streamlit Dashboard

Launch: streamlit run app.py
"""

import time
import io
import os
from datetime import datetime
import streamlit as st
import pandas as pd
from scraper import TXResultsScraper, KNOWN_ELECTIONS, DEFAULT_ELECTIONS


st.set_page_config(page_title="TX Primary Results", page_icon="\U0001f5f3\ufe0f", layout="wide")

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
PARTY_COLORS = {"Republican": "#cc0000", "Democratic": "#0057b8"}

st.markdown("""
<style>
    /* Tighter tables */
    .stDataFrame td, .stDataFrame th { padding: 4px 8px !important; font-size: 14px; }
    /* Metric labels */
    [data-testid="stMetricLabel"] { font-size: 13px; }
    /* Progress text */
    .stProgress > div > div { height: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def short_race_name(name):
    """Shorten verbose race names for display."""
    name = name.strip()
    if name.startswith("U. S. SENATOR"):
        return "US Senate"
    if name.startswith("U. S. REPRESENTATIVE DISTRICT"):
        dist = name.replace("U. S. REPRESENTATIVE DISTRICT", "").strip()
        return f"US House TX-{dist}"
    if name.startswith("STATE SENATOR"):
        dist = name.replace("STATE SENATOR, DISTRICT", "").strip()
        return f"State Senate {dist}"
    return name


def fmt_pct(val):
    """Format percentage for display: 28.9% not 28.900000"""
    if pd.isna(val) or val == 0:
        return "0%"
    if val == round(val):
        return f"{val:.0f}%"
    return f"{val:.1f}%"


def fmt_votes(val):
    """Format vote count with commas."""
    return f"{int(val):,}"


def filter_df(df, party_filter, race_type):
    if df.empty:
        return df
    out = df.copy()
    if party_filter != "Both":
        out = out[out["party"] == party_filter]
    if race_type == "US Senate":
        out = out[out["race_name"].str.startswith("U. S. SENATOR")]
    elif race_type == "US House":
        out = out[out["race_name"].str.startswith("U. S. REPRESENTATIVE")]
    return out


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(dfs_dict):
    """Write multiple DataFrames to an Excel file with named sheets."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for sheet_name, df in dfs_dict.items():
            if not df.empty:
                df.to_excel(w, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def party_color(name):
    return PARTY_COLORS.get(name, "#666666")


def run_live_export():
    """Run the live CSV export (same logic as export.py --live)."""
    scraper = TXResultsScraper()
    results = scraper.get_all_results()
    county = results["county"]
    if county.empty:
        return False, "No data returned"
    os.makedirs("data", exist_ok=True)
    county.to_csv("data/tx_primary_LIVE.csv", index=False)
    senate = county[county["race_name"].str.startswith("U. S. SENATOR")]
    if not senate.empty:
        senate.to_csv("data/tx_senate_LIVE.csv", index=False)
    house = county[county["race_name"].str.startswith("U. S. REPRESENTATIVE")]
    if not house.empty:
        house.to_csv("data/tx_house_LIVE.csv", index=False)
    statewide = results["statewide"]
    if not statewide.empty:
        statewide.to_csv("data/tx_statewide_LIVE.csv", index=False)
    return True, f"Exported {len(county):,} rows to data/"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(elections_key):
    elections = dict(elections_key)
    scraper = TXResultsScraper(elections=elections)
    return scraper.get_all_results()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("TX Election Results")

election_mode = st.sidebar.radio(
    "Data Source", ["2026 Primaries (Live)", "Historical / Test"], index=0
)

if election_mode == "Historical / Test":
    available = [k for k, v in KNOWN_ELECTIONS.items() if v["year"] == 2025]
    selected_elections = st.sidebar.multiselect(
        "Election(s)", available, default=available[:1]
    )
    elections = {n: KNOWN_ELECTIONS[n]["id"] for n in selected_elections} if selected_elections else DEFAULT_ELECTIONS
else:
    elections = DEFAULT_ELECTIONS

elections_key = tuple(sorted(elections.items()))

st.sidebar.divider()
party_filter = st.sidebar.radio("Party", ["Both", "Republican", "Democratic"])
race_type = st.sidebar.radio("Race Type", ["All Races", "US Senate", "US House"])

st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
refresh_interval = st.sidebar.number_input("Interval (sec)", min_value=30, value=60, step=10)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    results = load_data(elections_key)
    statewide = results["statewide"]
    county = results["county"]
    status = results["status"]
    data_ok = not county.empty
except Exception as e:
    st.error(f"Could not fetch election data. Check your network connection.\n\n{e}")
    data_ok = False
    statewide = pd.DataFrame()
    county = pd.DataFrame()
    status = {}

# ---------------------------------------------------------------------------
# Export sidebar section
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Export")

if data_ok:
    filtered = filter_df(county, party_filter, race_type)
    filtered_sw = filter_df(statewide, party_filter, race_type)

    # CSV download
    st.sidebar.download_button(
        "Download CSV (filtered)", to_csv_bytes(filtered),
        "tx_results.csv", "text/csv"
    )

    # Excel download with multiple sheets
    senate_df = county[county["race_name"].str.startswith("U. S. SENATOR")]
    house_df = county[county["race_name"].str.startswith("U. S. REPRESENTATIVE")]
    excel_sheets = {
        "All County Results": filtered,
        "Statewide Summary": filtered_sw,
    }
    if not senate_df.empty:
        excel_sheets["Senate by County"] = senate_df
    if not house_df.empty:
        excel_sheets["House by County"] = house_df
    st.sidebar.download_button(
        "Download Excel (multi-sheet)", to_excel_bytes(excel_sheets),
        "tx_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Live CSV export button
    st.sidebar.caption("Write live CSVs for Excel data source:")
    if st.sidebar.button("Export Live CSVs to data/"):
        ok, msg = run_live_export()
        if ok:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
if election_mode == "Historical / Test":
    st.title("TX Election Results")
    st.caption("Viewing historical data for testing")
else:
    st.title("TX 2026 Primary Results")

# Reporting status bar
if status:
    cols = st.columns(len(status) * 2)
    i = 0
    for label, s in status.items():
        if s:
            cr, ct = s["counties_reporting"], s["counties_total"]
            pr, pt = s["precincts_reporting"], s["precincts_total"]
            cols[i].metric(f"{label} Counties", f"{cr} / {ct}")
            if ct > 0:
                cols[i].progress(cr / ct)
            cols[i + 1].metric(f"{label} Precincts", f"{pr:,} / {pt:,}")
            if pt > 0:
                cols[i + 1].progress(pr / pt)
            i += 2
    for s in status.values():
        if s and s["last_updated"]:
            st.caption(f"Last updated: {s['last_updated']}")
            break

if not data_ok:
    st.warning("No data available yet. Results will appear once reporting begins.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Race Results", "County Breakdown", "County View"])

# ---- Tab 1: Race Results (the main view) ---------------------------------
with tab1:
    sw = filter_df(statewide, party_filter, race_type)
    co = filter_df(county, party_filter, race_type)
    if sw.empty:
        st.info("No results match the current filters.")
    else:
        # Group by party, then by race
        for party_name in sorted(sw["party"].unique()):
            party_sw = sw[sw["party"] == party_name]
            color = party_color(party_name)
            st.markdown(f"### <span style='color:{color}'>{party_name}</span>",
                        unsafe_allow_html=True)

            races = sorted(party_sw["race_name"].unique(),
                           key=lambda r: (not r.startswith("U. S. SENATOR"), r))

            for race in races:
                race_sw = party_sw[party_sw["race_name"] == race].sort_values(
                    "votes", ascending=False
                )
                n_cands = len(race_sw)
                total_v = race_sw["votes"].sum()
                display_name = short_race_name(race)

                # Get precinct info from county data if available
                race_co = co[(co["race_name"] == race) & (co["party"] == party_name)]
                if not race_co.empty:
                    rptg = race_co["precincts_reporting"].sum()
                    total_p = race_co["total_precincts"].sum()
                    pct_rptg = f"{rptg:,}/{total_p:,} precincts" if total_p > 0 else ""
                else:
                    pct_rptg = ""

                # Uncontested — just show the name
                if n_cands == 1:
                    c = race_sw.iloc[0]
                    st.markdown(
                        f"**{display_name}** — {c['candidate']} *(uncontested)* "
                        f"&nbsp; {fmt_votes(c['votes'])} votes &nbsp; {pct_rptg}",
                        unsafe_allow_html=True
                    )
                    continue

                # Contested race — show as a clean card
                leader = race_sw.iloc[0]
                runner = race_sw.iloc[1]
                margin = leader["votes"] - runner["votes"]
                margin_p = (margin / total_v * 100) if total_v > 0 else 0

                # Header line
                close_tag = " :warning:" if 0 < margin_p < 5 and total_v > 0 else ""
                st.markdown(f"**{display_name}**{close_tag} &nbsp;&nbsp; "
                            f"<small style='color:#888'>{pct_rptg}</small>",
                            unsafe_allow_html=True)

                # Simple results table — just candidate, votes, %
                display_rows = []
                for _, row in race_sw.iterrows():
                    display_rows.append({
                        "Candidate": row["candidate"],
                        "Votes": fmt_votes(row["votes"]),
                        "Pct": fmt_pct(row["vote_pct"]),
                    })
                display_df = pd.DataFrame(display_rows)

                # Use columns layout: table on left, bar on right
                if total_v > 0:
                    left, right = st.columns([3, 2])
                    with left:
                        st.dataframe(display_df, use_container_width=True,
                                     hide_index=True, height=min(38 + 35 * len(display_rows), 400))
                    with right:
                        chart_data = race_sw[["candidate", "votes"]].set_index("candidate").sort_values("votes")
                        st.bar_chart(chart_data, horizontal=True, color=color, height=min(35 * len(display_rows) + 80, 400))
                else:
                    st.dataframe(display_df, use_container_width=True,
                                 hide_index=True, height=min(38 + 35 * len(display_rows), 300))

                st.divider()

# ---- Tab 2: County Breakdown (pick a race, see all counties) ---------------
with tab2:
    co = filter_df(county, party_filter, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        # Race selector with short names
        race_list = sorted(co["race_name"].unique(),
                           key=lambda r: (not r.startswith("U. S. SENATOR"), r))
        labels = [short_race_name(r) for r in race_list]
        selected_label = st.selectbox("Select Race", labels, key="race_select")
        selected_race = race_list[labels.index(selected_label)]
        race_data = co[co["race_name"] == selected_race]

        for race_party in sorted(race_data["party"].unique()):
            party_data = race_data[race_data["party"] == race_party]
            color = party_color(race_party)

            st.markdown(f"#### <span style='color:{color}'>{race_party}</span> — {selected_label}",
                        unsafe_allow_html=True)

            # Precinct progress
            total_p = party_data["total_precincts"].sum()
            rptg_p = party_data["precincts_reporting"].sum()
            if total_p > 0:
                pct = rptg_p / total_p
                st.progress(pct, text=f"{rptg_p:,} / {total_p:,} precincts ({pct:.0%})")

            # Candidate totals
            cand_totals = (party_data.groupby("candidate")
                           .agg(votes=("votes", "sum"), early_votes=("early_votes", "sum"))
                           .sort_values("votes", ascending=False)
                           .reset_index())
            total_v = cand_totals["votes"].sum()
            cand_totals["pct"] = cand_totals["votes"].apply(
                lambda v: fmt_pct(v / total_v * 100) if total_v > 0 else "0%"
            )
            cand_totals["votes"] = cand_totals["votes"].apply(fmt_votes)
            cand_totals["early_votes"] = cand_totals["early_votes"].apply(fmt_votes)
            display_cands = cand_totals.rename(columns={
                "candidate": "Candidate", "votes": "Votes",
                "early_votes": "Early Votes", "pct": "Pct"
            })
            st.dataframe(display_cands, use_container_width=True, hide_index=True)

            # County pivot table
            pivot = party_data.pivot_table(
                index="county", columns="candidate",
                values="votes", aggfunc="sum", fill_value=0
            )
            # Add total column and sort by it
            pivot["Total"] = pivot.sum(axis=1)
            pivot = pivot.sort_values("Total", ascending=False)

            # Add precincts
            prec = (party_data.groupby("county")
                    .agg(pr=("precincts_reporting", "first"),
                         tp=("total_precincts", "first"))
                    .reset_index().set_index("county"))
            pivot = pivot.join(prec)
            pivot["Precincts"] = pivot.apply(
                lambda r: f"{int(r['pr'])}/{int(r['tp'])}", axis=1
            )
            pivot = pivot.drop(columns=["pr", "tp"])

            # Format vote numbers
            for col in pivot.columns:
                if col != "Precincts":
                    pivot[col] = pivot[col].apply(lambda v: fmt_votes(v) if isinstance(v, (int, float)) else v)

            pivot = pivot.reset_index().rename(columns={"county": "County"})
            st.dataframe(pivot, use_container_width=True, hide_index=True, height=600)

# ---- Tab 3: County View ---------------------------------------------------
with tab3:
    co = filter_df(county, party_filter, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        counties = sorted(co["county"].unique())
        selected_county = st.selectbox("Select County", counties, key="county_select")
        county_data = co[co["county"] == selected_county]

        # County precinct summary
        first_race = county_data.groupby("race_name").first().iloc[0]
        pr, tp = int(first_race["precincts_reporting"]), int(first_race["total_precincts"])
        if tp > 0:
            st.progress(pr / tp, text=f"{selected_county} — {pr}/{tp} precincts ({pr/tp:.0%})")

        for (p, race), grp in county_data.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            color = party_color(p)
            display_name = short_race_name(race)
            n_cands = len(grp_sorted)

            if n_cands == 1:
                c = grp_sorted.iloc[0]
                st.markdown(
                    f"<span style='color:{color}'>{p}</span> **{display_name}** — "
                    f"{c['candidate']} *(uncontested)* {fmt_votes(c['votes'])} votes",
                    unsafe_allow_html=True
                )
                continue

            st.markdown(f"<span style='color:{color}'>{p}</span> — **{display_name}**",
                        unsafe_allow_html=True)

            display_rows = []
            for _, row in grp_sorted.iterrows():
                display_rows.append({
                    "Candidate": row["candidate"],
                    "Votes": fmt_votes(row["votes"]),
                    "Early Votes": fmt_votes(row["early_votes"]),
                    "Pct": fmt_pct(row["vote_pct"]),
                })
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
