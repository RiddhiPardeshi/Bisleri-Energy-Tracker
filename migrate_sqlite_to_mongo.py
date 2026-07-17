import sqlite3
from database import daily_entries
from datetime import datetime

# Connect to SQLite
conn = sqlite3.connect("database/bisleri.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Read all SQLite records
cursor.execute("SELECT * FROM daily_entries")
rows = cursor.fetchall()

migrated = 0
skipped = 0

for row in rows:
    record = dict(row)

    # Remove SQLite primary key
    record.pop("id", None)

    # Convert date string to datetime (MongoDB stores datetime)
    if record.get("date"):
        try:
            if isinstance(record["date"], str):
                record["date"] = datetime.strptime(record["date"], "%Y-%m-%d")
        except Exception:
            pass

    # Skip if same batch already exists
    if daily_entries.find_one({"batch_no": record.get("batch_no")}):
        skipped += 1
        continue

    daily_entries.insert_one(record)
    migrated += 1

conn.close()

print(f"Migration Complete!")
print(f"Migrated: {migrated}")
print(f"Skipped: {skipped}")
print(f"MongoDB Total Records: {daily_entries.count_documents({})}")