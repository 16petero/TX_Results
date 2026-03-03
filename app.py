"""
TX Primary Election Results — Streamlit Dashboard

Launch: streamlit run app.py
"""

import time
import io
import streamlit as st
import pandas as pd
from scraper import TXResultsScraper, KNOWN_ELECTIONS, DEFAULT_ELECTIONS


st.set_page_config(page_title="TX Primary Results", page_icon="\U0001f5f3\ufe0f", layout="wide")

# Party colors for styling
PARTY_COLORS = {
    "Republican": "#cc0000",
    "Democratic": "#0057b8",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def filter_df(df, party_filter, race_type):
    """Apply sidebar filters to a DataFrame."""
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


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def party_color(party_name):
    return PARTY_COLORS.get(party_name, "#666666")


def is_contested(grp):
    """A race is contested if it has more than 1 candidate."""
    return grp["candidate"].nunique() > 1


def margin_pct(leader_votes, runner_votes, total_votes):
    """Margin as percentage points."""
    if total_votes == 0:
        return 0.0
    return (leader_votes - runner_votes) / total_votes * 100


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(elections_key):
    """Load data for the given election set. elections_key is used for caching."""
    elections = dict(elections_key)
    scraper = TXResultsScraper(elections=elections)
    return scraper.get_all_results()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("Settings")

# Election selector
election_mode = st.sidebar.radio(
    "Election",
    ["2026 Primaries (Tonight)", "Historical / Test"],
    index=0,
)

if election_mode == "Historical / Test":
    available = [k for k, v in KNOWN_ELECTIONS.items() if v["year"] == 2025]
    selected_elections = st.sidebar.multiselect(
        "Select Election(s)", available, default=available[:1]
    )
    if selected_elections:
        elections = {name: KNOWN_ELECTIONS[name]["id"] for name in selected_elections}
    else:
        elections = DEFAULT_ELECTIONS
else:
    elections = DEFAULT_ELECTIONS

# Convert to hashable key for caching
elections_key = tuple(sorted(elections.items()))

st.sidebar.divider()
st.sidebar.subheader("Filters")
party_filter = st.sidebar.radio("Party", ["Both", "Republican", "Democratic"])
race_type = st.sidebar.radio("Race Type", ["All Races", "US Senate", "US House"])

st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
refresh_interval = st.sidebar.number_input("Interval (seconds)", min_value=30, value=60, step=10)

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

# Export buttons (after data loaded)
if data_ok:
    st.sidebar.divider()
    st.sidebar.subheader("Export")
    filtered_county = filter_df(county, party_filter, race_type)
    st.sidebar.download_button("Download CSV", to_csv_bytes(filtered_county),
                               "tx_primary_results.csv", "text/csv")
    st.sidebar.download_button("Download Excel", to_excel_bytes(filtered_county),
                               "tx_primary_results.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------------------------
# Header + reporting status
# ---------------------------------------------------------------------------
if election_mode == "Historical / Test":
    st.title("TX Election Results (Test Mode)")
    st.caption("Viewing historical data for testing")
else:
    st.title("TX 2026 Primary Election Results")

if status:
    metric_cols = st.columns(len(status) * 2)
    i = 0
    for label, s in status.items():
        if s:
            color = party_color(label)
            # Counties progress
            cr, ct = s["counties_reporting"], s["counties_total"]
            metric_cols[i].metric(f"{label} Counties", f"{cr} / {ct}")
            if ct > 0:
                metric_cols[i].progress(cr / ct if ct else 0)
            # Precincts progress
            pr, pt = s["precincts_reporting"], s["precincts_total"]
            metric_cols[i + 1].metric(f"{label} Precincts", f"{pr} / {pt}")
            if pt > 0:
                metric_cols[i + 1].progress(pr / pt if pt else 0)
            i += 2
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
    sw = filter_df(statewide, party_filter, race_type)
    if sw.empty:
        st.info("No statewide results match the current filters.")
    else:
        summary_rows = []
        for (p, race), grp in sw.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            leader = grp_sorted.iloc[0]
            runner = grp_sorted.iloc[1] if len(grp_sorted) > 1 else None
            total_votes = int(grp["votes"].sum())
            n_cands = len(grp)
            contested = n_cands > 1

            leader_v = int(leader["votes"])
            runner_v = int(runner["votes"]) if runner is not None else 0
            margin = leader_v - runner_v
            margin_p = margin_pct(leader_v, runner_v, total_votes) if total_votes > 0 else 0

            summary_rows.append({
                "Party": p,
                "Race": race,
                "Status": "Contested" if contested else "Uncontested",
                "Leader": leader["candidate"],
                "Leader Votes": leader_v,
                "Leader %": leader["vote_pct"],
                "Runner-Up": runner["candidate"] if runner is not None else "-",
                "Runner-Up Votes": runner_v,
                "Margin": margin,
                "Margin %": round(margin_p, 1),
                "Total Votes": total_votes,
                "Candidates": n_cands,
            })
        summary_df = pd.DataFrame(summary_rows)

        # Sort: contested first (by closest margin), then uncontested
        summary_df["_sort"] = summary_df.apply(
            lambda r: (0, r["Margin %"]) if r["Status"] == "Contested" else (1, 0), axis=1
        )
        summary_df = summary_df.sort_values("_sort").drop(columns="_sort")

        # Highlight close races
        def style_row(row):
            styles = [""] * len(row)
            color = party_color(row["Party"])
            # Party column color
            party_idx = summary_df.columns.get_loc("Party")
            styles[party_idx] = f"color: {color}; font-weight: bold"
            # Close race highlight (margin < 5%)
            if row["Status"] == "Contested" and abs(row["Margin %"]) < 5 and row["Total Votes"] > 0:
                styles = [f"background-color: #fff3cd" if s == "" else s for s in styles]
            # Uncontested: grey out
            if row["Status"] == "Uncontested":
                styles = [f"color: #999" if "font-weight" not in s else s for s in styles]
            return styles

        styled = summary_df.style.apply(style_row, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True, height=700)

        # Quick counts
        contested_count = (summary_df["Status"] == "Contested").sum()
        close_count = ((summary_df["Status"] == "Contested") &
                       (summary_df["Margin %"].abs() < 5) &
                       (summary_df["Total Votes"] > 0)).sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Races", len(summary_df))
        c2.metric("Contested", contested_count)
        c3.metric("Close Races (<5%)", close_count)

# ---- Tab 2: Race Detail (county-level) -----------------------------------
with tab2:
    co = filter_df(county, party_filter, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        # Build race list with contest status
        race_info = []
        for race in co["race_name"].unique():
            n_cands = co[co["race_name"] == race]["candidate"].nunique()
            tag = "" if n_cands > 1 else " [Uncontested]"
            race_info.append((race, f"{race}{tag}"))
        race_info.sort(key=lambda x: (x[1].endswith("[Uncontested]"), x[0]))
        race_names = [r[0] for r in race_info]
        race_labels = [r[1] for r in race_info]

        # Default to Senate if available
        default_ix = 0
        for i, r in enumerate(race_names):
            if r.startswith("U. S. SENATOR"):
                default_ix = i
                break

        selected_label = st.selectbox("Select Race", race_labels, index=default_ix, key="race_select")
        selected_race = race_names[race_labels.index(selected_label)]
        race_data = co[co["race_name"] == selected_race]

        for race_party in sorted(race_data["party"].unique()):
            party_data = race_data[race_data["party"] == race_party]
            color = party_color(race_party)
            st.markdown(f"### <span style='color:{color}'>{race_party} Primary</span>",
                        unsafe_allow_html=True)

            # Reporting progress for this race
            total_prec = party_data["total_precincts"].sum()
            rptg_prec = party_data["precincts_reporting"].sum()
            if total_prec > 0:
                pct_rptg = rptg_prec / total_prec
                st.progress(pct_rptg, text=f"{rptg_prec:,} / {total_prec:,} precincts reporting ({pct_rptg:.0%})")

            # Candidate totals
            cand_totals = (party_data.groupby("candidate")
                           .agg(votes=("votes", "sum"), early_votes=("early_votes", "sum"))
                           .sort_values("votes", ascending=False)
                           .reset_index())
            total_v = cand_totals["votes"].sum()
            cand_totals["pct"] = (cand_totals["votes"] / total_v * 100).round(2) if total_v > 0 else 0.0

            # Styled candidate table — bold leader
            def style_candidates(row):
                styles = [""] * len(row)
                if row.name == 0:  # leader row
                    styles = ["font-weight: bold"] * len(row)
                return styles

            display_cands = cand_totals.rename(columns={
                "candidate": "Candidate", "votes": "Votes",
                "early_votes": "Early Votes", "pct": "%"
            })
            styled_cands = display_cands.style.apply(style_candidates, axis=1)
            st.dataframe(styled_cands, use_container_width=True, hide_index=True)

            # Horizontal bar chart (better for many candidates)
            if total_v > 0:
                chart_df = cand_totals.set_index("candidate")[["votes"]].sort_values("votes")
                st.bar_chart(chart_df, horizontal=True, color=color)

            # County breakdown
            with st.expander("County Breakdown", expanded=False):
                pivot = party_data.pivot_table(
                    index="county", columns="candidate",
                    values="votes", aggfunc="sum", fill_value=0
                ).reset_index()
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
    co = filter_df(county, party_filter, race_type)
    if co.empty:
        st.info("No county results match the current filters.")
    else:
        counties = sorted(co["county"].unique())
        selected_county = st.selectbox("Select County", counties, key="county_select")
        county_data = co[co["county"] == selected_county]

        # County-level precinct summary
        county_prec = county_data.groupby("race_name").agg(
            pr=("precincts_reporting", "first"),
            tp=("total_precincts", "first")
        ).iloc[0]
        if county_prec["tp"] > 0:
            pct = county_prec["pr"] / county_prec["tp"]
            st.progress(pct, text=f"{int(county_prec['pr'])} / {int(county_prec['tp'])} precincts ({pct:.0%})")

        for (p, race), grp in county_data.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            prec_str = f"{int(grp_sorted.iloc[0]['precincts_reporting'])}/{int(grp_sorted.iloc[0]['total_precincts'])} precincts"
            color = party_color(p)
            n_cands = len(grp_sorted)
            tag = "" if n_cands > 1 else " [Uncontested]"
            st.markdown(f"**<span style='color:{color}'>{p}</span>** — {race}{tag}",
                        unsafe_allow_html=True)
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
