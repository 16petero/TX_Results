# TX Election Results

Live-updating Texas election results dashboard. Scrapes county-level data from the Texas Secretary of State's election night reporting system. Supports primaries, runoffs, special elections, and constitutional amendments.

## Quick Start

1. Clone this repo (or download it and save as a folder)
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

## Dashboard

The dashboard is the single control surface for everything:

- **Election picker** — select any combination of elections (primaries, specials, runoffs, amendments)
- **Race Results tab** — all races with vote totals, percentages, and bar charts
- **County Breakdown tab** — pick a race, see results by county
- **County View tab** — pick a county, see all its races
- **Auto-refresh** — enable in sidebar; also writes live CSV if checked
- **Export** — download CSV or Excel directly, or write a live CSV for Excel data source

### Live CSV for Excel

1. In the dashboard sidebar, check "Update live CSV on refresh" and enable auto-refresh
2. In Excel: Data > From Text/CSV > select `data/tx_results_LIVE.csv` > Load
3. Excel can refresh the data connection to pull the latest

## CLI Tools (optional)

The dashboard handles everything, but CLI tools are also available:

```
python export.py                                    # One-shot export
python export.py --live --auto --interval 60        # Live CSV loop
python scraper.py --election "2025 Special CD-18"   # Test with historical data
python test_soak.py --duration 30                   # Stability test
```

## Available Elections

- 2026 Republican Primary / Democratic Primary
- 2026 Runoff CD-18 / Runoff SD-9
- 2025 Special CD-18 / Special SD-9 (completed — good for testing)
- 2025 Constitutional Amendment (completed)
