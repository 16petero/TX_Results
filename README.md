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

## Export Data

Export current results to CSV/Excel:
```
python export.py
```

Auto-export (re-fetches and exports on a loop):
```
python export.py --auto --interval 60
```

Files are saved to the `data/` directory.

## What's Tracked

- US Senate race (both Republican and Democratic primaries)
- All 38 US House district races (both primaries)
- County-level results for every race (254 TX counties)
- Vote totals, early votes, percentages, precincts reporting
