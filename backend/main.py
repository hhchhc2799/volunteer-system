import os
import sqlite3
from typing import List, Optional
from datetime import datetime, date
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
if not os.path.exists(DB_PATH) and os.path.exists(os.path.join(os.path.dirname(BASE_DIR), "data.db")):
    DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "data.db")

app = FastAPI()

@app.get("/")
def index():
    html_file = os.path.join(os.path.dirname(BASE_DIR), "frontend", "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return res({"msg": "volunteer-system backend running"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as c:
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                stuid TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                tdate DATE NOT NULL,
                tothour REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS allocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tid INTEGER NOT NULL,
                uid INTEGER NOT NULL,
                hour REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_allocs_tid ON allocs(tid);
            CREATE INDEX IF NOT EXISTS idx_allocs_uid ON allocs(uid);
            CREATE INDEX IF NOT EXISTS idx_tasks_tdate ON tasks(tdate);
        ''')

init_db()

def res(dat=None, msg="success", code=200):
    return JSONResponse(
        status_code=code,
        content={
            "code": code,
            "message": msg,
            "data": dat,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    )

def save_allocs(conn, tid: Optional[int], totstu: List[int], tothour: float):
    if not tid or not totstu:
        return
    unique_uids = list(dict.fromkeys(totstu))
    placeholders = ",".join("?" for _ in unique_uids)
    valid_ids = {r[0] for r in conn.execute(f"SELECT id FROM users WHERE id IN ({placeholders})", unique_uids).fetchall()}
    for uid in unique_uids:
        if uid in valid_ids:
            conn.execute(
                "INSERT INTO allocs (tid, uid, hour) VALUES (?, ?, ?)",
                (tid, uid, round(tothour, 1))
            )

class Addu(BaseModel):
    name: str
    stuid: Optional[str] = None
    studentNumber: Optional[str] = None

class Addt(BaseModel):
    title: str
    tdate: Optional[date] = None
    taskDate: Optional[date] = None
    tothour: Optional[float] = None
    totalHours: Optional[float] = None
    totstu: Optional[List[int]] = None
    participantIds: Optional[List[int]] = None

@app.post("/api/v1/members")
def addu(u: Addu):
    name = u.name.strip()
    if not name or len(name) > 50:
        return res(None, "invalid name", 400)
    raw_id = (u.studentNumber or u.stuid or "").strip()
    if len(raw_id) > 50:
        return res(None, "invalid stuid", 400)
    stuid = raw_id if raw_id else f"STU{int(datetime.now().timestamp() * 1000)}"
    try:
        with get_db() as c:
            cur = c.execute("INSERT INTO users (name, stuid) VALUES (?, ?)", (name, stuid))
            return res({"id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return res(None, "stuid exists", 409)

@app.post("/api/v1/tasks")
def addt(t: Addt):
    title = t.title.strip()
    if not title or len(title) > 100:
        return res(None, "invalid title", 400)
    task_date = t.taskDate or t.tdate
    if not task_date:
        return res(None, "date required", 400)
    task_hours = t.totalHours if t.totalHours is not None else t.tothour
    if task_hours is None or task_hours < 0.1 or task_hours > 100.0:
        return res(None, "hours must be between 0.1 and 100", 400)
    uids = t.participantIds if t.participantIds is not None else (t.totstu or [])
    tothour = round(task_hours, 1)
    with get_db() as c:
        cur = c.execute("INSERT INTO tasks (title, tdate, tothour) VALUES (?, ?, ?)", 
                        (title, task_date.isoformat(), tothour))
        tid = cur.lastrowid
        save_allocs(c, tid, uids, tothour)
        return res({"taskId": tid})

@app.get("/api/v1/tasks")
def queryt(page: int = 1, pageSize: int = 10, all: bool = False):
    with get_db() as c:
        total = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if all:
            task_rows = c.execute("SELECT id, title, tdate, tothour FROM tasks ORDER BY id DESC").fetchall()
            ps = total if total > 0 else 1
            p = 1
            total_pages = 1 if total > 0 else 0
        else:
            p = max(1, page)
            ps = max(1, min(100, pageSize))
            offset = (p - 1) * ps
            total_pages = (total + ps - 1) // ps if total > 0 else 0
            task_rows = c.execute(
                "SELECT id, title, tdate, tothour FROM tasks ORDER BY id DESC LIMIT ? OFFSET ?",
                (ps, offset)
            ).fetchall()
        if not task_rows:
            return res({
                "items": [],
                "total": total,
                "page": p,
                "pageSize": ps,
                "totalPages": total_pages
            })
        task_ids = [r["id"] for r in task_rows]
        placeholders = ",".join("?" for _ in task_ids)
        alloc_rows = c.execute(f"""
            SELECT a.tid, u.id, u.name, ROUND(a.hour, 1) as hour
            FROM allocs a
            JOIN users u ON a.uid = u.id
            WHERE a.tid IN ({placeholders})
        """, task_ids).fetchall()
        task_allocs = {}
        for ar in alloc_rows:
            tid = ar["tid"]
            if tid not in task_allocs:
                task_allocs[tid] = []
            task_allocs[tid].append({
                "id": ar["id"],
                "name": ar["name"],
                "hour": ar["hour"],
                "allocatedHours": ar["hour"]
            })
        tasks = []
        for r in task_rows:
            item = dict(r)
            item["tothour"] = round(item["tothour"], 1)
            item["totalHours"] = item["tothour"]
            item["taskDate"] = item["tdate"]
            parts = task_allocs.get(item["id"], [])
            item["participants"] = parts
            item["participantIds"] = [p["id"] for p in parts]
            tasks.append(item)
        return res({
            "items": tasks,
            "total": total,
            "page": p,
            "pageSize": ps,
            "totalPages": total_pages
        })

@app.put("/api/v1/tasks/{tid}")
def modifyt(tid: int, t: Addt):
    title = t.title.strip()
    if not title or len(title) > 100:
        return res(None, "invalid title", 400)
    task_date = t.taskDate or t.tdate
    if not task_date:
        return res(None, "date required", 400)
    task_hours = t.totalHours if t.totalHours is not None else t.tothour
    if task_hours is None or task_hours < 0.1 or task_hours > 100.0:
        return res(None, "hours must be between 0.1 and 100", 400)
    uids = t.participantIds if t.participantIds is not None else (t.totstu or [])
    tothour = round(task_hours, 1)
    with get_db() as c:
        exist = c.execute("SELECT id FROM tasks WHERE id = ?", (tid,)).fetchone()
        if not exist:
            return res(None, "task not found", 404)
        c.execute("UPDATE tasks SET title=?, tdate=?, tothour=? WHERE id=?", 
                  (title, task_date.isoformat(), tothour, tid))
        c.execute("DELETE FROM allocs WHERE tid=?", (tid,))
        save_allocs(c, tid, uids, tothour)
        return res({"taskId": tid})

@app.delete("/api/v1/tasks/{tid}")
def delt(tid: int):
    with get_db() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        c.execute("DELETE FROM allocs WHERE tid=?", (tid,))
        return res(None)

@app.delete("/api/v1/members/{uid}")
def delu(uid: int):
    with get_db() as c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        c.execute("DELETE FROM allocs WHERE uid=?", (uid,))
        return res(None)

@app.get("/api/v1/members/{uid}/hours")
def getuhour(uid: int, page: int = 1, pageSize: int = 5, all: bool = False):
    with get_db() as c:
        total = c.execute("SELECT COUNT(*) FROM allocs WHERE uid = ?", (uid,)).fetchone()[0]
        tot_row = c.execute("SELECT SUM(hour) FROM allocs WHERE uid = ?", (uid,)).fetchone()
        tot = round(tot_row[0], 1) if tot_row and tot_row[0] else 0.0
        if all:
            history = [dict(r) for r in c.execute("""
                SELECT a.tid as taskId, ROUND(a.hour, 1) as allocatedHours, t.title as taskTitle, t.tdate as tdate, t.tdate as taskDate
                FROM allocs a
                JOIN tasks t ON a.tid = t.id
                WHERE a.uid = ?
                ORDER BY t.tdate DESC, t.id DESC
            """, (uid,)).fetchall()]
            return res({
                "tothour": tot,
                "totalHours": tot,
                "history": {
                    "items": history,
                    "total": total,
                    "page": 1,
                    "pageSize": total if total > 0 else 1,
                    "totalPages": 1 if total > 0 else 0
                }
            })
        p = max(1, page)
        ps = max(1, min(100, pageSize))
        offset = (p - 1) * ps
        total_pages = (total + ps - 1) // ps if total > 0 else 0
        history = [dict(r) for r in c.execute("""
            SELECT a.tid as taskId, ROUND(a.hour, 1) as allocatedHours, t.title as taskTitle, t.tdate as tdate, t.tdate as taskDate
            FROM allocs a
            JOIN tasks t ON a.tid = t.id
            WHERE a.uid = ?
            ORDER BY t.tdate DESC, t.id DESC
            LIMIT ? OFFSET ?
        """, (uid, ps, offset)).fetchall()]
        return res({
            "tothour": tot,
            "totalHours": tot,
            "history": {
                "items": history,
                "total": total,
                "page": p,
                "pageSize": ps,
                "totalPages": total_pages
            }
        })

@app.get("/api/v1/hours/leaderboard")
def getalltime(page: int = 1, pageSize: int = 10, all: bool = False):
    with get_db() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if all:
            rows = [dict(r) for r in c.execute("""
                SELECT u.id as memberId, u.name, u.stuid, u.stuid as studentNumber, ROUND(COALESCE(SUM(a.hour), 0.0), 1) as tothour, ROUND(COALESCE(SUM(a.hour), 0.0), 1) as totalHours
                FROM users u
                LEFT JOIN allocs a ON u.id = a.uid
                GROUP BY u.id
                ORDER BY tothour DESC, u.id ASC
            """).fetchall()]
            return res({
                "items": rows,
                "total": total,
                "page": 1,
                "pageSize": total if total > 0 else 1,
                "totalPages": 1 if total > 0 else 0
            })
        p = max(1, page)
        ps = max(1, min(100, pageSize))
        offset = (p - 1) * ps
        total_pages = (total + ps - 1) // ps if total > 0 else 0
        rows = [dict(r) for r in c.execute("""
            SELECT u.id as memberId, u.name, u.stuid, u.stuid as studentNumber, ROUND(COALESCE(SUM(a.hour), 0.0), 1) as tothour, ROUND(COALESCE(SUM(a.hour), 0.0), 1) as totalHours
            FROM users u
            LEFT JOIN allocs a ON u.id = a.uid
            GROUP BY u.id
            ORDER BY tothour DESC, u.id ASC
            LIMIT ? OFFSET ?
        """, (ps, offset)).fetchall()]
        return res({
            "items": rows,
            "total": total,
            "page": p,
            "pageSize": ps,
            "totalPages": total_pages
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=32004, reload=True)
