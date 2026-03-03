"""
TX Election Results — Streamlit Dashboard

Launch: streamlit run app.py
"""

import time
import io
import os
from datetime import datetime
import streamlit as st
import pandas as pd
from scraper import TXResultsScraper, KNOWN_ELECTIONS, DEFAULT_ELECTIONS


st.set_page_config(page_title="TX Election Results", page_icon="\U0001f5f3\ufe0f", layout="wide")

st.markdown("""
<style>
    .stDataFrame td, .stDataFrame th { padding: 4px 8px !important; font-size: 14px; }
    [data-testid="stMetricLabel"] { font-size: 13px; }
    .stProgress > div > div { height: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PARTY_COLORS = {"Republican": "#cc0000", "Democratic": "#0057b8"}


def short_race_name(name):
    """Shorten verbose race names for display."""
    name = name.strip()
    if name.startswith("U. S. SENATOR"):
        return "US Senate"
    if name.startswith("U. S. REPRESENTATIVE DISTRICT"):
        dist = name.replace("U. S. REPRESENTATIVE DISTRICT", "").strip()
        return f"US House TX-{dist}"
    if name.startswith("STATE SENATOR, DISTRICT"):
        dist = name.replace("STATE SENATOR, DISTRICT", "").strip()
        return f"State Senate Dist. {dist}"
    if name.startswith("PROPOSITION"):
        return name  # Already short enough
    return name


def fmt_pct(val):
    if pd.isna(val) or val == 0:
        return "0%"
    if val == round(val):
        return f"{val:.0f}%"
    return f"{val:.1f}%"


def fmt_votes(val):
    return f"{int(val):,}"


def party_color(name):
    # Check if name contains a party keyword
    for party, color in PARTY_COLORS.items():
        if party in name:
            return color
    return "#666666"


def filter_df(df, race_type):
    if df.empty:
        return df
    if race_type == "US Senate":
        return df[df["race_name"].str.startswith("U. S. SENATOR")]
    elif race_type == "US House":
        return df[df["race_name"].str.startswith("U. S. REPRESENTATIVE")]
    return df


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(dfs_dict):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for sheet, df in dfs_dict.items():
            if not df.empty:
                df.to_excel(w, sheet_name=sheet[:31], index=False)
    return buf.getvalue()


def write_live_csv(county, statewide):
    """Write a single live CSV file for Excel data source."""
    os.makedirs("data", exist_ok=True)
    county.to_csv("data/tx_results_LIVE.csv", index=False)
    return len(county)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(elections_key, race_filter_key):
    elections = dict(elections_key)
    race_filter = race_filter_key if race_filter_key else None
    scraper = TXResultsScraper(elections=elections, race_filter=race_filter)
    return scraper.get_all_results()


# ---------------------------------------------------------------------------
# Sidebar: Election Selection
# ---------------------------------------------------------------------------
st.sidebar.title("TX Election Results")

# Build election list grouped by year
elections_by_year = {}
for name, info in KNOWN_ELECTIONS.items():
    elections_by_year.setdefault(info["year"], []).append(name)

# Default to 2026 primaries
all_names = list(KNOWN_ELECTIONS.keys())
default_selections = ["2026 Republican Primary", "2026 Democratic Primary"]

selected_elections = st.sidebar.multiselect(
    "Elections",
    options=all_names,
    default=default_selections,
    help="Select one or more elections to view"
)

if not selected_elections:
    st.warning("Select at least one election from the sidebar.")
    st.stop()

# Determine if we should filter to federal races or show all
# Primaries have hundreds of races — filter to federal by default
# Other types have few races — show all
selected_types = [KNOWN_ELECTIONS[n]["type"] for n in selected_elections]
has_primaries = "primary" in selected_types

if has_primaries:
    race_scope = st.sidebar.radio(
        "Races to show",
        ["Federal Only (Senate + House)", "All Races"],
        index=0,
        help="Primaries have 100+ races. Federal Only shows US Senate and US House."
    )
    if race_scope == "Federal Only (Senate + House)":
        race_filter = TXResultsScraper.TARGET_PREFIXES
    else:
        race_filter = None
else:
    race_filter = None

st.sidebar.divider()

# Race type sub-filter (only relevant when showing federal)
if race_filter:
    race_type = st.sidebar.radio("Race Type", ["All", "US Senate", "US House"])
else:
    race_type = "All"

# ---------------------------------------------------------------------------
# Sidebar: Auto-Refresh & Live Export
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Auto-Refresh")
auto_refresh = st.sidebar.checkbox("Enable auto-refresh", value=False)
refresh_interval = st.sidebar.number_input("Interval (sec)", min_value=30, value=60, step=10)
live_csv = st.sidebar.checkbox(
    "Update live CSV on refresh",
    value=False,
    help="Writes data/tx_results_LIVE.csv on each refresh for Excel"
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
elections = {n: KNOWN_ELECTIONS[n]["id"] for n in selected_elections}
elections_key = tuple(sorted(elections.items()))
race_filter_key = race_filter if race_filter else None

try:
    results = load_data(elections_key, race_filter_key)
    statewide = results["statewide"]
    county = results["county"]
    status = results["status"]
    data_ok = not county.empty
except Exception as e:
    st.error(f"Could not fetch election data.\n\n{e}")
    data_ok = False
    statewide = pd.DataFrame()
    county = pd.DataFrame()
    status = {}

# Write live CSV if enabled (happens every load, including auto-refresh)
if data_ok and live_csv:
    write_live_csv(county, statewide)

# ---------------------------------------------------------------------------
# Sidebar: Export
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Export")

if data_ok:
    filtered = filter_df(county, race_type)
    filtered_sw = filter_df(statewide, race_type)

    st.sidebar.download_button(
        "Download CSV", to_csv_bytes(filtered),
        "tx_results.csv", "text/csv"
    )

    sheets = {"County Results": filtered}
    if not filtered_sw.empty:
        sheets["Statewide Summary"] = filtered_sw
    st.sidebar.download_button(
        "Download Excel", to_excel_bytes(sheets),
        "tx_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.sidebar.button("Write Live CSV Now"):
        n = write_live_csv(county, statewide)
        st.sidebar.success(f"Wrote {n:,} rows to data/tx_results_LIVE.csv")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("TX Election Results")
st.caption(" + ".join(selected_elections))

# Reporting status
if status:
    cols = st.columns(min(len(status) * 2, 6))
    i = 0
    for label, s in status.items():
        if s and i + 1 < len(cols):
            cr, ct = s["counties_reporting"], s["counties_total"]
            pr, pt = s["precincts_reporting"], s["precincts_total"]
            cols[i].metric(f"{label} Counties", f"{cr}/{ct}")
            if ct > 0:
                cols[i].progress(cr / ct)
            cols[i + 1].metric(f"{label} Precincts", f"{pr:,}/{pt:,}")
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
# Apply race type filter
# ---------------------------------------------------------------------------
sw_filtered = filter_df(statewide, race_type)
co_filtered = filter_df(county, race_type)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Race Results", "County Breakdown", "County View"])

# ---- Tab 1: Race Results -------------------------------------------------
with tab1:
    if sw_filtered.empty:
        st.info("No results match the current filters.")
    else:
        for election_label in sorted(sw_filtered["party"].unique()):
            label_sw = sw_filtered[sw_filtered["party"] == election_label]
            label_co = co_filtered[co_filtered["party"] == election_label] if not co_filtered.empty else pd.DataFrame()
            color = party_color(election_label)

            st.markdown(f"### <span style='color:{color}'>{election_label}</span>",
                        unsafe_allow_html=True)

            races = sorted(label_sw["race_name"].unique(),
                           key=lambda r: (not r.startswith("U. S. SENATOR"), r))

            for race in races:
                race_sw = label_sw[label_sw["race_name"] == race].sort_values(
                    "votes", ascending=False
                )
                n_cands = len(race_sw)
                total_v = race_sw["votes"].sum()
                display_name = short_race_name(race)

                # Precinct info from county data
                race_co = label_co[label_co["race_name"] == race] if not label_co.empty else pd.DataFrame()
                if not race_co.empty:
                    rptg = int(race_co["precincts_reporting"].sum())
                    total_p = int(race_co["total_precincts"].sum())
                    pct_rptg = f"{rptg:,}/{total_p:,} precincts" if total_p > 0 else ""
                else:
                    pct_rptg = ""

                # Uncontested
                if n_cands == 1:
                    c = race_sw.iloc[0]
                    st.markdown(
                        f"**{display_name}** — {c['candidate']} *(uncontested)* "
                        f"&nbsp; {fmt_votes(c['votes'])} votes &nbsp; {pct_rptg}",
                        unsafe_allow_html=True
                    )
                    continue

                # Contested race
                leader = race_sw.iloc[0]
                runner = race_sw.iloc[1]
                margin_v = leader["votes"] - runner["votes"]
                margin_p = (margin_v / total_v * 100) if total_v > 0 else 0

                close_tag = " :warning:" if 0 < margin_p < 5 and total_v > 0 else ""
                st.markdown(
                    f"**{display_name}**{close_tag} &nbsp;&nbsp; "
                    f"<small style='color:#888'>{pct_rptg}</small>",
                    unsafe_allow_html=True
                )

                display_rows = []
                for _, row in race_sw.iterrows():
                    display_rows.append({
                        "Candidate": row["candidate"],
                        "Votes": fmt_votes(row["votes"]),
                        "Pct": fmt_pct(row["vote_pct"]),
                    })
                display_df = pd.DataFrame(display_rows)

                if total_v > 0 and n_cands > 1:
                    left, right = st.columns([3, 2])
                    with left:
                        st.dataframe(display_df, use_container_width=True,
                                     hide_index=True,
                                     height=min(38 + 35 * n_cands, 400))
                    with right:
                        chart = race_sw[["candidate", "votes"]].set_index("candidate").sort_values("votes")
                        st.bar_chart(chart, horizontal=True, color=color,
                                     height=min(35 * n_cands + 80, 400))
                else:
                    st.dataframe(display_df, use_container_width=True,
                                 hide_index=True,
                                 height=min(38 + 35 * n_cands, 300))

                st.divider()

# ---- Tab 2: County Breakdown ---------------------------------------------
with tab2:
    if co_filtered.empty:
        st.info("No county results match the current filters.")
    else:
        race_list = sorted(co_filtered["race_name"].unique(),
                           key=lambda r: (not r.startswith("U. S. SENATOR"), r))
        labels = [short_race_name(r) for r in race_list]
        selected_label = st.selectbox("Select Race", labels, key="race_select")
        selected_race = race_list[labels.index(selected_label)]
        race_data = co_filtered[co_filtered["race_name"] == selected_race]

        for election_label in sorted(race_data["party"].unique()):
            party_data = race_data[race_data["party"] == election_label]
            color = party_color(election_label)

            st.markdown(
                f"#### <span style='color:{color}'>{election_label}</span> — {selected_label}",
                unsafe_allow_html=True
            )

            total_p = int(party_data["total_precincts"].sum())
            rptg_p = int(party_data["precincts_reporting"].sum())
            if total_p > 0:
                pct = rptg_p / total_p
                st.progress(pct, text=f"{rptg_p:,} / {total_p:,} precincts ({pct:.0%})")

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
            st.dataframe(
                cand_totals.rename(columns={
                    "candidate": "Candidate", "votes": "Votes",
                    "early_votes": "Early Votes", "pct": "Pct"
                }),
                use_container_width=True, hide_index=True
            )

            # County pivot
            pivot = party_data.pivot_table(
                index="county", columns="candidate",
                values="votes", aggfunc="sum", fill_value=0
            )
            pivot["Total"] = pivot.sum(axis=1)
            pivot = pivot.sort_values("Total", ascending=False)

            prec = (party_data.groupby("county")
                    .agg(pr=("precincts_reporting", "first"),
                         tp=("total_precincts", "first"))
                    .reset_index().set_index("county"))
            pivot = pivot.join(prec)
            pivot["Precincts"] = pivot.apply(
                lambda r: f"{int(r['pr'])}/{int(r['tp'])}", axis=1
            )
            pivot = pivot.drop(columns=["pr", "tp"])

            for col in pivot.columns:
                if col != "Precincts":
                    pivot[col] = pivot[col].apply(
                        lambda v: fmt_votes(v) if isinstance(v, (int, float)) else v
                    )

            pivot = pivot.reset_index().rename(columns={"county": "County"})
            st.dataframe(pivot, use_container_width=True, hide_index=True, height=600)

# ---- Tab 3: County View --------------------------------------------------
with tab3:
    if co_filtered.empty:
        st.info("No county results match the current filters.")
    else:
        counties = sorted(co_filtered["county"].unique())
        selected_county = st.selectbox("Select County", counties, key="county_select")
        county_data = co_filtered[co_filtered["county"] == selected_county]

        first = county_data.groupby("race_name").first().iloc[0]
        pr, tp = int(first["precincts_reporting"]), int(first["total_precincts"])
        if tp > 0:
            st.progress(pr / tp, text=f"{selected_county} — {pr}/{tp} precincts ({pr/tp:.0%})")

        for (el, race), grp in county_data.groupby(["party", "race_name"]):
            grp_sorted = grp.sort_values("votes", ascending=False)
            color = party_color(el)
            display_name = short_race_name(race)
            n = len(grp_sorted)

            if n == 1:
                c = grp_sorted.iloc[0]
                st.markdown(
                    f"<span style='color:{color}'>{el}</span> **{display_name}** — "
                    f"{c['candidate']} *(uncontested)* {fmt_votes(c['votes'])} votes",
                    unsafe_allow_html=True
                )
                continue

            st.markdown(
                f"<span style='color:{color}'>{el}</span> — **{display_name}**",
                unsafe_allow_html=True
            )
            rows = []
            for _, row in grp_sorted.iterrows():
                rows.append({
                    "Candidate": row["candidate"],
                    "Votes": fmt_votes(row["votes"]),
                    "Early Votes": fmt_votes(row["early_votes"]),
                    "Pct": fmt_pct(row["vote_pct"]),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
