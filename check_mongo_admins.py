from database import admins

print("MongoDB Admins:\n")

for user in admins.find():
    print(user["username"])