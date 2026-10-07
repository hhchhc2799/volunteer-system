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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
