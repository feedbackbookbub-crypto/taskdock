
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
DB_PATH = DATA_DIR / "taskdock.db"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
FAMSUP_MODE = os.getenv("FAMSUP_MODE", "manual")
FAMSUP_OFFICIAL_API_ENABLED = os.getenv("FAMSUP_OFFICIAL_API_ENABLED", "false").lower() == "true"
FAMSUP_BROWSER_AUTOMATION_ENABLED = os.getenv("FAMSUP_BROWSER_AUTOMATION_ENABLED", "false").lower() == "true"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                account_name TEXT NOT NULL,
                profile_url TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                platform TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending',
                due_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
        )


def add_account(platform, account_name, profile_url, notes):
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "INSERT INTO accounts(platform, account_name, profile_url, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (platform, account_name, profile_url, notes, now),
        )


def add_task(title, platform, due_date, notes):
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "INSERT INTO tasks(title, platform, status, due_date, notes, created_at, updated_at) VALUES (?, ?, 'Pending', ?, ?, ?, ?)",
            (title, platform, due_date, notes, now, now),
        )


def update_task_status(task_id, status):
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, now, task_id),
        )


def save_evidence(task_id, uploaded_file):
    safe_name = Path(uploaded_file.name).name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = SCREENSHOT_DIR / f"{timestamp}_{safe_name}"
    target.write_bytes(uploaded_file.getbuffer())

    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "INSERT INTO evidence(task_id, filename, stored_path, uploaded_at) VALUES (?, ?, ?, ?)",
            (task_id, safe_name, str(target.relative_to(BASE_DIR)), now),
        )


def get_accounts():
    with db() as conn:
        return conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()


def get_tasks():
    with db() as conn:
        return conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()


def get_evidence():
    with db() as conn:
        return conn.execute(
            """
            SELECT evidence.*, tasks.title
            FROM evidence
            JOIN tasks ON tasks.id = evidence.task_id
            ORDER BY evidence.id DESC
            """
        ).fetchall()


init_db()

st.set_page_config(page_title="TaskDock", page_icon="🗂️", layout="wide")

st.title("🗂️ TaskDock")
st.caption("Local task management and evidence workspace for authorized social accounts.")

with st.sidebar:
    st.header("Operating mode")
    st.write(f"DRY_RUN: {'ON' if DRY_RUN else 'OFF'}")
    st.write(f"FamsUp mode: `{FAMSUP_MODE}`")
    st.write(
        "Official FamsUp API: "
        + ("enabled" if FAMSUP_OFFICIAL_API_ENABLED else "disabled")
    )
    st.write(
        "Browser automation: "
        + ("enabled" if FAMSUP_BROWSER_AUTOMATION_ENABLED else "disabled")
    )
    st.info(
        "Safe default: manage tasks and evidence locally. Do not use this app "
        "to bypass CAPTCHA, platform restrictions, or automate fake engagement."
    )

tabs = st.tabs(["Dashboard", "Tasks", "Accounts", "Evidence", "FamsUp Handoff"])

