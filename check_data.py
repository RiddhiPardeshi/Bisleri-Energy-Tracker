from database import daily_entries

count = daily_entries.count_documents({})

print("Total plant records:", count)

for data in daily_entries.find().limit(3):
    print(data)