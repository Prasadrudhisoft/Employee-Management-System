# connector.py
from dbutils.pooled_db import PooledDB
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

HOST     = os.environ.get("HOST")
USER     = os.environ.get("USER")
PASSWORD = os.environ.get("PASSWORD")
DATABASE = os.environ.get("DATABASE")

# ── Created ONCE when the app starts, reused forever ──
pool = PooledDB(
    creator         = pymysql,          # DB driver
    maxconnections  = 20,               # Max open connections to MySQL at one time
    mincached       = 5,                # Keep 5 connections warm on startup
    maxcached       = 10,               # Max idle connections kept in pool
    maxshared       = 0,                # 0 = no sharing between threads (safest)
    blocking        = True,             # Wait for a free conn instead of crashing
    maxusage        = 500,              # Recycle a connection after 500 uses (prevents stale)
    ping            = 1,                # Ping DB before using connection (auto-reconnect)
    host            = HOST,
    user            = USER,
    password        = PASSWORD,
    database        = DATABASE,
    charset         = 'utf8mb4',
    cursorclass     = pymysql.cursors.DictCursor
)

def get_connection():
    """
    Returns a pooled connection.
    Use exactly like before — just call get_connection().
    The pool handles checkout/checkin automatically on conn.close().
    """
    return pool.connection()