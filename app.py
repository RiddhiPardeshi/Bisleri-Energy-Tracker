from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

from config import Config
from models import db, DailyEntry
import pandas as pd
import numpy as np

from sklearn.linear_model import LinearRegression
from models import db, DailyEntry, Expense
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


# -----------------------------
# Dashboard
# -----------------------------
@app.route("/")
def dashboard():

    entries = DailyEntry.query.all()

    total_production = sum(entry.production or 0 for entry in entries)
    total_consumption = sum(entry.consumption or 0 for entry in entries)
    total_loss = sum(entry.total_loss_rs or 0 for entry in entries)

    if total_consumption > 0:
        efficiency = ((total_consumption - total_loss) / total_consumption) * 100
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
def add_entry():

    if request.method == "POST":

        # Meter Readings
        generation_opening = float(request.form["generation_opening"])
        generation_closing = float(request.form["generation_closing"])

        import_opening = float(request.form["import_opening"])
        import_closing = float(request.form["import_closing"])

        export_opening = float(request.form["export_opening"])
        export_closing = float(request.form["export_closing"])

        # Automatic Meter Calculation
        generation_total = generation_closing - generation_opening
        import_total = import_closing - import_opening
        export_total = export_closing - export_opening

        consumption = generation_total + import_total - export_total

        # Production
        production = int(request.form["production"])
        production_type = request.form["production_type"]
        boxes = int(request.form["boxes"]) if request.form["boxes"] else 0

        # -----------------------------------------
        # Loss Data - UNITS (entered by operator)
        # -----------------------------------------
        blowing_preform = int(request.form["blowing_preform"] or 0)

        filling_preform = int(request.form["filling_preform"] or 0)
        filling_cap = int(request.form["filling_cap"] or 0)

        labeling_bottle = int(request.form["labeling_bottle"] or 0)
        labeling_cap = int(request.form["labeling_cap"] or 0)
        labeling_sticker = int(request.form["labeling_sticker"] or 0)

        shrink_paper = int(request.form["shrink_paper"] or 0)
        shrink_bottle = int(request.form["shrink_bottle"] or 0)
        shrink_cap = int(request.form["shrink_cap"] or 0)
        shrink_sticker = int(request.form["shrink_sticker"] or 0)

        # -----------------------------------------
        # Loss Data - RUPEES (entered by operator,
        # exactly like the physical register)
        # -----------------------------------------
        blowing_preform_rs = float(request.form["blowing_preform_rs"] or 0)

        filling_preform_rs = float(request.form["filling_preform_rs"] or 0)
        filling_cap_rs = float(request.form["filling_cap_rs"] or 0)

        labeling_bottle_rs = float(request.form["labeling_bottle_rs"] or 0)
        labeling_cap_rs = float(request.form["labeling_cap_rs"] or 0)
        labeling_sticker_rs = float(request.form["labeling_sticker_rs"] or 0)

        shrink_paper_rs = float(request.form["shrink_paper_rs"] or 0)
        shrink_bottle_rs = float(request.form["shrink_bottle_rs"] or 0)
        shrink_cap_rs = float(request.form["shrink_cap_rs"] or 0)
        shrink_sticker_rs = float(request.form["shrink_sticker_rs"] or 0)

        # -----------------------------------------
        # Total Loss Units (simple addition)
        # -----------------------------------------
        total_loss_units = (
            blowing_preform +
            filling_preform +
            filling_cap +
            labeling_bottle +
            labeling_cap +
            labeling_sticker +
            shrink_paper +
            shrink_bottle +
            shrink_cap +
            shrink_sticker
        )

        # -----------------------------------------
        # Total Loss ₹ (simple addition - NO RATE
        # MULTIPLICATION, exactly like the physical
        # register where the operator writes the
        # rupee value directly)
        # -----------------------------------------
        total_loss_rs = (
            blowing_preform_rs +

            filling_preform_rs +
            filling_cap_rs +

            labeling_bottle_rs +
            labeling_cap_rs +
            labeling_sticker_rs +

            shrink_paper_rs +
            shrink_bottle_rs +
            shrink_cap_rs +
            shrink_sticker_rs
        )

        # Save Record
        entry = DailyEntry(

            date=datetime.strptime(
                request.form["date"],
                "%Y-%m-%d"
            ).date(),

            batch_no=request.form["batch_no"],

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

            # Units
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

            # Rupees (manually entered)
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

            # Totals
            total_loss_units=total_loss_units,
            total_loss_rs=total_loss_rs

        )

        db.session.add(entry)
        db.session.commit()

        return redirect(url_for("records"))

    return render_template("add_entry.html")


# -----------------------------
# Records
# -----------------------------
@app.route("/records")
def records():

    entries = DailyEntry.query.all()

    return render_template(
        "records.html",
        entries=entries
    )


# -----------------------------
# Analysis
# -----------------------------
@app.route("/analysis")
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
def expenses():

    expenses = Expense.query.order_by(Expense.date.desc()).all()

    total_expense = sum(e.amount for e in expenses)

    return render_template(

        "expenses.html",

        expenses=expenses,

        total_expense=total_expense

    )

@app.route("/prediction")
def prediction():

    # Fetch all daily entries
    entries = DailyEntry.query.order_by(DailyEntry.date).all()

    if len(entries) == 0:
        return render_template(
            "prediction.html",
            message="No records found."
        )

    # -----------------------------
    # Historical Production
    # -----------------------------
    production = [e.production or 0 for e in entries]

    average_production = sum(production) / len(production)

    # -----------------------------
    # Production Prediction
    # -----------------------------
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
            round(
                min(max(value, minimum), maximum),
                2
            )
            for value in future_prediction
        ]

    # Total Production for next 30 days
    total_prediction = round(sum(future_prediction), 2)

    # -----------------------------
    # Predict Monthly Loss
    # -----------------------------
    total_loss = sum(e.total_loss_rs or 0 for e in entries)

    average_daily_loss = total_loss / len(entries)

    predicted_loss = average_daily_loss * 30

    # -----------------------------
    # Predict Monthly Expenses
    # -----------------------------
    expenses = Expense.query.all()

    total_expense = sum(e.amount or 0 for e in expenses)

    if len(expenses) > 0:
        average_daily_expense = total_expense / len(expenses)
    else:
        average_daily_expense = 0

    predicted_expense = average_daily_expense * 30

    # -----------------------------
    # Revenue Prediction
    # -----------------------------
    SELLING_PRICE_PER_BOTTLE = 12

    predicted_revenue = total_prediction * SELLING_PRICE_PER_BOTTLE

    # -----------------------------
    # Profit Prediction
    # -----------------------------
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
if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)