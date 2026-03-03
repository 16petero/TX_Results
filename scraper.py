"""
TXResultsScraper: Fetches and decodes TX primary election results from the
Civix ENR API. Returns pandas DataFrames with county-level data.

Supports multiple election types (primaries, specials, runoffs) for testing
against historical data with real vote counts.
"""

import base64
import json
import time
import requests
import pandas as pd


# All known elections on the Civix platform
KNOWN_ELECTIONS = {
    "2026 Republican Primary": {"id": 53813, "year": 2026, "type": "primary"},
    "2026 Democratic Primary": {"id": 53814, "year": 2026, "type": "primary"},
    "2026 Runoff CD-18": {"id": 54612, "year": 2026, "type": "runoff"},
    "2026 Runoff SD-9": {"id": 54613, "year": 2026, "type": "runoff"},
    "2025 Special CD-18": {"id": 51742, "year": 2025, "type": "special"},
    "2025 Special SD-9": {"id": 51830, "year": 2025, "type": "special"},
    "2025 Constitutional Amendment": {"id": 51031, "year": 2025, "type": "amendment"},
}

# Default election set for tonight
DEFAULT_ELECTIONS = {
    "Republican": 53813,
    "Democratic": 53814,
}


class TXResultsScraper:
    BASE_URL = "https://goelect.txelections.civixapps.com/api-ivis-system/api/s3/enr"
    TARGET_PREFIXES = ("U. S. SENATOR", "U. S. REPRESENTATIVE DISTRICT")

    # Sentinel to distinguish "not passed" from "explicitly passed None"
    _UNSET = object()

    def __init__(self, elections=None, race_filter=_UNSET):
        """
        Args:
            elections: dict of {label: election_id}. Defaults to tonight's primaries.
            race_filter: tuple of race name prefixes to include.
                         Defaults to US Senate + US House for primaries.
                         Pass None to include ALL races (recommended for
                         specials, runoffs, amendments).
        """
        self.elections = elections or DEFAULT_ELECTIONS
        if race_filter is self._UNSET:
            self.race_filter = self.TARGET_PREFIXES
        else:
            self.race_filter = race_filter
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        })

    def _fetch_json(self, endpoint):
        """GET {BASE_URL}/{endpoint} with retries and exponential backoff."""
        url = f"{self.BASE_URL}/{endpoint}"
        last_exc = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                last_exc = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_exc

    @staticmethod
    def _decode_b64(payload):
        """Decode a base64-encoded JSON string."""
        return json.loads(base64.b64decode(payload))

    @staticmethod
    def _iter_candidates(candidates):
        """Yield candidate dicts regardless of whether the API returns a list or dict."""
        if isinstance(candidates, list):
            yield from candidates
        elif isinstance(candidates, dict):
            yield from candidates.values()

    def _matches_filter(self, race_name):
        """Return True if race_name matches the configured race filter."""
        if not self.race_filter:
            return True
        return race_name.startswith(self.race_filter)

    def fetch_reporting_status(self, election_id):
        """Return reporting status dict from the Home section."""
        data = self._fetch_json(f"election/{election_id}")
        home = self._decode_b64(data["Home"])
        cr = home.get("CountiesReporting", {})
        polling = home.get("PollingReporting", {})
        return {
            "counties_reporting": cr.get("CR", 0),
            "counties_total": cr.get("CT", 254),
            "precincts_reporting": polling.get("PLR", 0),
            "precincts_total": polling.get("PLT", 0),
            "last_updated": home.get("LastUpdatedTime", ""),
            "refresh_interval": home.get("RefreshTime", 5),
        }

    def fetch_statewide_results(self, label, election_id):
        """Return a DataFrame of statewide race results.

        Checks Federal, Districted, and StateWide sections (different
        election types store races in different sections).
        """
        data = self._fetch_json(f"election/{election_id}")
        rows = []

        for section_key in ("Federal", "Districted", "StateWide", "StateWideQ"):
            raw = data.get(section_key)
            if not raw or not isinstance(raw, str) or len(raw) < 20:
                continue
            try:
                section = self._decode_b64(raw)
            except Exception:
                continue
            races = section.get("Races") or []
            if isinstance(races, dict):
                races = list(races.values())
            for race in races:
                name = race.get("N", "")
                if not self._matches_filter(name):
                    continue
                for c in self._iter_candidates(race.get("Candidates", [])):
                    rows.append({
                        "party": label,
                        "race_name": name.strip(),
                        "race_id": race.get("id"),
                        "candidate": c.get("N", ""),
                        "votes": c.get("V", 0),
                        "early_votes": c.get("EV", 0),
                        "vote_pct": c.get("PE", 0.0),
                    })

        return pd.DataFrame(rows)

    def fetch_county_results(self, label, election_id):
        """Return a DataFrame of county-level race results."""
        data = self._fetch_json(f"election/countyInfo/{election_id}")
        decoded = self._decode_b64(data["upload"])

        rows = []
        for county_id, county in decoded.items():
            county_name = county.get("N", f"County {county_id}")
            for race_key, race in county.get("Races", {}).items():
                name = race.get("N", "")
                if not self._matches_filter(name):
                    continue
                for c in self._iter_candidates(race.get("C", [])):
                    rows.append({
                        "party": label,
                        "county": county_name,
                        "race_name": name.strip(),
                        "race_id": race.get("OID"),
                        "candidate": c.get("N", ""),
                        "votes": c.get("V", 0),
                        "early_votes": c.get("EV", 0),
                        "vote_pct": c.get("PE", 0.0),
                        "precincts_reporting": race.get("PR", 0),
                        "total_precincts": race.get("TP", 0),
                    })

        return pd.DataFrame(rows)

    def get_all_results(self):
        """Fetch statewide and county results for all configured elections.

        Returns dict with keys: statewide, county, status
        """
        statewide_frames = []
        county_frames = []
        status = {}

        for label, eid in self.elections.items():
            try:
                status[label] = self.fetch_reporting_status(eid)
            except Exception as e:
                print(f"Warning: Could not fetch {label} reporting status: {e}")
                status[label] = None

            try:
                sw = self.fetch_statewide_results(label, eid)
                statewide_frames.append(sw)
            except Exception as e:
                print(f"Warning: Could not fetch {label} statewide results: {e}")

            try:
                co = self.fetch_county_results(label, eid)
                county_frames.append(co)
            except Exception as e:
                print(f"Warning: Could not fetch {label} county results: {e}")

        statewide = pd.concat(statewide_frames, ignore_index=True) if statewide_frames else pd.DataFrame()
        county = pd.concat(county_frames, ignore_index=True) if county_frames else pd.DataFrame()

        return {
            "statewide": statewide,
            "county": county,
            "status": status,
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch TX election results")
    parser.add_argument("--election", choices=list(KNOWN_ELECTIONS.keys()),
                        nargs="+", help="Specific election(s) to fetch")
    parser.add_argument("--all-races", action="store_true",
                        help="Include all races, not just federal")
    args = parser.parse_args()

    if args.election:
        elections = {name: KNOWN_ELECTIONS[name]["id"] for name in args.election}
    else:
        elections = DEFAULT_ELECTIONS

    race_filter = None if args.all_races else TXResultsScraper.TARGET_PREFIXES
    scraper = TXResultsScraper(elections=elections, race_filter=race_filter)
    print("Fetching TX election results...")
    results = scraper.get_all_results()

    sw = results["statewide"]
    co = results["county"]
    status = results["status"]

    for label, s in status.items():
        if s:
            print(f"\n{label}:")
            print(f"  Counties reporting: {s['counties_reporting']}/{s['counties_total']}")
            print(f"  Precincts reporting: {s['precincts_reporting']}/{s['precincts_total']}")
            print(f"  Last updated: {s['last_updated']}")

    if not sw.empty:
        print(f"\nStatewide races: {sw['race_name'].nunique()}")
        print(f"Total candidate-rows (statewide): {len(sw)}")

    if not co.empty:
        print(f"\nCounty-level rows: {len(co)}")
        print(f"Counties with data: {co['county'].nunique()}")
        print(f"Races tracked: {co['race_name'].nunique()}")

        # Show leaders per race
        print("\nLeaders by race:")
        for (label, race), grp in co.groupby(["party", "race_name"]):
            totals = grp.groupby("candidate")["votes"].sum().sort_values(ascending=False)
            if len(totals) > 0 and totals.iloc[0] > 0:
                print(f"  [{label}] {race}: {totals.index[0]} ({totals.iloc[0]:,} votes)")
