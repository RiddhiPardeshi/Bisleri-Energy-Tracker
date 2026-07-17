from database import admins
from werkzeug.security import check_password_hash

username = input("Username: ")
password = input("Password: ")

admin = admins.find_one({"username": username})

if admin is None:
    print("❌ User not found")
else:
    print("✅ User found")
    print("Stored Hash:", admin["password"])
    print("Password Match:", check_password_hash(admin["password"], password))