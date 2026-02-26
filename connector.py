import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

HOST = os.environ.get("HOST")
USER = os.environ.get("USER")
PASSWORD = os.environ.get("PASSWORD")
DATABASE = os.environ.get("DATABASE")

def get_connection():
    return pymysql.connect(
        host = HOST,
        user = USER,
        password = PASSWORD,
        database = DATABASE,
        cursorclass=pymysql.cursors.DictCursor
    )