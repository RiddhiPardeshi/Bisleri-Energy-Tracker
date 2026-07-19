from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from datetime import datetime, date, timedelta

from config import Config
from models import create_admin, create_employee, verify_password, ROLES
from database import (
    mongo_db,
    daily_entries,
    admins,
    expenses,
    stocks,
    employees,
    attendance,
    products,
    meters
)

import numpy as np
from sklearn.linear_model import LinearRegression
from functools import wraps
import os


app = Flask(__name__)
app.config.from_object(Config)

# Sessions expire after 30 minutes of inactivity instead of lasting
# indefinitely in the browser (fixes "always goes straight to dashboard")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)


# -----------------------------
# Helper Functions
# -----------------------------

def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def today_start_datetime():
    """Return today's date as a midnight datetime, matching how form
    dates are stored (datetime.strptime(..., "%Y-%m-%d"))."""
    return datetime.combine(date.today(), datetime.min.time())


def current_owner_id():
    """Every piece of plant data (entries, stock, products, meters,
    expenses, attendance, employees) belongs to one Owner/Admin account.

    - When an Admin (owner) is logged in, they ARE the owner, so
      owner_id == their own admin_id.
    - When an Employee is logged in, owner_id is the Admin who created
      that employee (stored on the employee record at creation time).

    This is what keeps two different Owner accounts from ever seeing
    each other's data.
    """
    return session.get("owner_id")


# -----------------------------
# Login Required Decorator
# -----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "admin_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


