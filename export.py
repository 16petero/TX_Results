"""
Export TX primary election results to CSV and Excel files.

Usage:
    python export.py                      # One-shot export
    python export.py --auto --interval 60 # Auto-refresh export loop
"""

import argparse
import os
import sys
import time
from datetime import datetime

from scraper import TXResultsScraper


def export_results(scraper):
    """Fetch results and write CSV + Excel to data/."""
    print("Fetching results...")
    results = scraper.get_all_results()
    county = results["county"]
    statewide = results["statewide"]

    if county.empty:
        print("No data returned. Check network connection.")
        return

    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV
    csv_path = f"data/tx_primary_results_{ts}.csv"
    county.to_csv(csv_path, index=False)

    # Excel with multiple sheets
    xlsx_path = f"data/tx_primary_results_{ts}.xlsx"
    with open(xlsx_path, "wb") as f:
        with __import__("pandas").ExcelWriter(f, engine="openpyxl") as writer:
            county.to_excel(writer, sheet_name="County Results", index=False)
            if not statewide.empty:
                statewide.to_excel(writer, sheet_name="Statewide Summary", index=False)

            senate = county[county["race_name"].str.startswith("U. S. SENATOR")]
            if not senate.empty:
                senate.to_excel(writer, sheet_name="Senate by County", index=False)

            house = county[county["race_name"].str.startswith("U. S. REPRESENTATIVE")]
            if not house.empty:
                house.to_excel(writer, sheet_name="House by County", index=False)

    # Status
    for party, s in results["status"].items():
        if s:
            print(f"  {party}: {s['counties_reporting']}/{s['counties_total']} counties reporting")

    print(f"  CSV:   {csv_path} ({len(county)} rows)")
    print(f"  Excel: {xlsx_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Export TX primary election results")
    parser.add_argument("--auto", action="store_true", help="Auto-refresh and re-export")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds (default: 60)")
    args = parser.parse_args()

    scraper = TXResultsScraper()

    if not args.auto:
        export_results(scraper)
        return

    print(f"Auto-export mode: refreshing every {args.interval}s (Ctrl+C to stop)")
    try:
        while True:
            export_results(scraper)
            print(f"Next refresh in {args.interval}s...")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
