from database import admins

for user in admins.find():
    print(user)