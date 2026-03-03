# TX Primary Election Results

Live-updating Texas 2026 primary election results dashboard. Scrapes county-level data for US Senate and US House races from the Texas Secretary of State's election night reporting system.

## Quick Start

1. Clone this repo
2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Launch the dashboard:
   ```
   streamlit run app.py
   ```
4. Open http://localhost:8501 in your browser

No API keys or credentials needed — the data source is public.

## Dashboard Features

- **Statewide Overview**: All races ranked by competitiveness, close races highlighted
- **Race Detail**: Drill into any race with county-level breakdown and charts
- **County View**: See all races for a specific county
- **Party color coding**: Red/blue throughout
- **Progress bars**: Counties and precincts reporting
- **Auto-refresh**: Set an interval and the dashboard updates automatically
- **Election picker**: Switch to 2025 historical data for testing
- **Export**: Download filtered data as CSV or Excel directly from the dashboard

## Export Data

One-shot export to timestamped CSV/Excel:
```
python export.py
```

Auto-export loop:
```
python export.py --auto --interval 60
```

### Live CSV for Excel

For a live-updating Excel setup, use `--live` mode. This writes fixed-name CSV files that Excel can connect to as a data source:

```
python export.py --live --interval 60
```

This creates these files in `data/` (overwritten each cycle):
- `tx_primary_LIVE.csv` — all county-level results
- `tx_senate_LIVE.csv` — Senate race only
- `tx_house_LIVE.csv` — House races only
- `tx_statewide_LIVE.csv` — statewide summary

**To connect Excel:**
1. Start the live export: `python export.py --live --interval 60`
2. In Excel: Data > From Text/CSV > select `data/tx_primary_LIVE.csv` > Load
3. To refresh: Data > Refresh All (or set auto-refresh in Connection Properties)

The CSV can be read while being overwritten — no file lock issues.

## Testing

Test with historical election data that has real vote counts:
```
python scraper.py --election "2025 Special CD-18"
```

Run a soak test to validate stability under sustained use:
```
python test_soak.py --duration 5 --interval 30
```

## What's Tracked

- US Senate race (both Republican and Democratic primaries)
- All 38 US House district races (both primaries)
- County-level results for every race (254 TX counties)
- Vote totals, early votes, percentages, precincts reporting
