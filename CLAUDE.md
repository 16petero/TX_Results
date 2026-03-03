# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Texas 2026 primary election night results scraper and dashboard. Fetches live county-level results for US Senate and US House races from the Texas Secretary of State's Civix ENR platform. Provides a Streamlit web dashboard for non-technical users and CSV/Excel export.

## Common Commands

# Install dependencies
pip install -r requirements.txt

# Launch web dashboard (opens browser at http://localhost:8501)
streamlit run app.py

# Export current results to CSV/Excel
python export.py

# Export with auto-refresh
python export.py --auto --interval 60

# One-shot scrape (prints summary to stdout)
python scraper.py

## API Reference

Base URL: https://goelect.txelections.civixapps.com/api-ivis-system/api/s3/enr/

Endpoints:
- electionConstants — lists elections with IDs (base64 JSON in "upload" field)
- election/{id} — statewide/federal summaries + Home metadata (base64 per section)
- election/countyInfo/{id} — all 254 counties with per-race results (base64 in "upload")

Election IDs:
- 53813 = 2026 Republican Primary
- 53814 = 2026 Democratic Primary

Data is base64-encoded JSON. Decode with: json.loads(base64.b64decode(payload))

Key data fields:
- V = votes, EV = early votes, PE = percentage, T = total
- TP = total precincts, PR = precincts reporting
- OTRV = total registered voters
- Home.RefreshTime = recommended refresh interval (minutes)

Race name prefixes for filtering:
- "U. S. SENATOR" (statewide, 1 race)
- "U. S. REPRESENTATIVE DISTRICT" (38 districts)

## File Structure

TX_Results/
├── CLAUDE.md           # This file
├── README.md           # Setup & usage for sharing
├── requirements.txt    # Python dependencies
├── .gitignore
├── scraper.py          # Core API client (TXResultsScraper class)
├── app.py              # Streamlit web dashboard
├── export.py           # CSV/Excel export CLI
└── data/               # Exported files (git-ignored)

## Git Workflow

This project uses git. Follow these practices for all work:

### Branching
- **NEVER work directly on `main`.** Create a feature branch as the very first action — before reading files, before exploring, before anything else. No exceptions.
- Branch names should be descriptive and lowercase with hyphens: `add-county-heatmap`, `fix-base64-decode-error`, `update-refresh-logic`.
- Branch from `main` unless told otherwise.

### Committing
- Commit after each logical unit of work — not one giant commit at the end of a session.
- A "logical unit" means: one new feature, one bug fix, one view update. If you can describe it in one sentence, it's one commit.
- Write clear commit messages in this format:
  - `add: county-level heatmap to dashboard`
  - `fix: base64 decode error on empty payload`
  - `update: refresh interval logic per API guidance`
  - `refactor: extract data filtering into helper`
- Always run `git diff --stat` before committing to review what's being included.
- **Never commit `.env`, data files, or anything in `data/`.** Verify with `git status` before staging.

### End of Session
- Commit all outstanding work before ending a session.
- If work is incomplete, commit to the feature branch with a message prefixed with `wip:` (e.g., `wip: export rework, Excel sheets not yet updated`).
- Update CLAUDE.md if anything changed (new features, scripts, patterns).

### Merging
- Only merge to `main` when the work is complete, tested, and verified.
- Before merging, confirm with the user.

## Working Style

### Before Writing Code
1. **Create a feature branch.** The very first action in every task. See Git Workflow above.
2. Read and understand the API response structure before modifying scraper.py.
3. Test API calls manually with curl before assuming endpoint behavior.
4. **Identify every file that documents or depends on what you're changing** and update them in the same commit.
5. Update CLAUDE.md and README.md when adding new features or commands.

### Robustness
- All HTTP calls must have timeout (30s) and retry logic (3 attempts, exponential backoff).
- Catch and log JSON/base64 decode errors; show stale data with warning instead of crashing.
- Handle KeyboardInterrupt gracefully.
- Never poll faster than 30 seconds.

### Quality
- Prefer correct and verified over fast and assumed.
- If a task is ambiguous, ask before writing code.
- Keep dependencies minimal — only add packages that earn their weight.

### Guardrails
- No credentials or API keys needed (public API), but never commit data/ files.
- Streamlit dashboard must handle network errors with user-friendly messages, not stack traces.

### Keeping Docs Current
A change is not done until CLAUDE.md and README.md are updated.
