import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import datetime, date

app = FastAPI()

def init_db():
    with sqlite3.connect("data.db") as c:
        cur = c.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                stuid TEXT UNIQUE NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                tdate DATE NOT NULL,
                tothour REAL NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS allocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tid INTEGER NOT NULL,
                uid INTEGER NOT NULL,
                hour REAL NOT NULL
            )
        ''')
        c.commit()

init_db()

def get_db():
    c = sqlite3.connect("data.db")
    c.row_factory = sqlite3.Row
    return c


def res(dat=None, msg="success", code=200):
    return {"code": code, "message": msg, "data": dat, "timestamp": int(datetime.now().timestamp() * 1000)}

class Addu(BaseModel):
    name: str
    stuid: str

class Addt(BaseModel):
    title: str
    tdate: date
    tothour: float
    totstu: List[int]

@app.post("/api/v1/members")
def addu(u: Addu):
    c = get_db()
    cur = c.cursor()
    try:
        cur.execute("INSERT INTO users (name, stuid) VALUES (?, ?)", (u.name, u.stuid))
        c.commit(); 
        return res({"id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return res(None, "stuid exists", 409)
    finally:
        c.close()

@app.post("/api/v1/tasks")
def addt(t: Addt):
    c = get_db() 
    cur = c.cursor()
    cur.execute("INSERT INTO tasks (title, tdate, tothour) VALUES (?, ?, ?)", (t.title, t.tdate.isoformat(), t.tothour))
    tid = cur.lastrowid
    if t.totstu:
        n = len(t.totstu)
        avg = round(t.tothour / n, 2)
        rem = round(t.tothour - avg * n, 2)
        for i, uid in enumerate(t.totstu):
            cur.execute("INSERT INTO allocs (tid, uid, hour) VALUES (?, ?, ?)", (tid, uid, round(avg + (rem if i == 0 else 0), 2)))
    c.commit()
    c.close()
    return res({"taskId": tid})

@app.get("/api/v1/tasks")
def queryt():
    c = get_db()
    cur = c.cursor()
    cur.execute("SELECT id, title, tdate as tdate, tothour as tothour FROM tasks")
    rows = [dict(r) for r in cur.fetchall()]
    c.close()
    return res({"items": rows})

@app.put("/api/v1/tasks/{tid}")
def modifyt(tid: int, t: Addt):
    c = get_db()
    cur = c.cursor()
    cur.execute("UPDATE tasks SET title=?, tdate=?, tothour=? WHERE id=?", (t.title, t.tdate.isoformat(), t.tothour, tid))
    cur.execute("DELETE FROM allocs WHERE tid=?", (tid,))
    if t.totstu:
        n = len(t.totstu)
        avg = round(t.tothour / n, 2)
        rem = round(t.tothour - avg * n, 2)
        for i, uid in enumerate(t.totstu):
            cur.execute("INSERT INTO allocs (tid, uid, hour) VALUES (?, ?, ?)", (tid, uid, round(avg + (rem if i == 0 else 0), 2)))
    c.commit()
    c.close()
    return res({"taskId": tid})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
