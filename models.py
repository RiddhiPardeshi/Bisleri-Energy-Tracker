from werkzeug.security import generate_password_hash, check_password_hash


# -----------------------------
# Roles
# -----------------------------
# "Admin"    -> full access, can create/manage employees
# "Manager"  -> everything except employee management
# "Operator" -> daily entry, records, stock, attendance (no products/employees)
ROLES = ["Admin", "Manager", "Operator"]


# -----------------------------
# Admin Password Helpers
# -----------------------------

def create_admin(username, password):
    return {
        "username": username,
        "password": generate_password_hash(password),
        "role": "Admin"
    }


def verify_password(stored_password, entered_password):
    return check_password_hash(
        stored_password,
        entered_password
    )


# -----------------------------
# Employee Helpers
# -----------------------------

def create_employee(name, username, password, role, phone="", designation=""):
    return {
        "name": name,
        "username": username,
        "password": generate_password_hash(password),
        "role": role if role in ROLES else "Operator",
        "phone": phone,
        "designation": designation
    }