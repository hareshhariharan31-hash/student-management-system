import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute(
    "INSERT INTO users(username,password,role) VALUES(?,?,?)",
    ("admin", generate_password_hash("admin123"), "admin")
)

conn.commit()
conn.close()

print("Admin Created")
