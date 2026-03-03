"""
TXResultsScraper: Fetches and decodes TX primary election results from the
Civix ENR API. Returns pandas DataFrames with county-level data.
"""

import base64
import json
import time
import requests
import pandas as pd


class TXResultsScraper:
    BASE_URL = "https://goelect.txelections.civixapps.com/api-ivis-system/api/s3/enr"
    ELECTIONS = {
        "Republican": 53813,
        "Democratic": 53814,
    }
    TARGET_PREFIXES = ("U. S. SENATOR", "U. S. REPRESENTATIVE DISTRICT")

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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

    def _decode_b64(self, payload):
        """Decode a base64-encoded JSON string."""
        return json.loads(base64.b64decode(payload))

    def fetch_reporting_status(self, election_id):
        """Return reporting status dict from the Home section."""
        data = self._fetch_json(f"election/{election_id}")
        home = self._decode_b64(data["Home"])
        cr = home.get("CountiesReporting", {})
        pr = home.get("PrecinctsReporting", {})
        polling = home.get("PollingReporting", {})
        return {
            "counties_reporting": cr.get("CR", 0),
            "counties_total": cr.get("CT", 254),
            "precincts_reporting": polling.get("PLR", 0),
            "precincts_total": polling.get("PLT", 0),
            "last_updated": home.get("LastUpdatedTime", ""),
            "refresh_interval": home.get("RefreshTime", 5),
        }

    def fetch_statewide_results(self, party, election_id):
        """Return a DataFrame of statewide federal race results."""
        data = self._fetch_json(f"election/{election_id}")
        federal = self._decode_b64(data["Federal"])
        races = federal.get("Races", [])

        rows = []
        for race in races:
            name = race.get("N", "")
            if not name.startswith(self.TARGET_PREFIXES):
                continue
            for c in race.get("Candidates", []):
                rows.append({
                    "party": party,
                    "race_name": name.strip(),
                    "race_id": race.get("id"),
                    "candidate": c.get("N", ""),
                    "votes": c.get("V", 0),
                    "early_votes": c.get("EV", 0),
                    "vote_pct": c.get("PE", 0.0),
                })

        return pd.DataFrame(rows)

    def fetch_county_results(self, party, election_id):
        """Return a DataFrame of county-level federal race results."""
        data = self._fetch_json(f"election/countyInfo/{election_id}")
        decoded = self._decode_b64(data["upload"])

        rows = []
        for county_id, county in decoded.items():
            county_name = county.get("N", f"County {county_id}")
            for race_key, race in county.get("Races", {}).items():
                name = race.get("N", "")
                if not name.startswith(self.TARGET_PREFIXES):
                    continue
                for c in race.get("C", []):
                    rows.append({
                        "party": party,
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
        """Fetch statewide and county results for both primaries.

        Returns dict with keys: statewide, county, status
        """
        statewide_frames = []
        county_frames = []
        status = {}

        for party, eid in self.ELECTIONS.items():
            try:
                status[party] = self.fetch_reporting_status(eid)
            except Exception as e:
                print(f"Warning: Could not fetch {party} reporting status: {e}")
                status[party] = None

            try:
                sw = self.fetch_statewide_results(party, eid)
                statewide_frames.append(sw)
            except Exception as e:
                print(f"Warning: Could not fetch {party} statewide results: {e}")

            try:
                co = self.fetch_county_results(party, eid)
                county_frames.append(co)
            except Exception as e:
                print(f"Warning: Could not fetch {party} county results: {e}")

        statewide = pd.concat(statewide_frames, ignore_index=True) if statewide_frames else pd.DataFrame()
        county = pd.concat(county_frames, ignore_index=True) if county_frames else pd.DataFrame()

        return {
            "statewide": statewide,
            "county": county,
            "status": status,
        }


if __name__ == "__main__":
    scraper = TXResultsScraper()
    print("Fetching TX primary election results...")
    results = scraper.get_all_results()

    sw = results["statewide"]
    co = results["county"]
    status = results["status"]

    for party, s in status.items():
        if s:
            print(f"\n{party} Primary:")
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

        # Show leading candidates for Senate
        senate = co[co["race_name"].str.startswith("U. S. SENATOR")]
        if not senate.empty:
            print("\nUS Senate leaders by party:")
            for party in senate["party"].unique():
                party_senate = senate[senate["party"] == party]
                totals = party_senate.groupby("candidate")["votes"].sum().sort_values(ascending=False)
                if len(totals) > 0:
                    leader = totals.index[0]
                    print(f"  {party}: {leader} ({totals.iloc[0]:,} votes)")
