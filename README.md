# TaskDock Streamlit

TaskDock is a local-first Streamlit workspace for organizing tasks, authorized social-account records, screenshot evidence, and manual FamsUp handoffs.

## Features

- Task creation and status tracking
- Authorized account records for supported social platforms
- Local screenshot/evidence storage
- SQLite local database
- Evidence history
- Manual FamsUp handoff workflow
- Safe-by-default configuration
- No credentials stored in the database
- No undocumented browser automation
- No CAPTCHA bypass or fake engagement automation

## Project structure

```text
taskdock_streamlit/
├── app.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
└── screenshots/
    └── .gitkeep
```

## Windows setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

## macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Safe defaults

`.env.example` uses:

```env
DRY_RUN=true
FAMSUP_MODE=manual
FAMSUP_OFFICIAL_API_ENABLED=false
FAMSUP_BROWSER_AUTOMATION_ENABLED=false
```

Keep these defaults unless you have a legitimate, documented integration and authorization to enable an official API.

## GitHub safety

The `.gitignore` intentionally excludes:

- `.env` and local secrets
- Streamlit secrets
- SQLite/database files
- screenshots
- logs
- Python virtual environments
- Python cache files
- local data

Only `.env.example` is intended to be committed.

## Security note

Do not place passwords, session cookies, API tokens, recovery codes, or other credentials in this repository or in the local database. Use the platform's official authentication mechanisms and official APIs where available.

## Running

```bash
streamlit run app.py
```
