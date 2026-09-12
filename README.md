# TaskDock — FamsUp Session & Maximum-Automation Assistant

TaskDock is a local Streamlit workspace for organizing FamsUp tasks and authorized social-account browser sessions.

## Workflow

1. Open **Connections → FamsUpTasks → Open FamsUp Login** and log in normally.
2. Add/open each authorized social account and log in in its own persistent browser profile.
3. Use **Sync FamsUp** to work from the authenticated FamsUp browser session or import visible task text/JSON.
4. In **Execute**, select the correct social session.
5. **Open session + target**.
6. **Assist action** locates/highlights the likely control.
7. You click the Like/Follow/Subscribe control yourself.
8. **Check action + capture proof** verifies a completed-state indicator where possible and automatically captures the screenshot.
9. Proof is attached to the task and shown in Evidence.

## Security

- Credentials are entered by the user in the browser.
- TaskDock does not store social/FamsUp passwords in SQLite.
- Persistent Playwright profiles are local under `browser_profiles/`.
- Do not commit browser profiles, screenshots, logs, `.env`, or the SQLite database.
- Do not bypass CAPTCHA, anti-bot controls, rate limits, or access controls.

## FamsUp integration

No undocumented API is assumed. Browser-session sync is deliberately user-visible and depends on the current FamsUp site UI. If FamsUp provides an authorized API later, it can be added as a separate adapter.

## Install

Windows:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
playwright install chromium
streamlit run app.py
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
playwright install chromium
streamlit run app.py
```
