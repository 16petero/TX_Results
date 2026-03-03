"""
TX Primary Election Results — Streamlit Dashboard

Launch: streamlit run app.py
"""

import time
import io
import streamlit as st
import pandas as pd
from scraper import TXResultsScraper


st.set_page_config(page_title="TX Primary Results", page_icon="\U0001f5f3\ufe0f", layout="wide")


@st.cache_data(ttl=60)
def load_data():
    scraper = TXResultsScraper()
    return scraper.get_all_results()


def filter_df(df, party, race_type):
    """Apply sidebar filters to a DataFrame."""
    if df.empty:
        return df
    out = df.copy()
    if party != "Both":
        out = out[out["party"] == party]
    if race_type == "US Senate":
        out = out[out["race_name"].str.startswith("U. S. SENATOR")]
    elif race_type == "US House":
        out = out[out["race_name"].str.startswith("U. S. REPRESENTATIVE")]
    return out


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
try:
    results = load_data()
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
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("Filters")
party = st.sidebar.radio("Party", ["Both", "Republican", "Democratic"])
race_type = st.sidebar.radio("Race Type", ["All Races", "US Senate", "US House"])

st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
refresh_interval = st.sidebar.number_input("Interval (seconds)", min_value=30, value=60, step=10)

if data_ok:
    st.sidebar.divider()
    st.sidebar.subheader("Export")
    filtered_county = filter_df(county, party, race_type)
    st.sidebar.download_button("Download CSV", to_csv_bytes(filtered_county),
                               "tx_primary_results.csv", "text/csv")
    st.sidebar.download_button("Download Excel", to_excel_bytes(filtered_county),
                               "tx_primary_results.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------------------------
# Header + status
# ---------------------------------------------------------------------------
st.title("TX 2026 Primary Election Results")

if status:
    cols = st.columns(len(status) * 2)
    i = 0
    for party_name, s in status.items():
        if s:
            cols[i].metric(f"{party_name} Counties", f"{s['counties_reporting']}/{s['counties_total']}")
            cols[i + 1].metric(f"{party_name} Precincts", f"{s['precincts_reporting']}/{s['precincts_total']}")
            i += 2
    # Show last updated from first available
    for s in status.values():
        if s and s["last_updated"]:
            st.caption(f"Last updated: {s['last_updated']}")
            break

if not data_ok:
    st.warning("No data available yet. Results will appear once the API returns data.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Statewide Overview", "Race Detail", "County View"])

# ---- Tab 1: Statewide Overview -------------------------------------------
with tab1:
    sw = filter_df(statewide, party, race_type)
    if sw.empty:
        st.info("No statewide results match the current filters.")
    else:
        # Build summary: leading candidate per race
        summary_rows = []
        for (p, race), grp in sw.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            leader = grp_sorted.iloc[0]
            runner = grp_sorted.iloc[1] if len(grp_sorted) > 1 else None
            total_votes = grp["votes"].sum()
            summary_rows.append({
                "Party": p,
                "Race": race,
                "Leader": leader["candidate"],
                "Leader Votes": int(leader["votes"]),
                "Leader %": leader["vote_pct"],
                "Runner-Up": runner["candidate"] if runner is not None else "",
                "Margin": int(leader["votes"] - runner["votes"]) if runner is not None else int(leader["votes"]),
                "Total Votes": int(total_votes),
                "Candidates": len(grp),
            })
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ---- Tab 2: Race Detail (county-level) -----------------------------------
with tab2:
    co = filter_df(county, party, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        races = sorted(co["race_name"].unique())
        # Default to Senate if available
        default_ix = 0
        for i, r in enumerate(races):
            if r.startswith("U. S. SENATOR"):
                default_ix = i
                break
        selected_race = st.selectbox("Select Race", races, index=default_ix, key="race_select")
        race_data = co[co["race_name"] == selected_race]

        # Show results for each party present
        for race_party in sorted(race_data["party"].unique()):
            party_data = race_data[race_data["party"] == race_party]
            st.subheader(f"{race_party} Primary")

            # Candidate totals
            cand_totals = (party_data.groupby("candidate")
                           .agg(votes=("votes", "sum"), early_votes=("early_votes", "sum"))
                           .sort_values("votes", ascending=False)
                           .reset_index())
            total_v = cand_totals["votes"].sum()
            cand_totals["pct"] = (cand_totals["votes"] / total_v * 100).round(2) if total_v > 0 else 0
            st.dataframe(cand_totals.rename(columns={
                "candidate": "Candidate", "votes": "Votes",
                "early_votes": "Early Votes", "pct": "%"
            }), use_container_width=True, hide_index=True)

            # Bar chart
            chart_df = cand_totals.set_index("candidate")["votes"]
            st.bar_chart(chart_df)

            # County breakdown — pivot table
            with st.expander("County Breakdown", expanded=False):
                pivot = party_data.pivot_table(
                    index="county", columns="candidate",
                    values="votes", aggfunc="sum", fill_value=0
                ).reset_index()
                # Add precincts info
                prec = (party_data.groupby("county")
                        .agg(precincts_reporting=("precincts_reporting", "first"),
                             total_precincts=("total_precincts", "first"))
                        .reset_index())
                pivot = pivot.merge(prec, on="county", how="left")
                pivot = pivot.rename(columns={"county": "County",
                                              "precincts_reporting": "Precincts Rptg",
                                              "total_precincts": "Total Precincts"})
                st.dataframe(pivot, use_container_width=True, hide_index=True, height=600)

# ---- Tab 3: County View --------------------------------------------------
with tab3:
    co = filter_df(county, party, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        counties = sorted(co["county"].unique())
        selected_county = st.selectbox("Select County", counties, key="county_select")
        county_data = co[co["county"] == selected_county]

        for (p, race), grp in county_data.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            prec_str = f"{grp_sorted.iloc[0]['precincts_reporting']}/{grp_sorted.iloc[0]['total_precincts']} precincts"
            st.subheader(f"{p} — {race}")
            st.caption(prec_str)
            display = grp_sorted[["candidate", "votes", "early_votes", "vote_pct"]].rename(columns={
                "candidate": "Candidate", "votes": "Votes",
                "early_votes": "Early Votes", "vote_pct": "%"
            })
            st.dataframe(display, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