with tabs[0]:
    tasks = get_tasks()
    accounts = get_accounts()
    evidence = get_evidence()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tasks", len(tasks))
    c2.metric("Pending", sum(t["status"] == "Pending" for t in tasks))
    c3.metric("Completed", sum(t["status"] == "Completed" for t in tasks))
    c4.metric("Evidence files", len(evidence))

    st.subheader("Recent tasks")
    if tasks:
        st.dataframe(
            [
                {
                    "ID": t["id"],
                    "Task": t["title"],
                    "Platform": t["platform"],
                    "Status": t["status"],
                    "Due": t["due_date"],
                }
                for t in tasks[:10]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tasks yet. Add your first task from the Tasks tab.")

with tabs[1]:
    st.subheader("Create task")
    with st.form("task_form"):
        title = st.text_input("Task title")
        platform = st.selectbox(
            "Platform",
            ["", "TikTok", "X", "Facebook", "Instagram", "YouTube", "Other"],
        )
        due_date = st.date_input("Due date")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add task")
        if submitted:
            if not title.strip():
                st.error("Task title is required.")
            else:
                add_task(title.strip(), platform, str(due_date), notes.strip())
                st.success("Task added.")
                st.rerun()

    st.subheader("Manage tasks")
    tasks = get_tasks()
    for task in tasks:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                st.write(f"**#{task['id']} — {task['title']}**")
                st.caption(f"{task['platform'] or 'General'} · Due {task['due_date'] or 'Not set'}")
                if task["notes"]:
                    st.write(task["notes"])
            with right:
                new_status = st.selectbox(
                    "Status",
                    ["Pending", "In Progress", "Completed", "Blocked"],
                    index=["Pending", "In Progress", "Completed", "Blocked"].index(task["status"]),
                    key=f"status_{task['id']}",
                    label_visibility="collapsed",
                )
                if new_status != task["status"]:
                    update_task_status(task["id"], new_status)
                    st.rerun()

with tabs[2]:
    st.subheader("Authorized account records")
    with st.form("account_form"):
        platform = st.selectbox(
            "Platform",
            ["TikTok", "X", "Facebook", "Instagram", "YouTube", "Other"],
        )
        account_name = st.text_input("Account name / handle")
        profile_url = st.text_input("Profile URL (optional)")
        notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("Add account")
        if submitted:
            if not account_name.strip():
                st.error("Account name / handle is required.")
            else:
                add_account(platform, account_name.strip(), profile_url.strip(), notes.strip())
                st.success("Account record added.")
                st.rerun()

    accounts = get_accounts()
    if accounts:
        st.dataframe(
            [
                {
                    "ID": a["id"],
                    "Platform": a["platform"],
                    "Account": a["account_name"],
                    "Profile": a["profile_url"],
                    "Notes": a["notes"],
                }
                for a in accounts
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No authorized account records yet.")

with tabs[3]:
    st.subheader("Screenshot / evidence upload")
    tasks = get_tasks()
    if not tasks:
        st.warning("Create a task before attaching evidence.")
    else:
        task_options = {f"#{t['id']} — {t['title']}": t["id"] for t in tasks}
        selected = st.selectbox("Task", list(task_options))
        uploaded = st.file_uploader(
            "Upload screenshot evidence",
            type=["png", "jpg", "jpeg", "webp"],
        )
        if uploaded and st.button("Save evidence"):
            save_evidence(task_options[selected], uploaded)
            st.success("Evidence saved locally.")
            st.rerun()

    evidence = get_evidence()
    if evidence:
        st.subheader("Evidence history")
        st.dataframe(
            [
                {
                    "Task": e["title"],
                    "File": e["filename"],
                    "Stored path": e["stored_path"],
                    "Uploaded": e["uploaded_at"],
                }
                for e in evidence
            ],
            use_container_width=True,
            hide_index=True,
        )

with tabs[4]:
    st.subheader("FamsUp handoff")
    st.write(
        "This safe build prepares information for a manual handoff. It does not "
        "perform undocumented browser automation or automatic login."
    )

    tasks = get_tasks()
    completed = [t for t in tasks if t["status"] == "Completed"]

    if completed:
        selected = st.selectbox(
            "Completed task",
            [f"#{t['id']} — {t['title']}" for t in completed],
        )
        selected_id = int(selected.split("—")[0].replace("#", "").strip())

        related = [e for e in get_evidence() if e["task_id"] == selected_id]
        st.write(f"Evidence attached: **{len(related)}**")

        if st.button("Mark ready for manual FamsUp handoff"):
            st.success(
                "Task marked ready. Open FamsUp separately and complete the "
                "authorized submission/upload manually."
            )
    else:
        st.info("Complete a task first, then prepare its evidence for handoff.")

st.divider()
st.caption("TaskDock • Local-first • Safe-by-default")
