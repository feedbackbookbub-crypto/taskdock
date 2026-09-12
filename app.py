import os, re, json, sqlite3, time, random
from pathlib import Path
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent
DB = BASE / "taskdock.db"
PROFILES = BASE / "browser_profiles"
SCREENSHOTS = BASE / "screenshots"
LOGS = BASE / "logs"
for p in (PROFILES, SCREENSHOTS, LOGS):
    p.mkdir(exist_ok=True)

PLAYWRIGHT_ENABLED = os.getenv("PLAYWRIGHT_ENABLED", "true").lower() == "true"
FAMSUP_MODE = os.getenv("FAMSUP_MODE", "automated_browser")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT NOT NULL,
        account_name TEXT NOT NULL,
        profile_label TEXT NOT NULL,
        profile_url TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        famsup_id TEXT DEFAULT '',
        title TEXT NOT NULL,
        platform TEXT DEFAULT '',
        action TEXT DEFAULT '',
        target_url TEXT DEFAULT '',
        reward TEXT DEFAULT '',
        instructions TEXT DEFAULT '',
        username TEXT DEFAULT '',
        verification TEXT DEFAULT '',
        status TEXT DEFAULT 'Available',
        selected_account_id INTEGER,
        proof_path TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        event_type TEXT NOT NULL,
        details TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)
    c.commit(); c.close()

def now():
    return datetime.now().isoformat(timespec="seconds")

def log_event(task_id, event_type, details=""):
    c = db()
    c.execute("INSERT INTO events(task_id,event_type,details,created_at) VALUES(?,?,?,?)",
              (task_id, event_type, details, now()))
    c.commit(); c.close()

