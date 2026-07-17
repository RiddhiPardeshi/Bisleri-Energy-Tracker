import sqlite3

conn = sqlite3.connect("database/bisleri.db")
conn.row_factory = sqlite3.Row

cursor = conn.cursor()
cursor.execute("SELECT * FROM admins")

for row in cursor.fetchall():
    print(dict(row))

conn.close()