# -----------------------------
# Role Required Decorator
# -----------------------------
# Usage: @role_required("Admin") or @role_required("Admin", "Manager")
# Must be used AFTER @login_required (i.e. placed below it) so a
# session is guaranteed to already exist.
def role_required(*allowed_roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if "admin_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))

            return f(*args, **kwargs)

        return decorated_function
    return wrapper


# -----------------------------
# Owner / Employee Login
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        # Single login form now - no owner/employee toggle.
        # Usernames are unique across both collections (enforced when
        # an employee is created), so we can safely check both here
        # without any ambiguity about which account is which.
        account = admins.find_one({"username": username})
        login_as = "owner"

        if not account:
            account = employees.find_one({"username": username})
            login_as = "employee"

        if account and verify_password(account["password"], password):

            session.permanent = True
            session["admin_id"] = str(account["_id"])
            session["username"] = account["username"]
            session["role"] = account.get("role", "Admin")
            session["login_as"] = login_as

            if login_as == "employee":
                # Employees belong to whichever Owner/Admin created them.
                session["owner_id"] = account.get("owner_id")
            else:
                # An Owner/Admin account IS its own owner.
                session["owner_id"] = str(account["_id"])

            flash("Login Successful", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

        return redirect(url_for("login"))

    return render_template("login.html")


# -----------------------------
# Register Admin
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        existing = admins.find_one({
            "username": username
        })

        if existing:
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        admin = create_admin(
            username,
            password
        )

        admins.insert_one(admin)

        flash("Account Created Successfully. Please Login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


# -----------------------------
# Logout
# -----------------------------
@app.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully", "success")

    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("login"))


# -----------------------------
# Dashboard
# -----------------------------
@app.route("/dashboard")
@login_required
def dashboard():

    today_dt = today_start_datetime()

    today_entry = daily_entries.find_one({
        "date": today_dt,
        "owner_id": current_owner_id()
    })

    total_production = today_entry.get("production", 0) if today_entry else 0
    total_consumption = today_entry.get("consumption", 0) if today_entry else 0
    total_loss = today_entry.get("total_loss_rs", 0) if today_entry else 0

    if today_entry and today_entry.get("consumption"):
        efficiency = (
            (today_entry.get("production") or 0) / today_entry.get("consumption") * 100
        )
    else:
        efficiency = 0

    return render_template(
        "dashboard.html",
        total_production=total_production,
        total_consumption=total_consumption,
        total_loss=total_loss,
        efficiency=efficiency
    )


# -----------------------------
# Add Daily Entry
# -----------------------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_entry():

    owner_id = current_owner_id()

    last_entry_cursor = daily_entries.find(
        {"owner_id": owner_id}
    ).sort("date", -1).limit(1)
    last_entry = next(last_entry_cursor, None)

    today_str = date.today().strftime("%Y-%m-%d")

    # Auto-generated batch number
    next_batch_no = f"BSL-{daily_entries.count_documents({'owner_id': owner_id}) + 1:04d}"

    if request.method == "POST":

        error = None

        # On the very first entry ever, there's no previous closing
        # reading to inherit from - so the user types their own
        # starting Opening values. From the second entry onward,
        # Opening auto-fills from the previous entry's Closing and
        # stays locked (see add_entry.html).
        if last_entry:
            generation_opening = last_entry.get("generation_closing", 0.0) or 0.0
            import_opening = last_entry.get("import_closing", 0.0) or 0.0
            export_opening = last_entry.get("export_closing", 0.0) or 0.0
        else:
            generation_opening = parse_float(request.form.get("generation_opening"), 0.0) or 0.0
            import_opening = parse_float(request.form.get("import_opening"), 0.0) or 0.0
            export_opening = parse_float(request.form.get("export_opening"), 0.0) or 0.0

        generation_closing = parse_float(request.form.get("generation_closing"), None)
        import_closing = parse_float(request.form.get("import_closing"), None)
        export_closing = parse_float(request.form.get("export_closing"), None)

        if generation_closing is None or import_closing is None or export_closing is None:
            error = "Please enter all closing meter readings."
        elif generation_closing < generation_opening:
            error = "Generation Closing cannot be smaller than Generation Opening."
        elif import_closing < import_opening:
            error = "Import Closing cannot be smaller than Import Opening."
        elif export_closing < export_opening:
            error = "Export Closing cannot be smaller than Export Opening."

        if error:
            return render_template(
                "add_entry.html",
                last_entry=last_entry,
                today=request.form.get("date", today_str),
                form_data=request.form,
                next_batch_no=next_batch_no,
                error=error
            )

        # Meter Calculations
        generation_total = generation_closing - generation_opening
        import_total = import_closing - import_opening
        export_total = export_closing - export_opening
        consumption = generation_total + import_total - export_total

        # Production
        production = parse_int(request.form.get("production"), 0)
        production_type = request.form.get("production_type", "")
        boxes = parse_int(request.form.get("boxes"), 0)

        # Loss Data - Units
        blowing_preform = parse_int(request.form.get("blowing_preform"))
        filling_preform = parse_int(request.form.get("filling_preform"))
        filling_cap = parse_int(request.form.get("filling_cap"))
        labeling_bottle = parse_int(request.form.get("labeling_bottle"))
        labeling_cap = parse_int(request.form.get("labeling_cap"))
        labeling_sticker = parse_int(request.form.get("labeling_sticker"))
        shrink_paper = parse_int(request.form.get("shrink_paper"))
        shrink_bottle = parse_int(request.form.get("shrink_bottle"))
        shrink_cap = parse_int(request.form.get("shrink_cap"))
        shrink_sticker = parse_int(request.form.get("shrink_sticker"))

        # Loss Data - Rupees
        blowing_preform_rs = parse_float(request.form.get("blowing_preform_rs"))
        filling_preform_rs = parse_float(request.form.get("filling_preform_rs"))
        filling_cap_rs = parse_float(request.form.get("filling_cap_rs"))
        labeling_bottle_rs = parse_float(request.form.get("labeling_bottle_rs"))
        labeling_cap_rs = parse_float(request.form.get("labeling_cap_rs"))
        labeling_sticker_rs = parse_float(request.form.get("labeling_sticker_rs"))
        shrink_paper_rs = parse_float(request.form.get("shrink_paper_rs"))
        shrink_bottle_rs = parse_float(request.form.get("shrink_bottle_rs"))
        shrink_cap_rs = parse_float(request.form.get("shrink_cap_rs"))
        shrink_sticker_rs = parse_float(request.form.get("shrink_sticker_rs"))

        total_loss_units = (
            blowing_preform + filling_preform + filling_cap +
            labeling_bottle + labeling_cap + labeling_sticker +
            shrink_paper + shrink_bottle + shrink_cap + shrink_sticker
        )

        total_loss_rs = (
            blowing_preform_rs + filling_preform_rs + filling_cap_rs +
            labeling_bottle_rs + labeling_cap_rs + labeling_sticker_rs +
            shrink_paper_rs + shrink_bottle_rs + shrink_cap_rs + shrink_sticker_rs
        )

        entry = {
            "date": datetime.strptime(request.form["date"], "%Y-%m-%d"),
            "batch_no": request.form.get("batch_no", ""),

            "generation_opening": generation_opening,
            "generation_closing": generation_closing,
            "generation_total": generation_total,

            "import_opening": import_opening,
            "import_closing": import_closing,
            "import_total": import_total,

            "export_opening": export_opening,
            "export_closing": export_closing,
            "export_total": export_total,

            "consumption": consumption,

            "production": production,
            "production_type": production_type,
            "boxes": boxes,

            "blowing_preform": blowing_preform,
            "filling_preform": filling_preform,
            "filling_cap": filling_cap,
            "labeling_bottle": labeling_bottle,
            "labeling_cap": labeling_cap,
            "labeling_sticker": labeling_sticker,

            "shrink_paper": shrink_paper,
            "shrink_bottle": shrink_bottle,
            "shrink_cap": shrink_cap,
            "shrink_sticker": shrink_sticker,

            "blowing_preform_rs": blowing_preform_rs,
            "filling_preform_rs": filling_preform_rs,
            "filling_cap_rs": filling_cap_rs,
            "labeling_bottle_rs": labeling_bottle_rs,
            "labeling_cap_rs": labeling_cap_rs,
            "labeling_sticker_rs": labeling_sticker_rs,

            "shrink_paper_rs": shrink_paper_rs,
            "shrink_bottle_rs": shrink_bottle_rs,
            "shrink_cap_rs": shrink_cap_rs,
            "shrink_sticker_rs": shrink_sticker_rs,

            "total_loss_units": total_loss_units,
            "total_loss_rs": total_loss_rs,

            "owner_id": owner_id
        }

        # insert_one only ADDS a new document - existing plant data
        # is never touched, overwritten, or removed here.
        daily_entries.insert_one(entry)

        flash("Daily Entry Saved Successfully.", "success")

        # Redirect to Records page
        return redirect(url_for("records"))

    # GET Request
    return render_template(
        "add_entry.html",
        last_entry=last_entry,
        today=today_str,
        form_data={},
        next_batch_no=next_batch_no,
        error=None
    )


# -----------------------------
# Records
# -----------------------------
@app.route("/records")
@login_required
def records():

    entries = list(
        daily_entries.find({"owner_id": current_owner_id()}).sort("date", -1)
    )

    return render_template(
        "records.html",
        entries=entries
    )


# -----------------------------
# Stock Module
# -----------------------------
@app.route("/stock")
@login_required
def stock():

    stock_items = list(stocks.find({"owner_id": current_owner_id()}))

    return render_template(
        "stock.html",
        stocks=stock_items
    )


@app.route("/add_stock", methods=["GET", "POST"])
@login_required
def add_stock():

    if request.method == "POST":

        opening = parse_int(request.form.get("opening_stock"))
        stock_in = parse_int(request.form.get("stock_in"))
        stock_out = parse_int(request.form.get("stock_out"))

        closing = opening + stock_in - stock_out

        item = {
            "item_name": request.form.get("item_name", ""),
            "category": request.form.get("category", ""),
            "opening_stock": opening,
            "stock_in": stock_in,
            "stock_out": stock_out,
            "closing_stock": closing,
            "unit": request.form.get("unit", ""),

            "owner_id": current_owner_id()
        }

        # insert_one only ADDS a new document - existing stock records
        # are never touched, overwritten, or removed here.
        stocks.insert_one(item)

        flash("Stock Added Successfully", "success")

        return redirect(url_for("stock"))

    return render_template("add_stock.html")


# -----------------------------
# Analysis
# -----------------------------
@app.route("/analysis")
@login_required
def analysis():

    entries = list(daily_entries.find({"owner_id": current_owner_id()}))

    total_records = len(entries)

    total_production = sum(entry.get("production") or 0 for entry in entries)
    total_consumption = sum(entry.get("consumption") or 0 for entry in entries)
    total_loss_units = sum(entry.get("total_loss_units") or 0 for entry in entries)
    total_loss_rs = sum(entry.get("total_loss_rs") or 0 for entry in entries)

    if total_records > 0:
        avg_production = total_production / total_records
        avg_consumption = total_consumption / total_records
        avg_loss_units = total_loss_units / total_records
        avg_loss_rs = total_loss_rs / total_records
    else:
        avg_production = 0
        avg_consumption = 0
        avg_loss_units = 0
        avg_loss_rs = 0

    return render_template(
        "analysis.html",
        total_records=total_records,
        total_production=total_production,
        total_consumption=total_consumption,
        total_loss_units=total_loss_units,
        total_loss_rs=total_loss_rs,
        avg_production=avg_production,
        avg_consumption=avg_consumption,
        avg_loss_units=avg_loss_units,
        avg_loss_rs=avg_loss_rs
    )


# -----------------------------
# Add Expense
# -----------------------------
@app.route("/add_expense", methods=["GET", "POST"])
@login_required
def add_expense():

    if request.method == "POST":

        expense = {
            "date": datetime.strptime(
                request.form["date"],
                "%Y-%m-%d"
            ),
            "description": request.form.get("description", ""),
            "amount": parse_float(request.form.get("amount")),
            "payment_mode": request.form.get("payment_mode", ""),

            "owner_id": current_owner_id()
        }

        # insert_one only ADDS a new document - existing expense
        # records are never touched, overwritten, or removed here.
        expenses.insert_one(expense)

        return redirect(url_for("expenses_page"))

    return render_template("add_expense.html")


# -----------------------------
# Expense Records
# -----------------------------
@app.route("/expenses")
@login_required
def expenses_page():

    expense_list = list(
        expenses.find({"owner_id": current_owner_id()}).sort("date", -1)
    )

    total_expense = sum(e.get("amount") or 0 for e in expense_list)

    return render_template(
        "expenses.html",
        expenses=expense_list,
        total_expense=total_expense
    )


# -----------------------------
# Employees (Admin only)
# -----------------------------
@app.route("/employees")
@login_required
@role_required("Admin")
def employees_page():

    employee_list = list(
        employees.find({"owner_id": current_owner_id()}).sort("name", 1)
    )

    return render_template(
        "employees.html",
        employees=employee_list
    )


@app.route("/add_employee", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def add_employee():

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        existing = employees.find_one({"username": username})
        existing_admin = admins.find_one({"username": username})

        if existing or existing_admin:
            flash("Username already exists!", "danger")
            return redirect(url_for("add_employee"))

        employee = create_employee(
            name=request.form.get("name", ""),
            username=username,
            password=request.form.get("password", ""),
            role=request.form.get("role", "Operator"),
            phone=request.form.get("phone", ""),
            designation=request.form.get("designation", "")
        )

        # Tie this employee to the owner who created them, so their
        # login later scopes to this same owner's data.
        employee["owner_id"] = current_owner_id()

        employees.insert_one(employee)

        flash("Employee Added Successfully", "success")

        return redirect(url_for("employees_page"))

    return render_template("add_employee.html", roles=ROLES)


# -----------------------------
# Attendance (all logged-in roles)
# -----------------------------
@app.route("/attendance")
@login_required
def attendance_page():

    today_str = date.today().strftime("%Y-%m-%d")

    owner_id = current_owner_id()

    records_list = list(
        attendance.find({"owner_id": owner_id}).sort("date", -1).limit(200)
    )
    employee_list = list(
        employees.find({"owner_id": owner_id}).sort("name", 1)
    )

    return render_template(
        "attendance.html",
        attendance_records=records_list,
        employees=employee_list,
        today=today_str
    )


@app.route("/add_attendance", methods=["GET", "POST"])
@login_required
def add_attendance():

    if request.method == "POST":

        employee_id = request.form.get("employee_id", "")
        employee_name = request.form.get("employee_name", "")
        att_date = request.form.get("date", "")

        record = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "date": datetime.strptime(att_date, "%Y-%m-%d") if att_date else today_start_datetime(),
            "status": request.form.get("status", "Present"),
            "remarks": request.form.get("remarks", ""),

            "owner_id": current_owner_id()
        }

        # insert_one only ADDS a new document - existing attendance
        # records are never touched, overwritten, or removed here.
        attendance.insert_one(record)

        flash("Attendance Marked Successfully", "success")

        return redirect(url_for("attendance_page"))

    return redirect(url_for("attendance_page"))


# -----------------------------
# Products (Admin & Manager)
# -----------------------------
@app.route("/products")
@login_required
@role_required("Admin", "Manager")
def products_page():

    product_list = list(
        products.find({"owner_id": current_owner_id()}).sort("product_name", 1)
    )

    return render_template(
        "products.html",
        products=product_list
    )


@app.route("/add_product", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Manager")
def add_product():

    if request.method == "POST":

        product = {
            "product_name": request.form.get("product_name", ""),
            "category": request.form.get("category", ""),
            "unit": request.form.get("unit", ""),
            "unit_price": parse_float(request.form.get("unit_price")),
            "description": request.form.get("description", ""),

            "owner_id": current_owner_id()
        }

        # insert_one only ADDS a new document - existing product
        # records are never touched, overwritten, or removed here.
        products.insert_one(product)

        flash("Product Added Successfully", "success")

        return redirect(url_for("products_page"))

    return render_template("add_product.html")


# -----------------------------
# Meters (Admin & Manager)
# -----------------------------
@app.route("/meters")
@login_required
@role_required("Admin", "Manager")
def meters_page():

    meter_list = list(
        meters.find({"owner_id": current_owner_id()}).sort("meter_name", 1)
    )

    return render_template(
        "meters.html",
        meters=meter_list
    )


@app.route("/add_meter", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Manager")
def add_meter():

    if request.method == "POST":

        meter = {
            "meter_name": request.form.get("meter_name", ""),
            "meter_type": request.form.get("meter_type", ""),
            "location": request.form.get("location", ""),
            "installed_date": request.form.get("installed_date", ""),
            "status": request.form.get("status", "Active"),

            "owner_id": current_owner_id()
        }

        # insert_one only ADDS a new document - existing meter
        # records are never touched, overwritten, or removed here.
        meters.insert_one(meter)

        flash("Meter Added Successfully", "success")

        return redirect(url_for("meters_page"))

    return render_template("add_meter.html")


# -----------------------------
# Prediction
# -----------------------------
@app.route("/prediction")
@login_required
def prediction():

    owner_id = current_owner_id()

    entries = list(
        daily_entries.find({"owner_id": owner_id}).sort("date", 1)
    )

    if len(entries) == 0:
        return render_template(
            "prediction.html",
            message="No records found."
        )

    production = [e.get("production") or 0 for e in entries]
    average_production = sum(production) / len(production)

    if len(entries) < 3:
        future_prediction = [round(average_production, 2)] * 30
    else:
        X = np.arange(len(entries)).reshape(-1, 1)
        y = np.array(production)

        model = LinearRegression()
        model.fit(X, y)

        future_days = np.arange(
            len(entries),
            len(entries) + 30
        ).reshape(-1, 1)

        future_prediction = model.predict(future_days)

        minimum = average_production * 0.8
        maximum = average_production * 1.2

        future_prediction = [
            round(min(max(value, minimum), maximum), 2)
            for value in future_prediction
        ]

    total_prediction = round(sum(future_prediction), 2)

    total_loss = sum(e.get("total_loss_rs") or 0 for e in entries)
    average_daily_loss = total_loss / len(entries)
    predicted_loss = average_daily_loss * 30

    expense_list = list(expenses.find({"owner_id": owner_id}))
    total_expense = sum(e.get("amount") or 0 for e in expense_list)

    if len(expense_list) > 0:
        average_daily_expense = total_expense / len(expense_list)
    else:
        average_daily_expense = 0

    predicted_expense = average_daily_expense * 30

    SELLING_PRICE_PER_BOTTLE = 12
    predicted_revenue = total_prediction * SELLING_PRICE_PER_BOTTLE

    predicted_profit = (
        predicted_revenue
        - predicted_loss
        - predicted_expense
    )

    return render_template(
        "prediction.html",
        total_prediction=int(total_prediction),
        predictions=[round(x, 2) for x in future_prediction],
        predicted_loss=round(predicted_loss, 2),
        predicted_profit=round(predicted_profit, 2)
    )


# -----------------------------
# Main
# -----------------------------

# Create the default admin ONLY if it does not already exist.
# This never deletes or overwrites existing plant data.
if not admins.find_one({"username": "admin"}):

    admin = create_admin(
        "admin",
        "admin123"
    )

    admins.insert_one(admin)

    print("Default MongoDB Admin Created")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)