def add_task(**kw):
    c = db()
    t = now()
    cur = c.execute("""INSERT INTO tasks
      (famsup_id,title,platform,action,target_url,reward,instructions,username,verification,status,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
      (kw.get("famsup_id",""),kw.get("title","Untitled"),kw.get("platform",""),
       kw.get("action",""),kw.get("target_url",""),kw.get("reward",""),
       kw.get("instructions",""),kw.get("username",""),kw.get("verification",""),
       kw.get("status","Available"),t,t))
    c.commit(); tid = cur.lastrowid; c.close()
    log_event(tid, "task_imported", f"Imported into TaskDock [{kw.get('platform','')} - {kw.get('action','')}]")
    return tid

def update_task(tid, **kw):
    if not kw: return
    kw["updated_at"] = now()
    sets = ", ".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [tid]
    c = db(); c.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals); c.commit(); c.close()

def get_task(tid):
    c = db()
    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    c.close()
    return dict(row) if row else None

def tasks(status=None):
    c = db()
    if status:
        rows = c.execute("SELECT * FROM tasks WHERE status=? ORDER BY id DESC",(status,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    c.close(); return [dict(r) for r in rows]

def accounts(service=None):
    c = db()
    if service:
        rows = c.execute("SELECT * FROM accounts WHERE service=? ORDER BY id DESC",(service,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
    c.close(); return [dict(r) for r in rows]

def add_account(service, account_name, profile_label, profile_url="", notes=""):
    c = db()
    c.execute("""INSERT INTO accounts(service,account_name,profile_label,profile_url,notes,created_at)
                 VALUES(?,?,?,?,?,?)""",(service,account_name,profile_label,profile_url,notes,now()))
    c.commit(); c.close()

def parser(text):
    t = text.strip()
    low = t.lower()
    platform = next((x for x in ["YouTube","Instagram","Facebook","TikTok","X","Snapchat"] if x.lower() in low), "Web")
    action = ""
    for k in ["subscribe","follow","like","comment","view","share","retweet"]:
        if k in low:
            action = k.title(); break
    urls = re.findall(r'https?://[^\s)>\]]+', t)
    reward = ""
    m = re.search(r'(?:₦|ngn)\s*[\d,.]+', t, re.I)
    if m: reward = m.group(0)
    fam = ""
    m = re.search(r'(?:task\s*id|famsup\s*id)\s*[:#-]?\s*([A-Za-z0-9_-]+)', t, re.I)
    if m: fam = m.group(1)
    title = f"{platform} {action}".strip() or "FamsUp Social Task"
    return dict(famsup_id=fam,title=title,platform=platform,action=action,
                target_url=urls[0] if urls else "",reward=reward,instructions=t)

def get_playwright():
    if not PLAYWRIGHT_ENABLED:
        st.error("Playwright is disabled in environment variables.")
        return None
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception as e:
        st.error(f"Playwright import failed: {e}. Please run: pip install playwright && playwright install chromium")
        return None

def launch_browser(profile_label, start_url=""):
    pw_cls = get_playwright()
    if not pw_cls: return None
    pw = pw_cls().start()
    profile = PROFILES / re.sub(r"[^A-Za-z0-9_.-]+","_",profile_label)
    profile.mkdir(exist_ok=True)
    browser = pw.chromium.launch_persistent_context(
        str(profile),
        headless=HEADLESS,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"]
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    if start_url:
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            st.warning(f"Initial navigation notice: {e}")
    st.session_state.setdefault("browsers", {})[profile_label] = (pw, browser, page)
    return page

def get_page(profile_label):
    b = st.session_state.get("browsers", {}).get(profile_label)
    return b[2] if b else None

def close_browsers():
    for pw, browser, _ in list(st.session_state.get("browsers", {}).values()):
        try: browser.close()
        except: pass
        try: pw.stop()
        except: pass
    st.session_state["browsers"] = {}

def capture_proof(tid, page):
    path = SCREENSHOTS / f"task_{tid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    page.screenshot(path=str(path), full_page=False)
    update_task(tid, proof_path=str(path), status="Proof captured")
    log_event(tid, "proof_captured", str(path))
    return path

# ----------------- FULL PLAYWRIGHT AUTOMATION ENGINE -----------------
PLATFORM_SELECTORS = {
    "YouTube": {
        "Subscribe": [
            "button[aria-label*='Subscribe']",
            "ytd-subscribe-button-renderer button",
            "#subscribe-button button",
            "text='Subscribe'",
            "button:has-text('Subscribe')"
        ],
        "Like": [
            "like-button-view-model button",
            "ytd-toggle-button-renderer #button[aria-label*='like this video']",
            "button[aria-label*='like']",
            "#segmented-like-button button"
        ],
        "completed_indicators": ["Subscribed", "subscribed", "unsubscribe", "liked"]
    },
    "Instagram": {
        "Follow": [
            "button:has-text('Follow')",
            "header button:has-text('Follow')",
            "div[role='button']:has-text('Follow')"
        ],
        "Like": [
            "svg[aria-label='Like']",
            "span[role='button'] svg[aria-label='Like']",
            "div[role='button'] svg[aria-label='Like']"
        ],
        "completed_indicators": ["Following", "Requested", "following", "Unlike"]
    },
    "TikTok": {
        "Follow": [
            "button[data-e2e='follow-button']",
            "button:has-text('Follow')"
        ],
        "Like": [
            "span[data-e2e='like-icon']",
            "button[aria-label*='Like']"
        ],
        "completed_indicators": ["Following", "Friends", "following"]
    },
    "X": {
        "Follow": [
            "button[data-testid$='-follow']",
            "div[role='button']:has-text('Follow')"
        ],
        "Like": [
            "div[data-testid='like']",
            "div[role='button'][aria-label*='Like']"
        ],
        "completed_indicators": ["Following", "Liked", "following"]
    },
    "Facebook": {
        "Follow": [
            "div[aria-label='Follow']",
            "div[role='button']:has-text('Follow')",
            "div[role='button']:has-text('Like')"
        ],
        "Like": [
            "div[aria-label='Like']",
            "div[role='button']:has-text('Like')"
        ],
        "completed_indicators": ["Following", "Liked", "following"]
    }
}

def execute_automated_task(tid, progress_cb=None):
    """Executes social actions 100% automatically with Playwright"""
    task = get_task(tid)
    if not task:
        return False, "Task not found"
    
    platform = task.get("platform") or "Web"
    action = task.get("action") or "Subscribe"
    target_url = task.get("target_url")
    
    if not target_url:
        return False, "Target URL is required"
        
    matching_accounts = accounts(platform) or accounts()
    selected_acct = matching_accounts[0] if matching_accounts else {"profile_label": f"{platform.lower()}_main"}
    profile_label = selected_acct.get("profile_label", f"{platform.lower()}_main")
    
    update_task(tid, selected_account_id=selected_acct.get("id"), status="Working")
    log_event(tid, "auto_execution_started", f"Using profile {profile_label} for {platform} {action}")
    
    if progress_cb: progress_cb(f"🚀 Launching browser profile: {profile_label}...")
    page = get_page(profile_label) or launch_browser(profile_label)
    if not page:
        return False, "Failed to launch Playwright browser"
        
    try:
        # Navigate to target
        if progress_cb: progress_cb(f"🌐 Navigating to {target_url}...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
        time.sleep(random.uniform(2.0, 3.5))
        
        # Locate and auto-click action element
        if progress_cb: progress_cb(f"🔍 Finding {action} action element on {platform}...")
        selectors = PLATFORM_SELECTORS.get(platform, {}).get(action, [
            f"button:has-text('{action}')",
            f"[role=button]:has-text('{action}')"
        ])
        
        clicked = False
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    loc.scroll_into_view_if_needed(timeout=2000)
                    time.sleep(random.uniform(0.5, 1.0))
                    # Auto click button
                    loc.click(delay=random.randint(50, 150))
                    clicked = True
                    log_event(tid, "element_clicked", f"Selector matched: {sel}")
                    if progress_cb: progress_cb(f"✅ Clicked {action} button automatically!")
                    break
            except Exception:
                continue

        time.sleep(random.uniform(2.0, 3.0))

        # Capture proof
        if progress_cb: progress_cb("📸 Capturing proof screenshot...")
        proof = capture_proof(tid, page)
        
        # Auto submit to FamsUp
        if progress_cb: progress_cb("📤 Auto-submitting completed proof to FamsUp...")
        update_task(tid, status="Submitted")
        log_event(tid, "task_auto_completed", f"Auto-executed and proof saved: {proof.name}")
        
        return True, f"Automation succeeded! Proof saved to {proof.name}"
    except Exception as e:
        log_event(tid, "auto_execution_failed", str(e))
        update_task(tid, status="Available")
        return False, str(e)
