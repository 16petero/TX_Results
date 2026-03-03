"""
Export TX primary election results to CSV and Excel files.

Usage:
    python export.py                       # One-shot timestamped export
    python export.py --auto --interval 60  # Auto-refresh timestamped export loop
    python export.py --live --interval 60  # Live CSV for Excel data source (overwrites)
"""

import argparse
import os
import time
from datetime import datetime

import pandas as pd
from scraper import TXResultsScraper


def export_results(scraper, live=False):
    """Fetch results and write CSV + Excel to data/.

    If live=True, writes fixed-name files (overwriting each time) for use
    as an Excel Power Query data source. Otherwise writes timestamped files.
    """
    print("Fetching results...")
    results = scraper.get_all_results()
    county = results["county"]
    statewide = results["statewide"]

    if county.empty:
        print("No data returned. Check network connection.")
        return False

    os.makedirs("data", exist_ok=True)

    if live:
        csv_path = "data/tx_primary_LIVE.csv"
        county.to_csv(csv_path, index=False)

        # Also write per-race CSVs for targeted Excel connections
        senate = county[county["race_name"].str.startswith("U. S. SENATOR")]
        if not senate.empty:
            senate.to_csv("data/tx_senate_LIVE.csv", index=False)
        house = county[county["race_name"].str.startswith("U. S. REPRESENTATIVE")]
        if not house.empty:
            house.to_csv("data/tx_house_LIVE.csv", index=False)

        # Statewide summary
        if not statewide.empty:
            statewide.to_csv("data/tx_statewide_LIVE.csv", index=False)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"data/tx_primary_results_{ts}.csv"
        county.to_csv(csv_path, index=False)

        xlsx_path = f"data/tx_primary_results_{ts}.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            county.to_excel(writer, sheet_name="County Results", index=False)
            if not statewide.empty:
                statewide.to_excel(writer, sheet_name="Statewide Summary", index=False)

            senate = county[county["race_name"].str.startswith("U. S. SENATOR")]
            if not senate.empty:
                senate.to_excel(writer, sheet_name="Senate by County", index=False)

            house = county[county["race_name"].str.startswith("U. S. REPRESENTATIVE")]
            if not house.empty:
                house.to_excel(writer, sheet_name="House by County", index=False)

        print(f"  Excel: {xlsx_path}")

    # Status
    now = datetime.now().strftime("%H:%M:%S")
    for label, s in results["status"].items():
        if s:
            print(f"  {label}: {s['counties_reporting']}/{s['counties_total']} counties reporting")

    print(f"  CSV: {csv_path} ({len(county)} rows) [{now}]")
    return True


def main():
    parser = argparse.ArgumentParser(description="Export TX primary election results")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-refresh and re-export (timestamped files)")
    parser.add_argument("--live", action="store_true",
                        help="Live mode: overwrite fixed-name CSVs for Excel data source")
    parser.add_argument("--interval", type=int, default=60,
                        help="Refresh interval in seconds (default: 60)")
    args = parser.parse_args()

    scraper = TXResultsScraper()

    if not args.auto and not args.live:
        export_results(scraper, live=False)
        return

    mode = "live CSV" if args.live else "timestamped"
    print(f"Auto-export mode ({mode}): refreshing every {args.interval}s (Ctrl+C to stop)")
    try:
        while True:
            export_results(scraper, live=args.live)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
