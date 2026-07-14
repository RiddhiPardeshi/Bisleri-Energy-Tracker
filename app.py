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
from models import db, DailyEntry, Expense, Admin, Stock

import numpy as np
from sklearn.linear_model import LinearRegression
from functools import wraps




app = Flask(__name__)
app.config.from_object(Config)

# Sessions expire after 30 minutes of inactivity instead of lasting
# indefinitely in the browser (fixes "always goes straight to dashboard")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

db.init_app(app)


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
# Admin Login
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):

            session.permanent = True
            session["admin_id"] = admin.id
            session["username"] = admin.username
            

            flash("Login Successful", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid Username or Password", "danger")

    return render_template("login.html")
  # -----------------------------
# Register Admin
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        existing = Admin.query.filter_by(username=username).first()

        if existing:
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        admin = Admin(username=username)
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

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

    today_date = date.today()

    today_entry = DailyEntry.query.filter_by(date=today_date).first()

    total_production = today_entry.production if today_entry else 0
    total_consumption = today_entry.consumption if today_entry else 0
    total_loss = today_entry.total_loss_rs if today_entry else 0

    if today_entry and today_entry.consumption:
        efficiency = (
            (today_entry.production or 0) / today_entry.consumption * 100
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

    last_entry = DailyEntry.query.order_by(DailyEntry.id.desc()).first()
    today_str = date.today().strftime("%Y-%m-%d")

    # Auto-generated batch number
    next_batch_no = f"BSL-{DailyEntry.query.count() + 1:04d}"

    if request.method == "POST":

        error = None

        generation_opening = (last_entry.generation_closing if last_entry else 0.0) or 0.0
        import_opening = (last_entry.import_closing if last_entry else 0.0) or 0.0
        export_opening = (last_entry.export_closing if last_entry else 0.0) or 0.0

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

        entry = DailyEntry(
            date=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
            batch_no=request.form.get("batch_no", ""),

            generation_opening=generation_opening,
            generation_closing=generation_closing,
            generation_total=generation_total,

            import_opening=import_opening,
            import_closing=import_closing,
            import_total=import_total,

            export_opening=export_opening,
            export_closing=export_closing,
            export_total=export_total,

            consumption=consumption,

            production=production,
            production_type=production_type,
            boxes=boxes,

            blowing_preform=blowing_preform,
            filling_preform=filling_preform,
            filling_cap=filling_cap,
            labeling_bottle=labeling_bottle,
            labeling_cap=labeling_cap,
            labeling_sticker=labeling_sticker,

            shrink_paper=shrink_paper,
            shrink_bottle=shrink_bottle,
            shrink_cap=shrink_cap,
            shrink_sticker=shrink_sticker,

            blowing_preform_rs=blowing_preform_rs,
            filling_preform_rs=filling_preform_rs,
            filling_cap_rs=filling_cap_rs,
            labeling_bottle_rs=labeling_bottle_rs,
            labeling_cap_rs=labeling_cap_rs,
            labeling_sticker_rs=labeling_sticker_rs,

            shrink_paper_rs=shrink_paper_rs,
            shrink_bottle_rs=shrink_bottle_rs,
            shrink_cap_rs=shrink_cap_rs,
            shrink_sticker_rs=shrink_sticker_rs,

            total_loss_units=total_loss_units,
            total_loss_rs=total_loss_rs
        )

        db.session.add(entry)
        db.session.commit()

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

    entries = DailyEntry.query.all()

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

    stocks = Stock.query.all()

    return render_template(
        "stock.html",
        stocks=stocks
    )


@app.route("/add_stock", methods=["GET", "POST"])
@login_required
def add_stock():

    if request.method == "POST":

        opening = int(request.form["opening_stock"])
        stock_in = int(request.form["stock_in"])
        stock_out = int(request.form["stock_out"])

        closing = opening + stock_in - stock_out

        item = Stock(
            item_name=request.form["item_name"],
            category=request.form["category"],
            opening_stock=opening,
            stock_in=stock_in,
            stock_out=stock_out,
            closing_stock=closing,
            unit=request.form["unit"]
        )

        db.session.add(item)
        db.session.commit()

        flash("Stock Added Successfully", "success")

        return redirect(url_for("stock"))

    return render_template("add_stock.html")


# -----------------------------
# Analysis
# -----------------------------
@app.route("/analysis")
@login_required
def analysis():

    entries = DailyEntry.query.all()

    total_records = len(entries)

    total_production = sum(entry.production or 0 for entry in entries)
    total_consumption = sum(entry.consumption or 0 for entry in entries)
    total_loss_units = sum(entry.total_loss_units or 0 for entry in entries)
    total_loss_rs = sum(entry.total_loss_rs or 0 for entry in entries)

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

        expense = Expense(
            date=datetime.strptime(
                request.form["date"],
                "%Y-%m-%d"
            ).date(),
            description=request.form["description"],
            amount=float(request.form["amount"]),
            payment_mode=request.form["payment_mode"]
        )

        db.session.add(expense)
        db.session.commit()

        return redirect(url_for("expenses"))

    return render_template("add_expense.html")


# -----------------------------
# Expense Records
# -----------------------------
@app.route("/expenses")
@login_required
def expenses():

    expenses = Expense.query.order_by(Expense.date.desc()).all()

    total_expense = sum(e.amount for e in expenses)

    return render_template(
        "expenses.html",
        expenses=expenses,
        total_expense=total_expense
    )


# -----------------------------
# Prediction
# -----------------------------
@app.route("/prediction")
@login_required
def prediction():

    entries = DailyEntry.query.order_by(DailyEntry.date).all()

    if len(entries) == 0:
        return render_template(
            "prediction.html",
            message="No records found."
        )

    production = [e.production or 0 for e in entries]
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

    total_loss = sum(e.total_loss_rs or 0 for e in entries)
    average_daily_loss = total_loss / len(entries)
    predicted_loss = average_daily_loss * 30

    expenses = Expense.query.all()
    total_expense = sum(e.amount or 0 for e in expenses)

    if len(expenses) > 0:
        average_daily_expense = total_expense / len(expenses)
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
import os

with app.app_context():
    db.create_all()

    if not Admin.query.filter_by(username="admin").first():

        admin = Admin(
            username="admin"
        )

        admin.set_password("admin123")

        db.session.add(admin)
        db.session.commit()

        print("Default Admin Created")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)