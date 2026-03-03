"""
Soak test: repeatedly fetches election data to validate stability under
sustained use. Logs timing, errors, and data consistency.

Usage:
    python test_soak.py                    # 5 minutes, 30s interval
    python test_soak.py --duration 30      # 30 minutes
    python test_soak.py --interval 15      # every 15 seconds
    python test_soak.py --election "2025 Special CD-18"  # test with real votes
"""

import argparse
import time
import traceback
from datetime import datetime

from scraper import TXResultsScraper, KNOWN_ELECTIONS, DEFAULT_ELECTIONS


def run_soak(elections, duration_min, interval_sec, race_filter):
    scraper = TXResultsScraper(elections=elections, race_filter=race_filter)
    end_time = time.time() + duration_min * 60
    cycle = 0
    errors = 0
    timings = []

    print(f"Soak test: {duration_min}min, {interval_sec}s interval")
    print(f"Elections: {list(elections.keys())}")
    print(f"Race filter: {race_filter or 'all races'}")
    print("-" * 60)

    try:
        while time.time() < end_time:
            cycle += 1
            t0 = time.time()
            try:
                results = scraper.get_all_results()
                elapsed = time.time() - t0
                timings.append(elapsed)

                sw = results["statewide"]
                co = results["county"]
                sw_rows = len(sw) if not sw.empty else 0
                co_rows = len(co) if not co.empty else 0
                races = co["race_name"].nunique() if not co.empty else 0
                counties = co["county"].nunique() if not co.empty else 0

                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Cycle {cycle}: {elapsed:.1f}s | "
                      f"{sw_rows} statewide, {co_rows} county rows | "
                      f"{races} races, {counties} counties")

                # Consistency check
                if co_rows == 0:
                    print(f"  WARNING: No county data returned!")

            except Exception as e:
                errors += 1
                elapsed = time.time() - t0
                timings.append(elapsed)
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Cycle {cycle}: ERROR after {elapsed:.1f}s — {e}")
                traceback.print_exc()

            remaining = end_time - time.time()
            if remaining > interval_sec:
                time.sleep(interval_sec)
            elif remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    # Summary
    print("\n" + "=" * 60)
    print("SOAK TEST SUMMARY")
    print(f"  Cycles completed: {cycle}")
    print(f"  Errors: {errors}")
    if timings:
        print(f"  Avg fetch time: {sum(timings)/len(timings):.1f}s")
        print(f"  Max fetch time: {max(timings):.1f}s")
        print(f"  Min fetch time: {min(timings):.1f}s")
    if errors == 0:
        print("  Result: PASS")
    else:
        print(f"  Result: {errors} ERRORS in {cycle} cycles")


def main():
    parser = argparse.ArgumentParser(description="Soak test for TX results scraper")
    parser.add_argument("--duration", type=int, default=5, help="Duration in minutes (default: 5)")
    parser.add_argument("--interval", type=int, default=30, help="Interval in seconds (default: 30)")
    parser.add_argument("--election", choices=list(KNOWN_ELECTIONS.keys()),
                        nargs="+", help="Specific election(s) to test")
    parser.add_argument("--all-races", action="store_true", help="Include all races")
    args = parser.parse_args()

    if args.election:
        elections = {name: KNOWN_ELECTIONS[name]["id"] for name in args.election}
    else:
        elections = DEFAULT_ELECTIONS

    race_filter = None if args.all_races else TXResultsScraper.TARGET_PREFIXES
    run_soak(elections, args.duration, args.interval, race_filter)


if __name__ == "__main__":
    main()
