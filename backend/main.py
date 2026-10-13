import os
import sqlite3
from typing import List, Optional
from datetime import datetime, date
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
if not os.path.exists(DB_PATH) and os.path.exists(os.path.join(os.path.dirname(BASE_DIR), "data.db")):
    DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "data.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
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
    for uid in totstu:
        conn.execute(
            "INSERT INTO allocs (tid, uid, hour) VALUES (?, ?, ?)",
            (tid, uid, round(tothour, 1))
        )

class Addu(BaseModel):
    name: str
    stuid: Optional[str] = None

class Addt(BaseModel):
    title: str
    tdate: date
    tothour: float
    totstu: List[int]

@app.post("/api/v1/members")
def addu(u: Addu):
    stuid = u.stuid.strip() if (u.stuid and u.stuid.strip()) else f"STU{int(datetime.now().timestamp() * 1000)}"
    try:
        with get_db() as c:
            cur = c.execute("INSERT INTO users (name, stuid) VALUES (?, ?)", (u.name.strip(), stuid))
            return res({"id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return res(None, "stuid exists", 409)

@app.post("/api/v1/tasks")
def addt(t: Addt):
    with get_db() as c:
        tothour = round(t.tothour, 1)
        cur = c.execute("INSERT INTO tasks (title, tdate, tothour) VALUES (?, ?, ?)", 
                        (t.title, t.tdate.isoformat(), tothour))
        tid = cur.lastrowid
        save_allocs(c, tid, t.totstu, tothour)
        return res({"taskId": tid})

@app.get("/api/v1/tasks")
def queryt():
    with get_db() as c:
        tasks = []
        for r in c.execute("SELECT id, title, tdate, tothour FROM tasks ORDER BY id DESC").fetchall():
            item = dict(r)
            item["tothour"] = round(item["tothour"], 1)
            participants = [dict(u) for u in c.execute("""
                SELECT u.id, u.name, ROUND(a.hour, 1) as hour
                FROM allocs a
                JOIN users u ON a.uid = u.id
                WHERE a.tid = ?
            """, (item["id"],)).fetchall()]
            item["participants"] = participants
            tasks.append(item)
        return res({"items": tasks})

@app.put("/api/v1/tasks/{tid}")
def modifyt(tid: int, t: Addt):
    with get_db() as c:
        tothour = round(t.tothour, 1)
        c.execute("UPDATE tasks SET title=?, tdate=?, tothour=? WHERE id=?", 
                  (t.title, t.tdate.isoformat(), tothour, tid))
        c.execute("DELETE FROM allocs WHERE tid=?", (tid,))
        save_allocs(c, tid, t.totstu, tothour)
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
def getuhour(uid: int):
    with get_db() as c:
        history = [dict(r) for r in c.execute("""
            SELECT a.tid as taskId, a.hour as allocatedHours, t.title as taskTitle, t.tdate as tdate, t.tdate as taskDate
            FROM allocs a
            JOIN tasks t ON a.tid = t.id
            WHERE a.uid = ?
            ORDER BY t.tdate DESC
        """, (uid,)).fetchall()]
        tot_row = c.execute("SELECT SUM(hour) FROM allocs WHERE uid = ?", (uid,)).fetchone()
        tot = round(tot_row[0], 1) if tot_row and tot_row[0] else 0.0
        return res({"tothour": tot, "history": {"items": history}})

@app.get("/api/v1/hours/leaderboard")
def getalltime():
    with get_db() as c:
        rows = [dict(r) for r in c.execute("""
            SELECT u.id as memberId, u.name, u.stuid, ROUND(COALESCE(SUM(a.hour), 0.0), 1) as tothour
            FROM users u
            LEFT JOIN allocs a ON u.id = a.uid
            GROUP BY u.id
            ORDER BY tothour DESC
        """).fetchall()]
        return res({"items": rows})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)