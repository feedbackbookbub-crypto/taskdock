
import os, re, json, sqlite3, time
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
FAMSUP_MODE = os.getenv("FAMSUP_MODE", "browser_session")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

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
    log_event(tid, "task_imported", "Imported into TaskDock")
    return tid

def update_task(tid, **kw):
    if not kw: return
    kw["updated_at"] = now()
    sets = ", ".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [tid]
    c = db(); c.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals); c.commit(); c.close()

def tasks(status=None):
    c = db()
    if status:
        rows = c.execute("SELECT * FROM tasks WHERE status=? ORDER BY id DESC",(status,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    c.close(); return rows

def accounts(service=None):
    c = db()
    if service:
        rows = c.execute("SELECT * FROM accounts WHERE service=? ORDER BY id DESC",(service,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
    c.close(); return rows

def add_account(service, account_name, profile_label, profile_url="", notes=""):
    c=db()
    c.execute("""INSERT INTO accounts(service,account_name,profile_label,profile_url,notes,created_at)
                 VALUES(?,?,?,?,?,?)""",(service,account_name,profile_label,profile_url,notes,now()))
    c.commit(); c.close()

def parser(text):
    t = text.strip()
    low = t.lower()
    platform = next((x for x in ["YouTube","Instagram","Facebook","TikTok","X","Snapchat"] if x.lower() in low), "")
    action = ""
    for k in ["subscribe","follow","like","comment","view"]:
        if k in low:
            action = k.title(); break
    urls = re.findall(r'https?://[^\s)>\]]+', t)
    reward = ""
    m = re.search(r'(?:₦|ngn)\s*[\d,.]+', t, re.I)
    if m: reward = m.group(0)
    fam = ""
    m = re.search(r'(?:task\s*id|famsup\s*id)\s*[:#-]?\s*([A-Za-z0-9_-]+)', t, re.I)
    if m: fam = m.group(1)
    title = f"{platform} {action}".strip() or "FamsUp task"
    return dict(famsup_id=fam,title=title,platform=platform,action=action,
                target_url=urls[0] if urls else "",reward=reward,instructions=t)

def launch_browser(profile_label, start_url=""):
    if not PLAYWRIGHT_ENABLED:
        st.error("Playwright is disabled in .env")
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        st.error(f"Playwright unavailable: {e}")
        return None
    pw = sync_playwright().start()
    profile = PROFILES / re.sub(r"[^A-Za-z0-9_.-]+","_",profile_label)
    profile.mkdir(exist_ok=True)
    browser = pw.chromium.launch_persistent_context(str(profile), headless=False)
    page = browser.pages[0] if browser.pages else browser.new_page()
    if start_url:
        page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
    st.session_state.setdefault("browsers", {})[profile_label] = (pw,browser,page)
    return page

def get_page(profile_label):
    b = st.session_state.get("browsers", {}).get(profile_label)
    return b[2] if b else None

def close_browsers():
    for pw,browser,page in list(st.session_state.get("browsers", {}).values()):
        try: browser.close()
        except: pass
        try: pw.stop()
        except: pass
    st.session_state["browsers"] = {}

def capture(tid, page):
    path = SCREENSHOTS / f"task_{tid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    page.screenshot(path=str(path), full_page=True)
    update_task(tid, proof_path=str(path), status="Proof captured")
    log_event(tid,"proof_captured",str(path))
    return path

init_db()
st.set_page_config(page_title="TaskDock", page_icon="⚡", layout="wide")
st.title("⚡ TaskDock")
st.caption("FamsUp task workspace • local browser sessions • human-confirmed social actions")

with st.sidebar:
    st.header("Connections")
    st.success("FamsUp session" if st.session_state.get("famsup_connected") else "FamsUp not connected")
    social = {a["service"] for a in accounts()}
    st.write("Social sessions:", ", ".join(sorted(social)) if social else "None")
    if st.button("Close all browser sessions"):
        close_browsers()
        st.session_state["famsup_connected"] = False
        st.rerun()

tabs = st.tabs(["⚡ Task Inbox","▶ Execute","🔐 Connections","📥 Sync FamsUp","📸 Evidence","⚙ Settings"])

with tabs[0]:
    st.subheader("FamsUp Task Inbox")
    all_tasks = tasks()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Available", sum(x["status"]=="Available" for x in all_tasks))
    c2.metric("Working", sum(x["status"] in ("Working","Proof captured") for x in all_tasks))
    c3.metric("Proof ready", sum(bool(x["proof_path"]) for x in all_tasks))
    c4.metric("Submitted", sum(x["status"]=="Submitted" for x in all_tasks))
    if not all_tasks:
        st.info("No tasks yet. Connect FamsUp and use Sync FamsUp, or paste a task in the Sync tab.")
    for t in all_tasks:
        with st.container(border=True):
            a,b,c = st.columns([5,2,1])
            with a:
                st.markdown(f"**{t['title']}**")
                st.caption(f"{t['platform']} • {t['action']} • {t['reward'] or 'reward unknown'}")
                if t["target_url"]: st.code(t["target_url"], language=None)
            with b:
                st.write(t["status"])
                st.write("📸 Proof attached" if t["proof_path"] else "No proof")
            with c:
                if st.button("Execute", key=f"exec_{t['id']}"):
                    st.session_state["selected_task"] = t["id"]; st.rerun()

with tabs[1]:
    st.subheader("Execute")
    all_tasks = tasks()
    if not all_tasks:
        st.info("Import or sync a FamsUp task first.")
    else:
        ids=[t["id"] for t in all_tasks]
        default = st.session_state.get("selected_task", ids[0])
        tid = st.selectbox("Task", ids, index=ids.index(default) if default in ids else 0,
                           format_func=lambda x: next(t["title"] for t in all_tasks if t["id"]==x))
        t = next(x for x in all_tasks if x["id"]==tid)
        st.session_state["selected_task"]=tid
        st.write(f"**{t['action']}** on **{t['platform']}** — {t['reward'] or 'reward unknown'}")
        st.write(t["instructions"])
        if t["target_url"]: st.code(t["target_url"], language=None)

        opts=[a for a in accounts(t["platform"]) if a["service"]==t["platform"]]
        if not opts:
            opts=accounts()
        if opts:
            labels=[f"{a['service']} — {a['account_name']} [{a['profile_label']}]" for a in opts]
            ai=st.selectbox("Authorized social session", range(len(opts)), format_func=lambda i:labels[i])
            acct=opts[ai]
            update_task(tid, selected_account_id=acct["id"], status="Working")
            st.caption(f"Browser profile: `{acct['profile_label']}`")
            c1,c2,c3=st.columns(3)
            if c1.button("1. Open session + target", type="primary"):
                page=get_page(acct["profile_label"])
                if not page: page=launch_browser(acct["profile_label"], t["target_url"])
                elif t["target_url"]: page.goto(t["target_url"], wait_until="domcontentloaded", timeout=30000)
                log_event(tid,"target_opened",t["target_url"])
                st.success("Target opened. Log in normally if required.")
            if c2.button("2. Assist action"):
                page=get_page(acct["profile_label"])
                if not page:
                    st.warning("Open the session first.")
                else:
                    # Safe assistance: locate and highlight likely controls; do not click.
                    keywords = [t["action"].lower()]
                    if t["action"].lower()=="subscribe": keywords += ["subscribed"]
                    if t["action"].lower()=="follow": keywords += ["following"]
                    if t["action"].lower()=="like": keywords += ["liked"]
                    count = page.locator("button, a, [role=button]").count()
                    found = 0
                    for i in range(min(count,150)):
                        try:
                            el=page.locator("button, a, [role=button]").nth(i)
                            txt=(el.inner_text(timeout=300) or "").strip().lower()
                            if any(k in txt for k in keywords):
                                el.scroll_into_view_if_needed(timeout=1000)
                                el.evaluate("""e => { e.style.outline='4px solid orange'; e.style.outlineOffset='3px'; }""")
                                found += 1
                                break
                        except: pass
                    st.info("Action control highlighted. **You must click it yourself.**" if found else
                            "Could not reliably locate the control. Find it manually, then use Check action.")
            if c3.button("3. Check action + capture proof"):
                page=get_page(acct["profile_label"])
                if not page: st.warning("Open the session first.")
                else:
                    txt=page.locator("body").inner_text(timeout=3000).lower()
                    action=t["action"].lower()
                    indicators = {
                        "subscribe":["subscribed","unsubscribe"],
                        "follow":["following","unfollow"],
                        "like":["unlike","liked"]
                    }.get(action,[])
                    detected=any(x in txt for x in indicators)
                    if detected:
                        path=capture(tid,page)
                        st.success(f"Completed state detected. Proof captured: {path.name}")
                    else:
                        st.warning("Completed state was not confidently detected. You can perform the action and try again.")
        else:
            st.warning("Connect an authorized social account first.")

with tabs[2]:
    st.subheader("🔐 Connections")
    st.write("Use local persistent browser profiles. Passwords, cookies and tokens are not stored in TaskDock's database.")
    st.markdown("### FamsUpTasks")
    if st.button("Open FamsUp Login", key="famsup_login"):
        page=launch_browser("famsup_main","https://famsuptasks.com/")
        st.session_state["famsup_connected"]=True
        log_event(None,"famsup_session_opened","User login is completed in browser")
        st.success("FamsUp browser session opened. Log in normally in that window.")
    st.divider()
    st.markdown("### Social accounts")
    services=["YouTube","Instagram","Facebook","TikTok","X","Snapchat"]
    for svc in services:
        with st.expander(svc):
            name=st.text_input("Account/handle", key=f"name_{svc}")
            label=st.text_input("Browser profile label", value=svc.lower()+"_main", key=f"profile_{svc}")
            if st.button(f"Open {svc} login", key=f"open_{svc}"):
                add_account(svc,name or svc,label)
                page=launch_browser(label)
                st.success(f"{svc} browser profile opened. Log in normally in that window.")
                log_event(None,"social_session_opened",svc)

with tabs[3]:
    st.subheader("📥 Sync FamsUp")
    st.warning("TaskDock does not pretend an undocumented FamsUp API exists. This sync mode uses the authenticated FamsUp browser session and user-visible task content.")
    if st.button("Open/refresh FamsUp task page", type="primary"):
        page=get_page("famsup_main")
        if not page: page=launch_browser("famsup_main","https://famsuptasks.com/")
        else: page.reload(wait_until="domcontentloaded", timeout=30000)
        st.success("FamsUp opened. Navigate to the task list in the browser.")
    st.markdown("### Import visible task text")
    text=st.text_area("Paste copied FamsUp task text here", height=180)
    if st.button("Import task"):
        if text.strip():
            d=parser(text); tid=add_task(**d)
            st.success(f"Imported task #{tid}: {d['title']}")
        else: st.warning("Paste task text first.")
    st.markdown("### JSON import")
    raw=st.text_area("Task JSON", value='{"title":"YouTube Subscribe","platform":"YouTube","action":"Subscribe","target_url":"https://youtube.com/"}', height=120)
    if st.button("Import JSON"):
        try:
            d=json.loads(raw); tid=add_task(**d); st.success(f"Imported task #{tid}")
        except Exception as e: st.error(str(e))

with tabs[4]:
    st.subheader("📸 Evidence")
    for t in tasks():
        if t["proof_path"] and Path(t["proof_path"]).exists():
            st.markdown(f"**Task #{t['id']} — {t['title']}**")
            st.image(t["proof_path"], use_container_width=True)

with tabs[5]:
    st.subheader("⚙ Settings")
    st.write("DRY_RUN:", DRY_RUN)
    st.write("FAMSUP_MODE:", FAMSUP_MODE)
    st.write("PLAYWRIGHT_ENABLED:", PLAYWRIGHT_ENABLED)
    st.caption("Human-confirmed engagement is intentional: TaskDock can navigate, locate, verify and capture proof, but it does not press Like/Follow/Subscribe buttons automatically.")
