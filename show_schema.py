import sqlite3

conn = sqlite3.connect("database/bisleri.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(daily_entries)")
for column in cursor.fetchall():
    print(column)

conn.close()