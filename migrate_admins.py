import sqlite3
from database import admins

# Connect to SQLite
conn = sqlite3.connect("database/bisleri.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM admins")
rows = cursor.fetchall()

migrated = 0
skipped = 0

for row in rows:
    user = dict(row)

    # Remove SQLite ID
    user.pop("id", None)

    # Skip if username already exists
    if admins.find_one({"username": user["username"]}):
        skipped += 1
        continue

    # Insert the SAME hashed password into MongoDB
    admins.insert_one(user)
    migrated += 1

conn.close()

print(f"Admins Migrated: {migrated}")
print(f"Admins Skipped: {skipped}")